<template>
  <div class="skill-list-view">
    <div class="page-header">
      <h2>Skill Library</h2>
      <div class="header-right">
        <el-tag v-if="dataSource === 'mock'" type="warning" size="small" effect="plain">
          mock fallback (Python /api/v1/skills unreachable)
        </el-tag>
        <el-tag v-else-if="dataSource === 'live'" type="success" size="small" effect="plain">
          live · {{ PYTHON_BASE }}
        </el-tag>
        <el-button :icon="Refresh" link @click="loadSkills">Reload</el-button>
      </div>
    </div>

    <div class="search-bar">
      <el-input
        v-model="searchQuery"
        placeholder="Search by name or description..."
        clearable
        :prefix-icon="Search"
        style="width: 360px"
      />
      <el-select
        v-model="kindFilter"
        placeholder="Kind"
        clearable
        style="width: 150px; margin-left: 12px"
      >
        <el-option v-for="k in KINDS" :key="k" :label="k" :value="k" />
      </el-select>
    </div>

    <el-skeleton v-if="loading" :rows="6" animated style="margin-top: 16px" />

    <div v-else class="skill-grid">
      <el-card
        v-for="skill in filteredSkills"
        :key="skill.id"
        shadow="hover"
        class="skill-card"
      >
        <template #header>
          <div class="card-header">
            <span class="card-title">{{ skill.name }}</span>
            <el-tag size="small" type="info" effect="plain">{{ skill.kind }}</el-tag>
          </div>
        </template>
        <p class="card-description">{{ skill.description }}</p>
        <div class="card-meta">
          <span class="meta-item">v{{ skill.version }}</span>
          <span class="meta-item">{{ skill.category }}</span>
          <span v-if="skill.author" class="meta-item">@{{ skill.author }}</span>
        </div>
        <div class="card-actions">
          <el-button link type="primary" size="small" @click="openDetail(skill)">
            Detail
          </el-button>
          <el-button link type="success" size="small" @click="openTest(skill)">
            Test
          </el-button>
        </div>
      </el-card>

      <el-empty
        v-if="filteredSkills.length === 0"
        description="No skills match your filter"
        style="grid-column: 1 / -1"
      />
    </div>

    <SkillDetailDrawer
      v-model="detailOpen"
      :skill-id="activeSkill?.id"
      :fallback="activeSkill ?? undefined"
    />
    <SkillTestDialog
      v-model="testOpen"
      :skill-id="activeSkill?.id"
      :skill-name="activeSkill?.name"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { Search, Refresh } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import { pythonClient } from "@/api/client";
import type { SkillManifest, SkillKind } from "./skills/skillTypes";
import SkillDetailDrawer from "./skills/SkillDetailDrawer.vue";
import SkillTestDialog from "./skills/SkillTestDialog.vue";

const KINDS: SkillKind[] = ["ROUTINE", "SEARCH", "TOOL", "PLANNER", "CUSTOM"];

const PYTHON_BASE =
  import.meta.env.VITE_PYTHON_API_BASE_URL || "http://localhost:8000";

const skills = ref<SkillManifest[]>([]);
const loading = ref(false);
const dataSource = ref<"live" | "mock" | "loading">("loading");
const searchQuery = ref("");
const kindFilter = ref<SkillKind | "">("");
const detailOpen = ref(false);
const testOpen = ref(false);
const activeSkill = ref<SkillManifest | null>(null);

const MOCK_SKILLS: SkillManifest[] = [
  { id: "s1", name: "search-web", version: "1.0.0", kind: "SEARCH", category: "Web", description: "Search the public web and return cited snippets.", author: "agentcook", tags: ["web", "search"] },
  { id: "s2", name: "summarise", version: "1.2.0", kind: "ROUTINE", category: "Text", description: "Summarise a long document into 3 bullet points.", author: "agentcook", tags: ["text"] },
  { id: "s3", name: "code-search", version: "0.9.0", kind: "SEARCH", category: "Code", description: "Search a code repository with semantic matching.", author: "agentcook", tags: ["code"] },
  { id: "s4", name: "translate", version: "2.0.0", kind: "TOOL", category: "Text", description: "Translate text between supported language pairs.", author: "agentcook", tags: ["i18n"] },
  { id: "s5", name: "calendar-find", version: "1.0.1", kind: "TOOL", category: "Productivity", description: "Find a free meeting slot across multiple calendars.", author: "agentcook", tags: ["calendar"] },
  { id: "s6", name: "plan-task", version: "0.4.0", kind: "PLANNER", category: "Workflow", description: "Decompose a high-level goal into ordered subtasks.", author: "agentcook", tags: ["planner"] },
  { id: "s7", name: "fetch-url", version: "1.0.0", kind: "TOOL", category: "Web", description: "Fetch a URL and return cleaned-up text content.", author: "agentcook", tags: ["web"] },
  { id: "s8", name: "git-blame", version: "0.5.0", kind: "TOOL", category: "Code", description: "Run git blame on a file path and return author lines.", author: "agentcook", tags: ["code", "git"] },
];

const filteredSkills = computed(() => {
  let result = skills.value;
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase();
    result = result.filter(
      (s) =>
        s.name.toLowerCase().includes(q) ||
        s.description.toLowerCase().includes(q),
    );
  }
  if (kindFilter.value) {
    result = result.filter((s) => s.kind === kindFilter.value);
  }
  return result;
});

async function loadSkills() {
  loading.value = true;
  try {
    const data = await pythonClient.get<SkillManifest[]>("/api/v1/skills");
    skills.value = Array.isArray(data) ? data : [];
    dataSource.value = "live";
    if (skills.value.length === 0) {
      ElMessage.info("Python backend returned 0 skills");
    }
  } catch {
    skills.value = MOCK_SKILLS;
    dataSource.value = "mock";
  } finally {
    loading.value = false;
  }
}

function openDetail(skill: SkillManifest) {
  activeSkill.value = skill;
  detailOpen.value = true;
}

function openTest(skill: SkillManifest) {
  activeSkill.value = skill;
  testOpen.value = true;
}

onMounted(loadSkills);
</script>

<style scoped>
.skill-list-view {
  padding: 24px;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.page-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.search-bar {
  display: flex;
  align-items: center;
  margin-bottom: 16px;
}
.skill-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
  margin-top: 16px;
}
.skill-card {
  display: flex;
  flex-direction: column;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.card-title {
  font-weight: 600;
  font-size: 14px;
  color: var(--el-text-color-primary);
  font-family: "JetBrains Mono", monospace;
}
.card-description {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
  line-height: 1.5;
  min-height: 40px;
}
.card-meta {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  font-size: 11px;
  color: var(--el-text-color-secondary);
}
.meta-item {
  padding: 2px 6px;
  background: var(--el-fill-color-light);
  border-radius: 3px;
}
.card-actions {
  display: flex;
  gap: 8px;
  border-top: 1px solid var(--el-border-color-lighter);
  padding-top: 8px;
  margin-top: auto;
}
</style>
