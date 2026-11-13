package cc.agentcook.api.grpc;

import cc.agentcook.grpc.ChatFrame;
import cc.agentcook.grpc.ChatMetadata;
import cc.agentcook.grpc.ChatRequest;
import cc.agentcook.grpc.ChatServiceGrpc;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import io.grpc.Context;
import io.grpc.Status;
import io.grpc.StatusRuntimeException;
import io.grpc.stub.StreamObserver;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.atomic.AtomicReference;

/** Streams the runtime SSE protocol over gRPC, preserving the caller's identity. */
public class GrpcChatService extends ChatServiceGrpc.ChatServiceImplBase {
    private static final ObjectMapper JSON = new ObjectMapper();
    private final HttpClient client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).build();
    private final URI endpoint;

    public GrpcChatService(String pythonUpstreamUrl) {
        endpoint = URI.create(pythonUpstreamUrl.replaceAll("/+$", "") + "/api/v1/chat/stream");
    }

    @Override
    public void streamChat(ChatRequest request, StreamObserver<ChatFrame> observer) {
        Context context = Context.current();
        AtomicReference<InputStream> stream = new AtomicReference<>();
        AtomicReference<CompletableFuture<?>> pending = new AtomicReference<>();
        Context.CancellationListener cancellation = ignored -> {
            CompletableFuture<?> future = pending.get();
            if (future != null) future.cancel(true);
            close(stream.getAndSet(null));
        };
        context.addListener(cancellation, Runnable::run);
        try {
            HttpRequest.Builder upstream = HttpRequest.newBuilder(endpoint)
                    .header("Content-Type", "application/json")
                    .header("Accept", "text/event-stream")
                    .POST(HttpRequest.BodyPublishers.ofString(buildJsonBody(request)));
            String authorization = AuthorizationInterceptor.AUTHORIZATION.get();
            if (authorization != null) upstream.header("Authorization", authorization);
            CompletableFuture<HttpResponse<InputStream>> future = client.sendAsync(
                    upstream.build(), HttpResponse.BodyHandlers.ofInputStream());
            pending.set(future);
            if (context.isCancelled()) future.cancel(true);
            HttpResponse<InputStream> response = future.join();
            stream.set(response.body());
            if (context.isCancelled()) return;
            if (response.statusCode() != 200) {
                throw statusFor(response.statusCode()).withDescription(
                        "Runtime returned HTTP " + response.statusCode()).asRuntimeException();
            }
            readEvents(response.body(), context, observer);
            if (!context.isCancelled()) observer.onCompleted();
        } catch (StatusRuntimeException error) {
            if (!context.isCancelled()) observer.onError(error);
        } catch (Exception error) {
            if (!context.isCancelled()) observer.onError(Status.UNAVAILABLE
                    .withDescription("Runtime stream unavailable").withCause(error).asRuntimeException());
        } finally {
            context.removeListener(cancellation);
            close(stream.getAndSet(null));
        }
    }

    String buildJsonBody(ChatRequest request) throws IOException {
        ObjectNode body = JSON.createObjectNode();
        if (!request.getSessionId().isEmpty()) body.put("session_id", request.getSessionId());
        if (!request.getMessage().isEmpty()) body.put("message", request.getMessage());
        if (!request.getPluginIdsList().isEmpty()) body.set("plugin_ids", JSON.valueToTree(request.getPluginIdsList()));
        if (!request.getModel().isEmpty()) body.put("model", request.getModel());
        // Proto3 scalar fields have no presence; zero represents the omitted default.
        if (request.getTemperature() != 0) body.put("temperature", request.getTemperature());
        if (request.getMaxTokens() != 0) body.put("max_tokens", request.getMaxTokens());
        return JSON.writeValueAsString(body);
    }

    private void readEvents(InputStream input, Context context, StreamObserver<ChatFrame> observer) throws IOException {
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(input, StandardCharsets.UTF_8))) {
            StringBuilder data = new StringBuilder();
            String line;
            while (!context.isCancelled() && (line = reader.readLine()) != null) {
                if (line.isEmpty()) {
                    if (data.length() == 0) continue;
                    String payload = data.substring(0, data.length() - 1);
                    data.setLength(0);
                    if ("[DONE]".equals(payload)) return;
                    if (!payload.isEmpty()) observer.onNext(parseChatFrame(payload));
                } else if (!line.startsWith(":")) {
                    int colon = line.indexOf(':');
                    String field = colon < 0 ? line : line.substring(0, colon);
                    if (!"data".equals(field)) continue;
                    String value = colon < 0 ? "" : line.substring(colon + 1);
                    if (value.startsWith(" ")) value = value.substring(1);
                    data.append(value).append('\n');
                }
            }
            // An unterminated event is not dispatched by the SSE protocol.
        }
    }

    ChatFrame parseChatFrame(String payload) {
        try {
            JsonNode frame = JSON.readTree(payload);
            if (frame == null || !frame.isObject()) throw new IOException("Expected an object frame");
            String type = frame.path("type").asText();
            if ("error".equals(type)) throw Status.INTERNAL
                    .withDescription(frame.path("error").asText("Runtime run failed")).asRuntimeException();
            boolean tool = "tool_call".equals(type) || "tool_result".equals(type);
            ChatFrame.Builder result = ChatFrame.newBuilder()
                    .setRole(tool ? "tool" : frame.path("role").asText("assistant"))
                    .setContent(tool ? JSON.writeValueAsString(frame.path("tool_call")) : frame.path("content").asText(""))
                    .setDone("done".equals(type) || frame.path("done").asBoolean());
            JsonNode metadata = frame.path("metadata");
            if (metadata.isObject()) {
                JsonNode usage = metadata.path("usage");
                result.setMetadata(ChatMetadata.newBuilder()
                        .setModel(metadata.path("model").asText(""))
                        .setRequestId(metadata.path("request_id").asText(""))
                        .setPromptTokens(usage.path("input_tokens").asInt(metadata.path("prompt_tokens").asInt()))
                        .setCompletionTokens(usage.path("output_tokens").asInt(metadata.path("completion_tokens").asInt()))
                        .setDurationMs(metadata.path("duration_ms").asLong()));
            }
            return result.build();
        } catch (IOException error) {
            throw Status.INTERNAL.withDescription("Invalid runtime event").withCause(error).asRuntimeException();
        }
    }

    static Status statusFor(int code) {
        return switch (code) {
            case 401 -> Status.UNAUTHENTICATED;
            case 403 -> Status.PERMISSION_DENIED;
            case 400, 422 -> Status.INVALID_ARGUMENT;
            case 409 -> Status.ABORTED;
            default -> Status.UNAVAILABLE;
        };
    }

    private static void close(InputStream input) {
        if (input != null) {
            try { input.close(); } catch (IOException ignored) { /* Already closed on cancellation. */ }
        }
    }
}
