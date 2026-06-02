package cc.agentcook.api.grpc;

import cc.agentcook.grpc.ChatFrame;
import cc.agentcook.grpc.ChatRequest;
import cc.agentcook.grpc.ChatServiceGrpc;
import com.sun.net.httpserver.HttpServer;
import io.grpc.ManagedChannel;
import io.grpc.Server;
import io.grpc.Status;
import io.grpc.inprocess.InProcessChannelBuilder;
import io.grpc.inprocess.InProcessServerBuilder;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.junit.jupiter.api.Assertions.*;

class GrpcChatServiceTest {

    private Server inProcessServer;
    private ManagedChannel channel;
    private ChatServiceGrpc.ChatServiceBlockingStub blockingStub;

    @BeforeEach
    void setUp() throws Exception {
        String serverName = InProcessServerBuilder.generateName();
        inProcessServer = InProcessServerBuilder.forName(serverName)
                .directExecutor()
                .addService(new GrpcChatService("http://localhost:19999"))
                .build()
                .start();
        channel = InProcessChannelBuilder.forName(serverName)
                .directExecutor()
                .build();
        blockingStub = ChatServiceGrpc.newBlockingStub(channel);
    }

    @AfterEach
    void tearDown() {
        if (channel != null) channel.shutdownNow();
        if (inProcessServer != null) inProcessServer.shutdownNow();
    }

    @Test
    void streamChatReturnsErrorWhenUpstreamDown() {
        ChatRequest request = ChatRequest.newBuilder()
                .setSessionId("test-session-1")
                .setMessage("Hello")
                .setModel("gpt-4")
                .build();
        try {
            Iterator<ChatFrame> frames = blockingStub.streamChat(request);
            List<ChatFrame> results = new ArrayList<>();
            frames.forEachRemaining(results::add);
            fail("Expected exception when upstream is down");
        } catch (io.grpc.StatusRuntimeException e) {
            assertTrue(
                    e.getStatus().getCode() == Status.Code.UNAVAILABLE
                            || e.getStatus().getCode() == Status.Code.INTERNAL,
                    "Expected UNAVAILABLE or INTERNAL, got: " + e.getStatus().getCode()
            );
        }
    }

    @Test
    void parseChatFrameExtractsFieldsCorrectly() {
        GrpcChatService service = new GrpcChatService("http://localhost:19999");
        String json = "{\"role\":\"assistant\",\"content\":\"Hello world\",\"done\":false}";
        ChatFrame frame = service.parseChatFrame(json);
        assertEquals("assistant", frame.getRole());
        assertEquals("Hello world", frame.getContent());
        assertFalse(frame.getDone());
    }

    @Test
    void parseChatFrameHandlesDoneTrue() {
        GrpcChatService service = new GrpcChatService("http://localhost:19999");
        String json = "{\"role\":\"assistant\",\"content\":\"\",\"done\":true}";
        ChatFrame frame = service.parseChatFrame(json);
        assertEquals("assistant", frame.getRole());
        assertTrue(frame.getDone());
    }

    @Test
    void parseChatFramePopulatesMetadataWhenPresent() {
        GrpcChatService service = new GrpcChatService("http://localhost:19999");
        String json = "{\"role\":\"assistant\",\"content\":\"hi\",\"done\":false,"
                + "\"metadata\":{},\"model\":\"qwen-turbo\",\"request_id\":\"req-42\"}";
        ChatFrame frame = service.parseChatFrame(json);
        assertEquals("qwen-turbo", frame.getMetadata().getModel());
        assertEquals("req-42", frame.getMetadata().getRequestId());
    }

    @Test
    void parseChatFrameUsesFallbackForMissingFields() {
        GrpcChatService service = new GrpcChatService("http://localhost:19999");
        ChatFrame frame = service.parseChatFrame("{}");
        assertEquals("assistant", frame.getRole());
        assertEquals("", frame.getContent());
        assertFalse(frame.getDone());
    }

    @Test
    void streamChatProxiesSseFramesAndCompletesWhenUpstreamReturnsTwoEvents() throws Exception {
        HttpServer upstream = HttpServer.create(new InetSocketAddress(0), 0);
        upstream.createContext("/api/v1/chat/stream", exchange -> {
            String body = "data: {\"role\":\"assistant\",\"content\":\"你好\",\"done\":false}\n"
                    + "\n"
                    + "data: {\"role\":\"assistant\",\"content\":\"\",\"done\":true,"
                    + "\"metadata\":{},\"model\":\"qwen-turbo\",\"request_id\":\"req-7\"}\n"
                    + "\n"
                    + "data: [DONE]\n\n";
            byte[] payload = body.getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().add("Content-Type", "text/event-stream");
            exchange.sendResponseHeaders(200, payload.length);
            try (OutputStream os = exchange.getResponseBody()) {
                os.write(payload);
            }
        });
        upstream.start();

        Server local = null;
        ManagedChannel localChannel = null;
        try {
            String upstreamUrl = "http://127.0.0.1:" + upstream.getAddress().getPort();
            String name = InProcessServerBuilder.generateName();
            local = InProcessServerBuilder.forName(name).directExecutor()
                    .addService(new GrpcChatService(upstreamUrl))
                    .build()
                    .start();
            localChannel = InProcessChannelBuilder.forName(name).directExecutor().build();

            ChatRequest request = ChatRequest.newBuilder()
                    .setSessionId("s-1")
                    .setMessage("你好\\\"world")
                    .setModel("qwen-turbo")
                    .setTemperature(0.7f)
                    .setMaxTokens(128)
                    .addPluginIds("dingtalk-bot")
                    .addPluginIds("feishu-bot")
                    .build();

            Iterator<ChatFrame> frames = ChatServiceGrpc.newBlockingStub(localChannel).streamChat(request);
            List<ChatFrame> received = new ArrayList<>();
            frames.forEachRemaining(received::add);

            assertThat(received).hasSize(2);
            assertThat(received.get(0).getContent()).isEqualTo("你好");
            assertThat(received.get(1).getDone()).isTrue();
            assertThat(received.get(1).getMetadata().getRequestId()).isEqualTo("req-7");
        } finally {
            if (localChannel != null) localChannel.shutdownNow();
            if (local != null) local.shutdownNow();
            upstream.stop(0);
        }
    }

    @Test
    void streamChatReportsUnavailableWhenUpstreamReturnsHttp503() throws Exception {
        HttpServer upstream = HttpServer.create(new InetSocketAddress(0), 0);
        upstream.createContext("/api/v1/chat/stream", exchange -> {
            exchange.sendResponseHeaders(503, -1);
            exchange.close();
        });
        upstream.start();

        String upstreamUrl = "http://127.0.0.1:" + upstream.getAddress().getPort();
        String name = InProcessServerBuilder.generateName();
        Server local = InProcessServerBuilder.forName(name).directExecutor()
                .addService(new GrpcChatService(upstreamUrl))
                .build()
                .start();
        ManagedChannel localChannel = InProcessChannelBuilder.forName(name).directExecutor().build();
        try {
            ChatRequest request = ChatRequest.newBuilder()
                    .setSessionId("s-2")
                    .setMessage("ping")
                    .build();

            io.grpc.StatusRuntimeException error = assertThrows(
                    io.grpc.StatusRuntimeException.class,
                    () -> ChatServiceGrpc.newBlockingStub(localChannel).streamChat(request)
                            .forEachRemaining(f -> {})
            );
            assertEquals(Status.Code.UNAVAILABLE, error.getStatus().getCode());
            assertTrue(error.getStatus().getDescription().contains("503"));
        } finally {
            localChannel.shutdownNow();
            local.shutdownNow();
            upstream.stop(0);
        }
    }
}
