package cc.agentcook.api.grpc;

import cc.agentcook.grpc.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.sun.net.httpserver.HttpServer;
import io.grpc.*;
import io.grpc.inprocess.*;
import io.grpc.stub.MetadataUtils;
import io.grpc.stub.StreamObserver;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicReference;

import static org.assertj.core.api.Assertions.*;

class GrpcProtocolTest {
    private final ObjectMapper json = new ObjectMapper();

    @Test
    void escapesRequestAndMapsToolsAndUsage() throws Exception {
        var service = new GrpcChatService("http://localhost:1");
        String text = "引号\" 换行\n反斜杠\\\t";
        var body = json.readTree(service.buildJsonBody(ChatRequest.newBuilder().setMessage(text).addPluginIds(text).build()));
        assertThat(body.path("message").asText()).isEqualTo(text);
        assertThat(body.path("plugin_ids").get(0).asText()).isEqualTo(text);
        assertThat(body.has("session_id")).isFalse();
        assertThat(body.has("model")).isFalse();
        assertThat(body.has("temperature")).isFalse();
        var tool = service.parseChatFrame("{\"type\":\"tool_call\",\"tool_call\":{\"id\":\"1\",\"arguments\":{\"text\":\"a\\n\\\"b\"}}}");
        assertThat(tool.getRole()).isEqualTo("tool");
        assertThat(json.readTree(tool.getContent()).path("arguments").path("text").asText()).isEqualTo("a\n\"b");
        assertThat(service.parseChatFrame("{\"type\":\"tool_result\",\"tool_call\":{\"output\":\"42\"}}").getRole()).isEqualTo("tool");
        var done = service.parseChatFrame("{\"type\":\"done\",\"metadata\":{\"model\":\"test-model\",\"request_id\":\"r\",\"duration_ms\":12.5,\"usage\":{\"input_tokens\":7,\"output_tokens\":3}}}");
        assertThat(done.getDone()).isTrue();
        assertThat(done.getMetadata().getPromptTokens()).isEqualTo(7);
        assertThat(done.getMetadata().getCompletionTokens()).isEqualTo(3);
        assertThat(done.getMetadata().getDurationMs()).isEqualTo(12);
        assertThatThrownBy(() -> service.parseChatFrame("{\"type\":\"error\",\"error\":\"failed\"}"))
                .isInstanceOfSatisfying(StatusRuntimeException.class, e -> assertThat(e.getStatus().getCode()).isEqualTo(Status.Code.INTERNAL));
    }

    @ParameterizedTest
    @CsvSource({"401,UNAUTHENTICATED", "403,PERMISSION_DENIED", "400,INVALID_ARGUMENT", "422,INVALID_ARGUMENT", "409,ABORTED", "500,UNAVAILABLE", "503,UNAVAILABLE"})
    void mapsHttpStatuses(int http, Status.Code expected) {
        assertThat(GrpcChatService.statusFor(http).getCode()).isEqualTo(expected);
    }

    @Test
    void forwardsIdentityAndParsesMultilineEventsUntilDone() throws Exception {
        AtomicReference<String> header = new AtomicReference<>();
        HttpServer upstream = HttpServer.create(new InetSocketAddress(0), 0);
        upstream.createContext("/api/v1/chat/stream", exchange -> {
            header.set(exchange.getRequestHeaders().getFirst("Authorization"));
            exchange.getRequestBody().readAllBytes();
            byte[] body = (": ping\r\nevent: message\r\ndata: {\"type\":\"delta\",\r\ndata: \"content\":\"你好\\n\\\"世界\"}\r\n\r\n"
                    + "data:[DONE]\n\ndata: {\"type\":\"error\"}\n\n").getBytes(StandardCharsets.UTF_8);
            exchange.sendResponseHeaders(200, body.length);
            try (var output = exchange.getResponseBody()) { output.write(body); }
        });
        upstream.start();
        String name = InProcessServerBuilder.generateName();
        Server server = InProcessServerBuilder.forName(name).directExecutor()
                .addService(ServerInterceptors.intercept(new GrpcChatService("http://localhost:" + upstream.getAddress().getPort()), new AuthorizationInterceptor()))
                .build().start();
        ManagedChannel channel = InProcessChannelBuilder.forName(name).directExecutor().build();
        try {
            Metadata headers = new Metadata();
            headers.put(Metadata.Key.of("authorization", Metadata.ASCII_STRING_MARSHALLER), "Bearer caller-access");
            var stub = ChatServiceGrpc.newBlockingStub(channel).withInterceptors(MetadataUtils.newAttachHeadersInterceptor(headers));
            var frames = new ArrayList<ChatFrame>();
            stub.streamChat(ChatRequest.newBuilder().setMessage("hi").build()).forEachRemaining(frames::add);
            assertThat(header.get()).isEqualTo("Bearer caller-access");
            assertThat(frames).hasSize(1);
            assertThat(frames.get(0).getContent()).isEqualTo("你好\n\"世界");
        } finally {
            channel.shutdownNow(); server.shutdownNow(); upstream.stop(0);
        }
    }

    @Test
    void cancellationStopsABlockedRead() throws Exception {
        HttpServer upstream = HttpServer.create(new InetSocketAddress(0), 0);
        CountDownLatch headersSent = new CountDownLatch(1);
        CountDownLatch release = new CountDownLatch(1);
        upstream.createContext("/api/v1/chat/stream", exchange -> {
            exchange.getRequestBody().readAllBytes();
            exchange.sendResponseHeaders(200, 0);
            try (var output = exchange.getResponseBody()) {
                output.write(": ping\n\n".getBytes(StandardCharsets.UTF_8)); output.flush();
                headersSent.countDown();
                try { release.await(10, TimeUnit.SECONDS); } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
            }
        });
        upstream.start();
        var context = Context.current().withCancellation();
        var executor = Executors.newSingleThreadExecutor();
        AtomicReference<Throwable> unexpected = new AtomicReference<>();
        try {
            var future = executor.submit(() -> context.run(() -> new GrpcChatService("http://localhost:" + upstream.getAddress().getPort())
                    .streamChat(ChatRequest.newBuilder().setMessage("hi").build(), new StreamObserver<ChatFrame>() {
                        public void onNext(ChatFrame frame) { unexpected.set(new AssertionError("No data expected")); }
                        public void onError(Throwable error) { unexpected.set(error); }
                        public void onCompleted() { unexpected.set(new AssertionError("Cancelled stream must not complete")); }
                    })));
            assertThat(headersSent.await(5, TimeUnit.SECONDS)).isTrue();
            context.cancel(null);
            future.get(3, TimeUnit.SECONDS);
            assertThat(unexpected.get()).isNull();
        } finally {
            release.countDown(); context.close(); executor.shutdownNow(); upstream.stop(0);
        }
    }
}
