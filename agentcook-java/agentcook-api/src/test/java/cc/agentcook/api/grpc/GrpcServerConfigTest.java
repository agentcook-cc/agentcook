package cc.agentcook.api.grpc;

import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;
import io.grpc.health.v1.HealthCheckRequest;
import io.grpc.health.v1.HealthCheckResponse;
import io.grpc.health.v1.HealthGrpc;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import java.net.ServerSocket;
import java.util.concurrent.TimeUnit;

import static org.assertj.core.api.Assertions.assertThat;

class GrpcServerConfigTest {

    private GrpcServerConfig config;
    private int port;

    @BeforeEach
    void setUp() throws Exception {
        try (ServerSocket socket = new ServerSocket(0)) {
            port = socket.getLocalPort();
        }
        config = new GrpcServerConfig();
        ReflectionTestUtils.setField(config, "grpcPort", port);
        ReflectionTestUtils.setField(config, "pythonUpstreamUrl", "http://localhost:8000");
    }

    @AfterEach
    void tearDown() {
        if (config != null) {
            config.stopGrpcServer();
        }
    }

    @Test
    @DisplayName("PostConstruct starts an embedded gRPC server on the configured port")
    void startGrpcServerListensOnConfiguredPort() throws Exception {
        config.startGrpcServer();

        ManagedChannel channel = ManagedChannelBuilder.forAddress("127.0.0.1", port)
                .usePlaintext()
                .build();
        try {
            HealthCheckResponse response = HealthGrpc.newBlockingStub(channel)
                    .withDeadlineAfter(2, TimeUnit.SECONDS)
                    .check(HealthCheckRequest.newBuilder().build());
            assertThat(response.getStatus()).isEqualTo(HealthCheckResponse.ServingStatus.SERVING);
        } finally {
            channel.shutdownNow().awaitTermination(2, TimeUnit.SECONDS);
        }
    }

    @Test
    @DisplayName("PreDestroy is a no-op when the server was never started")
    void stopGrpcServerHandlesUninitialisedServer() {
        config.stopGrpcServer();
    }

    @Test
    @DisplayName("PreDestroy shuts down a running server and releases the port")
    void stopGrpcServerReleasesPort() throws Exception {
        config.startGrpcServer();
        config.stopGrpcServer();

        try (ServerSocket socket = new ServerSocket(port)) {
            assertThat(socket.isBound()).isTrue();
        }
    }

    @Test
    @DisplayName("PreDestroy is idempotent: second call on an already-stopped server is safe")
    void stopGrpcServerIsIdempotent() throws Exception {
        config.startGrpcServer();
        config.stopGrpcServer();
        config.stopGrpcServer();
    }
}
