-- V3: Performance indexes for common query patterns.

-- Users: lookup by status (admin list filtered view)
CREATE INDEX IF NOT EXISTS idx_users_status ON users (status);

-- Sessions: recent sessions per user (chat sidebar)
CREATE INDEX IF NOT EXISTS idx_sessions_user_created ON sessions (user_id, created_at DESC);

-- Plugins: lookup by kind (connector type filtering)
CREATE INDEX IF NOT EXISTS idx_plugins_kind ON plugins (kind);

-- Connectors: status-based health monitoring
CREATE INDEX IF NOT EXISTS idx_connectors_status ON connectors (status);

-- Permissions: user + action composite (authorization check hot path)
CREATE INDEX IF NOT EXISTS idx_permissions_user_action ON permissions (user_id, action);
