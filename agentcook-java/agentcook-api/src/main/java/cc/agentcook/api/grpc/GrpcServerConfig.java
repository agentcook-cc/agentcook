package cc.agentcook.api.grpc;

import io.grpc.Server;
import io.grpc.ServerBuilder;
import io.grpc.protobuf.services.HealthStatusManager;
import io.grpc.protobuf.services.ProtoReflectionService;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Configuration;

import java.io.IOException;
import java.util.concurrent.TimeUnit;

/**
 * Starts an embedded gRPC server alongside the Spring Boot HTTP server.
 * Registers ChatService, gRPC Health, and Reflection services.
 * Disabled in test profile via grpc.server.enabled=false.
 */
@Configuration
@ConditionalOnProperty(name = "grpc.server.enabled", havingValue = "true", matchIfMissing = true)
public class GrpcServerConfig {

    private static final Logger log = LoggerFactory.getLogger(GrpcServerConfig.class);

    @Value("${grpc.server.port:9090}")
    private int grpcPort;

    @Value("${agentcook.python-upstream-url:http://localhost:8000}")
    private String pythonUpstreamUrl;

    private Server grpcServer;
    private HealthStatusManager healthStatusManager;

    @PostConstruct
    public void startGrpcServer() throws IOException {
        healthStatusManager = new HealthStatusManager();

        grpcServer = ServerBuilder.forPort(grpcPort)
                .addService(new GrpcChatService(pythonUpstreamUrl))
                .addService(healthStatusManager.getHealthService())
                .addService(ProtoReflectionService.newInstance())
                .build()
                .start();

        log.info("gRPC server started on port {}", grpcPort);
    }

    @PreDestroy
    public void stopGrpcServer() {
        if (grpcServer != null && !grpcServer.isShutdown()) {
            try {
                grpcServer.shutdown().awaitTermination(10, TimeUnit.SECONDS);
                log.info("gRPC server stopped");
            } catch (InterruptedException e) {
                grpcServer.shutdownNow();
                Thread.currentThread().interrupt();
            }
        }
    }
}
