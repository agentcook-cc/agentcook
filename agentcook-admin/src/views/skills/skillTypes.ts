/**
 * Local Skill DTO until A bumps v1.yaml to v1.1.0 and B regenerates
 * `types.python.gen.ts` with `components["schemas"]["SkillResponse"]`.
 *
 * Day 28 reverse fact-check: v1.yaml is still 1.0.0 (no skills paths yet).
 * When A finishes the 5-step bump (wire / version / dump / SSE / CHANGELOG)
 * we run `pnpm gen:api:python` and replace this file with a re-export from
 * the generated module.
 */
export type SkillKind = "ROUTINE" | "SEARCH" | "TOOL" | "PLANNER" | "CUSTOM";

export interface SkillManifest {
  id: string;
  name: string;
  version: string;
  kind: SkillKind;
  category: string;
  description: string;
  author?: string;
  inputs?: Record<string, { type: string; description?: string; required?: boolean }>;
  outputs?: Record<string, { type: string; description?: string }>;
  tags?: string[];
  body?: string;
  createdAt?: string;
  updatedAt?: string;
}
