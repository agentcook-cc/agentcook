# gRPC API Reference

agentcook uses gRPC for two internal hops:

1. **Java → Python**: the admin BFF (Spring Boot) calls the agent core
   over gRPC when the admin UI initiates a chat. SSE is exposed at the
   edge; gRPC carries the inner stream.
2. **Service discovery**: services register themselves into etcd; the
   gateway reads etcd for routing.

End-user clients should consume HTTP/SSE instead — gRPC is an internal
boundary and not stable across releases.

## Protobuf sources

All `.proto` files live in `proto/` at the monorepo root:

```
proto/
  agentcook/
    v1/
      agent.proto        # AgentRuntimeService — chat, completion
      health.proto       # gRPC health-checking protocol
```

Generated stubs are checked in:

- Python: `agentcook-core/src/agentcook_core/grpc_gen/`
- Java: `agentcook-java/agentcook-grpc/target/generated-sources/`

Regenerate with:

```bash
make proto-gen
```

## Services

### `AgentRuntimeService` (port `50051`)

```proto
service AgentRuntimeService {
  rpc Chat(ChatRequest) returns (stream ChatChunk);
  rpc HealthCheck(google.protobuf.Empty) returns (HealthStatus);
}
```

- `Chat` — server-streaming. Each `ChatChunk` carries a partial reply
  token or a structured tool call. The stream terminates with a final
  empty message.
- `HealthCheck` — standard liveness probe.

### `Health` (port `50051`, standard gRPC health protocol)

Implements `grpc.health.v1.Health` so K8s probes can use the official
gRPC health-checking convention.

## Service discovery

Java service registration:

```java
@Configuration
class EtcdRegistration {
  @Bean EtcdServiceRegistry registry() { ... }
}
```

The registry writes a lease-bound key `/services/admin-bff/<instance-id>`
to etcd; the gateway watches the prefix and updates its routing table.

The Python side does the equivalent via `etcd3-py` in
`agent-core/etcd_registry.py`.

## When to use what

| Use case | API |
|----------|-----|
| Browser / Electron client | HTTP + SSE (`/api/v1/...`) |
| Java → Python internal | gRPC (`AgentRuntimeService`) |
| Service registration | etcd (gRPC-backed) |
| K8s probes | HTTP `/actuator/health/{liveness,readiness}` or gRPC health |

External clients should treat the gRPC services as **unstable** and
prefer the HTTP/SSE surface, which is versioned (`/v1/...`) and has a
deprecation policy.
