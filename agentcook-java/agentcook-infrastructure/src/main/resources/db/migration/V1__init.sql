-- agentcook-java V1 init schema
-- Five business aggregates: User / Session / Plugin / Connector / Permission
-- Aligned field-by-field with the domain model (cc.agentcook.domain.*)

CREATE TABLE users (
    id          UUID         PRIMARY KEY,
    email       VARCHAR(255) NOT NULL,
    nickname    VARCHAR(255),
    status      VARCHAR(32)  NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL,
    updated_at  TIMESTAMPTZ  NOT NULL,
    CONSTRAINT uk_users_email UNIQUE (email)
);

CREATE TABLE sessions (
    id          UUID         PRIMARY KEY,
    user_id     UUID         NOT NULL,
    title       VARCHAR(255),
    status      VARCHAR(32)  NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL,
    updated_at  TIMESTAMPTZ  NOT NULL,
    CONSTRAINT fk_sessions_user_id FOREIGN KEY (user_id) REFERENCES users (id)
);
CREATE INDEX idx_sessions_user_id ON sessions (user_id);

CREATE TABLE plugins (
    id          UUID         PRIMARY KEY,
    name        VARCHAR(255) NOT NULL,
    version     VARCHAR(64)  NOT NULL,
    kind        VARCHAR(32)  NOT NULL,
    description TEXT,
    status      VARCHAR(32)  NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL,
    updated_at  TIMESTAMPTZ  NOT NULL,
    CONSTRAINT uk_plugins_name_version UNIQUE (name, version)
);
CREATE INDEX idx_plugins_status ON plugins (status);

CREATE TABLE connectors (
    id                 UUID         PRIMARY KEY,
    plugin_id          UUID         NOT NULL,
    kind               VARCHAR(32)  NOT NULL,
    config             TEXT,
    status             VARCHAR(32)  NOT NULL,
    last_health_check  TIMESTAMPTZ,
    created_at         TIMESTAMPTZ  NOT NULL,
    updated_at         TIMESTAMPTZ  NOT NULL,
    CONSTRAINT fk_connectors_plugin_id FOREIGN KEY (plugin_id) REFERENCES plugins (id)
);
CREATE INDEX idx_connectors_plugin_id ON connectors (plugin_id);

CREATE TABLE permissions (
    id          UUID         PRIMARY KEY,
    user_id     UUID         NOT NULL,
    resource    VARCHAR(255) NOT NULL,
    action      VARCHAR(64)  NOT NULL,
    effect      VARCHAR(16)  NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL,
    CONSTRAINT fk_permissions_user_id FOREIGN KEY (user_id) REFERENCES users (id)
);
CREATE INDEX idx_permissions_user_resource ON permissions (user_id, resource);
