<template>
  <div class="skill-list-view">
    <div class="page-header">
      <h2>Skill Library</h2>
      <div class="header-right">
        <el-tag v-if="dataSource === 'error'" type="danger" size="small" effect="plain">
          Python /api/v1/skills unreachable
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
      <el-select v-model="categoryFilter" placeholder="Category" clearable style="width: 150px; margin-left: 12px">
        <el-option v-for="c in categories" :key="c" :label="c" :value="c" />
      </el-select>
    </div>

    <el-alert
      v-if="dataSource === 'error'"
      type="error"
      show-icon
      :closable="false"
      style="margin-top: 16px"
      title="Could not load skills from the agent runtime. Check that the Python service is running, then Reload."
    />

    <el-skeleton v-if="loading" :rows="6" animated style="margin-top: 16px" />

    <div v-else class="skill-grid">
      <el-card v-for="skill in filteredSkills" :key="skill.id" shadow="hover" class="skill-card">
        <template #header>
          <div class="card-header">
            <span class="card-title">{{ skill.name }}</span>
            <el-tag size="small" type="info" effect="plain">{{ skill.category }}</el-tag>
          </div>
        </template>
        <p class="card-description">{{ skill.description }}</p>
        <div class="card-meta">
          <span class="meta-item">v{{ skill.version }}</span>
          <span class="meta-item">{{ skill.id }}</span>
          <span v-if="skill.updated_at" class="meta-item">{{ skill.updated_at.slice(0, 10) }}</span>
        </div>
        <div class="card-actions">
          <el-button link type="primary" size="small" @click="openDetail(skill)"> Detail </el-button>
          <el-button link type="success" size="small" @click="openTest(skill)"> Test </el-button>
        </div>
      </el-card>

      <el-empty
        v-if="filteredSkills.length === 0"
        description="No skills match your filter"
        style="grid-column: 1 / -1"
      />
    </div>

    <SkillDetailDrawer v-model="detailOpen" :skill-id="activeSkill?.id" :fallback="activeSkill ?? undefined" />
    <SkillTestDialog v-model="testOpen" :skill-id="activeSkill?.id" :skill-name="activeSkill?.name" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { Search, Refresh } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import { pythonClient } from "@/api/client";
import type { SkillListResponse, SkillManifest } from "./skills/skillTypes";
import SkillDetailDrawer from "./skills/SkillDetailDrawer.vue";
import SkillTestDialog from "./skills/SkillTestDialog.vue";

const PYTHON_BASE = import.meta.env.VITE_PYTHON_API_BASE_URL || "http://localhost:8000";

const skills = ref<SkillManifest[]>([]);
const loading = ref(false);
const dataSource = ref<"live" | "error" | "loading">("loading");
const searchQuery = ref("");
const categoryFilter = ref("");
const detailOpen = ref(false);
const testOpen = ref(false);
const activeSkill = ref<SkillManifest | null>(null);

const categories = computed(() => [...new Set(skills.value.map((s) => s.category))].sort());

const filteredSkills = computed(() => {
  let result = skills.value;
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase();
    result = result.filter(
      (s) =>
        s.name.toLowerCase().includes(q) || s.id.toLowerCase().includes(q) || s.description.toLowerCase().includes(q),
    );
  }
  if (categoryFilter.value) {
    result = result.filter((s) => s.category === categoryFilter.value);
  }
  return result;
});

async function loadSkills() {
  loading.value = true;
  try {
    const data = await pythonClient.get<SkillListResponse>("/api/v1/skills");
    skills.value = data.items ?? [];
    dataSource.value = "live";
    if (skills.value.length === 0) {
      ElMessage.info("The runtime has no skills registered");
    }
  } catch {
    skills.value = [];
    dataSource.value = "error";
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
