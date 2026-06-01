FROM python:3.12-slim AS proto-builder

WORKDIR /build
COPY proto/agentcook.proto proto/
RUN pip install --no-cache-dir grpcio grpcio-tools \
    && python -m grpc_tools.protoc \
       -I proto \
       --python_out=. \
       --grpc_python_out=. \
       proto/agentcook.proto

FROM python:3.12-slim

WORKDIR /app
COPY agentcook-swarm/services/connector/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY agentcook-swarm/services/connector/main.py .
COPY --from=proto-builder /build/agentcook_pb2.py .
COPY --from=proto-builder /build/agentcook_pb2_grpc.py .

EXPOSE 8082
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8082"]
