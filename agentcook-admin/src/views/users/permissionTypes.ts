/**
 * Day 30 — Permission domain types for admin UI.
 *
 * Java Domain has Permission aggregate (5 aggregates: User / Session /
 * Plugin / Connector / Permission). java-v1.yaml does NOT yet declare
 * PermissionResponse schema (PermissionController missing — Day 29 #1 +
 * Day 30 #1 reverse fact-checks to D). We vendor the shape locally and
 * replace with `components["schemas"]["PermissionResponse"]` once D ships
 * the controller and re-exports the spec.
 *
 * Coordinator note (Day 30 brief §代决 1): "Role" concept does NOT exist
 * as its own aggregate. We render Permissions grouped by User instead —
 * cheaper than introducing a Role aggregate that would need a new ADR.
 */

export type PermissionEffect = "ALLOW" | "DENY";

export interface PermissionDto {
  id: string;
  resource: string;
  action: string;
  effect: PermissionEffect;
  userId?: string;
  createdAt?: string;
}

/** Group permissions by (resource, action) so the UI can render a matrix. */
export interface PermissionMatrix {
  resources: string[];
  actions: string[];
  /** Map of `${resource}#${action}` → effect (or undefined when unset). */
  cells: Map<string, PermissionEffect>;
}

export function buildMatrix(permissions: PermissionDto[]): PermissionMatrix {
  const resources = Array.from(new Set(permissions.map((p) => p.resource))).sort();
  const actions = Array.from(new Set(permissions.map((p) => p.action))).sort();
  const cells = new Map<string, PermissionEffect>();
  for (const p of permissions) {
    cells.set(`${p.resource}#${p.action}`, p.effect);
  }
  return { resources, actions, cells };
}

export const MOCK_PERMISSION_RESOURCES = [
  "plugin",
  "session",
  "user",
  "connector",
  "memory",
];

export const MOCK_PERMISSION_ACTIONS = ["read", "write", "delete", "admin"];

export function makeMockPermissions(userId: string): PermissionDto[] {
  // Deterministic mock derived from userId so reloads stay stable.
  const seed = userId.split("").reduce((a, c) => a + c.charCodeAt(0), 0);
  const list: PermissionDto[] = [];
  let id = 0;
  for (const resource of MOCK_PERMISSION_RESOURCES) {
    for (const action of MOCK_PERMISSION_ACTIONS) {
      // Skip ~30% so the matrix isn't fully filled
      if ((seed + id) % 7 === 0) {
        id++;
        continue;
      }
      list.push({
        id: `mock-perm-${userId}-${id++}`,
        resource,
        action,
        effect: (seed + id) % 5 === 0 ? "DENY" : "ALLOW",
        userId,
      });
    }
  }
  return list;
}
