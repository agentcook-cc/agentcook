import { describe, it, expect } from "vitest";
import Ajv from "ajv";
import { PLUGIN_JSON_SCHEMA } from "@/views/plugins/pluginJsonSchema";

const ajv = new Ajv({ allErrors: true, strict: false });
const validate = ajv.compile(PLUGIN_JSON_SCHEMA);

describe("plugin.json schema · Day 27 ajv live validation", () => {
  it("accepts a minimal valid plugin.json", () => {
    const ok = validate({ name: "github-connector", version: "1.0.0", kind: "HTTP" });
    expect(ok).toBe(true);
    expect(validate.errors).toBeNull();
  });

  it("rejects missing required field (kind)", () => {
    const ok = validate({ name: "broken", version: "1.0.0" });
    expect(ok).toBe(false);
    expect(validate.errors?.some((e) => e.message?.includes("'kind'"))).toBe(true);
  });

  it("rejects upper-case name (must be lower-kebab)", () => {
    const ok = validate({ name: "GitHubConnector", version: "1.0.0", kind: "HTTP" });
    expect(ok).toBe(false);
    expect(validate.errors?.some((e) => e.instancePath === "/name")).toBe(true);
  });

  it("rejects non-semver version", () => {
    const ok = validate({ name: "x", version: "v1.2", kind: "HTTP" });
    expect(ok).toBe(false);
    expect(validate.errors?.some((e) => e.instancePath === "/version")).toBe(true);
  });

  it("rejects unknown kind enum", () => {
    const ok = validate({ name: "x", version: "1.0.0", kind: "GRPC" });
    expect(ok).toBe(false);
    expect(validate.errors?.some((e) => e.instancePath === "/kind")).toBe(true);
  });

  it("accepts optional fields (description, permissions)", () => {
    const ok = validate({
      name: "rich-plugin",
      version: "1.2.3",
      kind: "MCP",
      description: "A rich plugin",
      permissions: ["fs:read", "net:fetch"],
    });
    expect(ok).toBe(true);
  });

  it("rejects malformed permission scope", () => {
    const ok = validate({
      name: "x",
      version: "1.0.0",
      kind: "HTTP",
      permissions: ["NotKebab"],
    });
    expect(ok).toBe(false);
    expect(validate.errors?.some((e) => e.instancePath?.startsWith("/permissions"))).toBe(true);
  });
});
