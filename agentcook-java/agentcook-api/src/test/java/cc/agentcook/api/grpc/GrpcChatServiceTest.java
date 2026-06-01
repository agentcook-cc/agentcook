package cc.agentcook.api.grpc;

import cc.agentcook.grpc.ChatFrame;
import cc.agentcook.grpc.ChatRequest;
import cc.agentcook.grpc.ChatServiceGrpc;
import io.grpc.ManagedChannel;
import io.grpc.Server;
import io.grpc.Status;
import io.grpc.inprocess.InProcessChannelBuilder;
import io.grpc.inprocess.InProcessServerBuilder;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;

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
}
