-- One Postgres (with pgvector) for both backends, one database each:
--   agentcook_business — agentcook-java (Flyway): users, plugins, connectors, permissions
--   agentcook_runtime  — agent runtime (Alembic): conversations, memory, embeddings
CREATE DATABASE agentcook_runtime OWNER agentcook;
