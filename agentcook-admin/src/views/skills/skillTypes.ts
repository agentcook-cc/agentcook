/**
 * Skill DTOs — mirror `SkillSummary` / `SkillDetailResponse` in the
 * Python runtime spec (docs/api/v1.yaml).
 */
export interface SkillManifest {
  id: string;
  name: string;
  version: string;
  category: string;
  description: string;
  updated_at?: string;
  body?: string;
}

export interface SkillListResponse {
  items: SkillManifest[];
  total: number;
}
