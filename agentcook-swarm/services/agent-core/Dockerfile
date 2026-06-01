FROM python:3.12-slim AS builder

WORKDIR /build
COPY agentcook-core/pyproject.toml agentcook-core/
COPY agentcook-core/src/ agentcook-core/src/
COPY agentcook/pyproject.toml agentcook/
COPY agentcook/src/ agentcook/src/
COPY proto/ proto/

RUN pip install --no-cache-dir grpcio grpcio-tools \
    && python -m grpc_tools.protoc \
       -I proto \
       --python_out=agentcook/src \
       --grpc_python_out=agentcook/src \
       proto/agentcook.proto

FROM python:3.12-slim

WORKDIR /app
COPY --from=builder /build/agentcook-core /tmp/agentcook-core
COPY --from=builder /build/agentcook /tmp/agentcook
COPY --from=builder /build/agentcook/src/agentcook_pb2.py /app/
COPY --from=builder /build/agentcook/src/agentcook_pb2_grpc.py /app/

RUN pip install --no-cache-dir \
    /tmp/agentcook-core \
    /tmp/agentcook \
    grpcio uvicorn[standard] httpx \
    && rm -rf /tmp/agentcook-core /tmp/agentcook

COPY agentcook-swarm/services/agent-core/main.py .
COPY agentcook-swarm/services/agent-core/grpc_server.py .
COPY agentcook-swarm/services/agent-core/etcd_registry.py .

EXPOSE 8000 50051
ENV AGENT_CORE_PORT=8000
ENV GRPC_PORT=50051

CMD ["python", "main.py"]
