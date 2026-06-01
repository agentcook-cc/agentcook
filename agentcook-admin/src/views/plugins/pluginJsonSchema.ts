/**
 * Minimal local copy of agent-plugin-spec v1 plugin.json schema.
 *
 * Long-term we should fetch this from the agent-plugin-spec repo at build
 * time so it stays in sync without manual updates. For Day 27 we vendor a
 * conservative subset that covers the fields the editor surfaces and the
 * checks the user most cares about (required fields + kind enum).
 *
 * Track upstream: https://github.com/agentcook-cc/agent-plugin-spec
 */
export const PLUGIN_JSON_SCHEMA = {
  $schema: "http://json-schema.org/draft-07/schema#",
  type: "object",
  additionalProperties: true,
  required: ["name", "version", "kind"],
  properties: {
    name: {
      type: "string",
      minLength: 1,
      maxLength: 64,
      pattern: "^[a-z][a-z0-9-]*$",
      description: "Lower-kebab-case plugin identifier.",
    },
    version: {
      type: "string",
      pattern: "^\\d+\\.\\d+\\.\\d+(-[A-Za-z0-9.-]+)?$",
      description: "SemVer 2.0.0 version.",
    },
    kind: {
      type: "string",
      enum: ["MCP", "HTTP", "OAUTH", "WEBHOOK"],
    },
    description: { type: "string", maxLength: 280 },
    homepage: { type: "string", format: "uri" },
    license: { type: "string" },
    author: { type: "string" },
    entry: {
      type: "object",
      description: "How the runtime invokes this plugin.",
      properties: {
        command: { type: "string" },
        args: { type: "array", items: { type: "string" } },
        env: { type: "object", additionalProperties: { type: "string" } },
      },
    },
    permissions: {
      type: "array",
      items: { type: "string", pattern: "^[a-z][a-z0-9_.]*:[a-z][a-z0-9_]*$" },
      description: "Permission scopes the plugin will request.",
    },
  },
} as const;
