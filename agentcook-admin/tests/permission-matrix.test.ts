import { describe, it, expect } from "vitest";
import {
  buildMatrix,
  makeMockPermissions,
  type PermissionDto,
} from "@/views/users/permissionTypes";

describe("permission matrix · Day 30", () => {
  it("groups permissions into unique resource × action axes", () => {
    const perms: PermissionDto[] = [
      { id: "1", resource: "plugin", action: "read", effect: "ALLOW" },
      { id: "2", resource: "plugin", action: "write", effect: "DENY" },
      { id: "3", resource: "user", action: "read", effect: "ALLOW" },
    ];
    const m = buildMatrix(perms);
    expect(m.resources).toEqual(["plugin", "user"]);
    expect(m.actions).toEqual(["read", "write"]);
    expect(m.cells.get("plugin#read")).toBe("ALLOW");
    expect(m.cells.get("plugin#write")).toBe("DENY");
    expect(m.cells.get("user#read")).toBe("ALLOW");
    expect(m.cells.get("user#write")).toBeUndefined();
  });

  it("returns empty axes for empty input", () => {
    const m = buildMatrix([]);
    expect(m.resources).toEqual([]);
    expect(m.actions).toEqual([]);
    expect(m.cells.size).toBe(0);
  });

  it("makeMockPermissions is deterministic per userId", () => {
    const a1 = makeMockPermissions("u1");
    const a2 = makeMockPermissions("u1");
    expect(a1.length).toBe(a2.length);
    expect(a1.map((p) => `${p.resource}#${p.action}#${p.effect}`)).toEqual(
      a2.map((p) => `${p.resource}#${p.action}#${p.effect}`),
    );
  });

  it("different userIds produce different mock matrices", () => {
    const a = makeMockPermissions("u1");
    const b = makeMockPermissions("u9-different");
    // At least the effect distribution should diverge (deterministic seeded)
    const aKey = a.map((p) => p.effect).join("");
    const bKey = b.map((p) => p.effect).join("");
    expect(aKey).not.toBe(bKey);
  });

  it("mock permissions cover the canonical resources × actions surface", () => {
    const perms = makeMockPermissions("alice");
    const resources = new Set(perms.map((p) => p.resource));
    const actions = new Set(perms.map((p) => p.action));
    expect(resources.size).toBeGreaterThanOrEqual(3);
    expect(actions.size).toBeGreaterThanOrEqual(3);
    for (const p of perms) {
      expect(["ALLOW", "DENY"]).toContain(p.effect);
    }
  });
});
