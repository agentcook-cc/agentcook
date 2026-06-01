package cc.agentcook.api.grpc;

import cc.agentcook.grpc.ChatFrame;
import cc.agentcook.grpc.ChatMetadata;
import cc.agentcook.grpc.ChatRequest;
import cc.agentcook.grpc.ChatServiceGrpc;
import io.grpc.Status;
import io.grpc.stub.StreamObserver;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URI;
import java.nio.charset.StandardCharsets;

/**
 * gRPC ChatService implementation that bridges requests to the Python
 * agent-core /api/v1/chat/stream SSE endpoint.
 */
public class GrpcChatService extends ChatServiceGrpc.ChatServiceImplBase {

    private static final Logger log = LoggerFactory.getLogger(GrpcChatService.class);

    private final String pythonUpstreamUrl;

    public GrpcChatService(String pythonUpstreamUrl) {
        this.pythonUpstreamUrl = pythonUpstreamUrl;
    }

    @Override
    public void streamChat(ChatRequest request, StreamObserver<ChatFrame> responseObserver) {
        log.info("gRPC StreamChat: sessionId={}, model={}", request.getSessionId(), request.getModel());

        HttpURLConnection connection = null;
        try {
            String body = buildJsonBody(request);
            connection = openSseConnection(body);

            int httpStatus = connection.getResponseCode();
            if (httpStatus != 200) {
                log.error("Python upstream returned HTTP {}", httpStatus);
                responseObserver.onError(Status.UNAVAILABLE
                        .withDescription("Python agent-core returned HTTP " + httpStatus)
                        .asRuntimeException());
                return;
            }

            parseSseFrames(connection, responseObserver);
            responseObserver.onCompleted();

        } catch (Exception e) {
            log.error("gRPC StreamChat failed", e);
            responseObserver.onError(Status.INTERNAL
                    .withDescription(e.getMessage())
                    .withCause(e)
                    .asRuntimeException());
        } finally {
            if (connection != null) {
                connection.disconnect();
            }
        }
    }

    private String buildJsonBody(ChatRequest request) {
        StringBuilder json = new StringBuilder("{");
        json.append("\"session_id\":\"").append(escape(request.getSessionId())).append("\"");
        json.append(",\"message\":\"").append(escape(request.getMessage())).append("\"");

        if (!request.getPluginIdsList().isEmpty()) {
            json.append(",\"plugin_ids\":[");
            for (int i = 0; i < request.getPluginIdsCount(); i++) {
                if (i > 0) json.append(",");
                json.append("\"").append(escape(request.getPluginIds(i))).append("\"");
            }
            json.append("]");
        }
        if (!request.getModel().isEmpty()) {
            json.append(",\"model\":\"").append(escape(request.getModel())).append("\"");
        }
        if (request.getTemperature() > 0) {
            json.append(",\"temperature\":").append(request.getTemperature());
        }
        if (request.getMaxTokens() > 0) {
            json.append(",\"max_tokens\":").append(request.getMaxTokens());
        }
        json.append("}");
        return json.toString();
    }

    private HttpURLConnection openSseConnection(String requestBody) throws Exception {
        URI uri = URI.create(pythonUpstreamUrl + "/api/v1/chat/stream");
        HttpURLConnection conn = (HttpURLConnection) uri.toURL().openConnection();
        conn.setRequestMethod("POST");
        conn.setRequestProperty("Content-Type", "application/json");
        conn.setRequestProperty("Accept", "text/event-stream");
        conn.setConnectTimeout(5000);
        conn.setReadTimeout(60000);
        conn.setDoOutput(true);
        conn.getOutputStream().write(requestBody.getBytes(StandardCharsets.UTF_8));
        conn.getOutputStream().flush();
        return conn;
    }

    private void parseSseFrames(HttpURLConnection connection, StreamObserver<ChatFrame> observer)
            throws Exception {
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(connection.getInputStream(), StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                if (!line.startsWith("data: ")) continue;
                String payload = line.substring(6).trim();
                if (payload.isEmpty() || "[DONE]".equals(payload)) continue;
                observer.onNext(parseChatFrame(payload));
            }
        }
    }

    ChatFrame parseChatFrame(String json) {
        ChatFrame.Builder builder = ChatFrame.newBuilder();
        builder.setRole(extractString(json, "role", "assistant"));
        builder.setContent(extractString(json, "content", ""));
        builder.setDone(extractBoolean(json, "done"));

        if (json.contains("\"metadata\"")) {
            ChatMetadata.Builder meta = ChatMetadata.newBuilder();
            meta.setModel(extractString(json, "model", ""));
            meta.setRequestId(extractString(json, "request_id", ""));
            builder.setMetadata(meta.build());
        }
        return builder.build();
    }

    private static String extractString(String json, String field, String fallback) {
        String key = "\"" + field + "\":\"";
        int start = json.indexOf(key);
        if (start < 0) return fallback;
        start += key.length();
        int end = json.indexOf("\"", start);
        return end < 0 ? fallback : json.substring(start, end);
    }

    private static boolean extractBoolean(String json, String field) {
        String key = "\"" + field + "\":";
        int idx = json.indexOf(key);
        if (idx < 0) return false;
        return json.substring(idx + key.length()).trim().startsWith("true");
    }

    private static String escape(String value) {
        if (value == null) return "";
        return value.replace("\\", "\\\\").replace("\"", "\\\"");
    }
}
