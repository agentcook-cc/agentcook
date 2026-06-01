-- V2: Seed initial admin user + default plugins for dev/docker environments.
-- Production deployments should skip this via Flyway's target version or
-- environment-specific migration locations.

INSERT INTO users (id, email, nickname, status, created_at, updated_at)
VALUES ('00000000-0000-0000-0000-000000000001', 'admin@agentcook.cc', 'Admin', 'ACTIVE', NOW(), NOW())
ON CONFLICT (email) DO NOTHING;

INSERT INTO plugins (id, name, version, kind, description, status, created_at, updated_at)
VALUES
    ('00000000-0000-0000-0000-000000000010', 'dingtalk-bot', '1.0.0', 'WEBHOOK', 'DingTalk group bot connector', 'PUBLISHED', NOW(), NOW()),
    ('00000000-0000-0000-0000-000000000011', 'feishu-bot', '1.0.0', 'WEBHOOK', 'Feishu/Lark group bot connector', 'PUBLISHED', NOW(), NOW()),
    ('00000000-0000-0000-0000-000000000012', 'mcp-filesystem', '1.0.0', 'MCP', 'MCP filesystem tool server', 'PUBLISHED', NOW(), NOW())
ON CONFLICT ON CONSTRAINT uk_plugins_name_version DO NOTHING;

-- Grant admin user all permissions
INSERT INTO permissions (id, user_id, resource, action, effect, created_at)
VALUES
    ('00000000-0000-0000-0000-000000000020', '00000000-0000-0000-0000-000000000001', 'plugin:*', 'activate', 'ALLOW', NOW()),
    ('00000000-0000-0000-0000-000000000021', '00000000-0000-0000-0000-000000000001', 'user:*', 'manage', 'ALLOW', NOW())
ON CONFLICT (id) DO NOTHING;
