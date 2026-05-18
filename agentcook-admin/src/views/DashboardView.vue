<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useAuthStore } from "@/stores/auth";
import { Line, Doughnut } from "vue-chartjs";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from "chart.js";

ChartJS.register(
  CategoryScale, LinearScale, PointElement, LineElement,
  ArcElement, Title, Tooltip, Legend, Filler,
);

const authStore = useAuthStore();

interface DashboardStats {
  agents: number;
  skills: number;
  plugins: number;
  sessions: number;
}

const stats = ref<DashboardStats>({ agents: 0, skills: 0, plugins: 0, sessions: 0 });
const loading = ref(true);
const fetchError = ref("");
const useMock = ref(false);

const MOCK_STATS: DashboardStats = { agents: 3, skills: 12, plugins: 7, sessions: 24 };

const MOCK_SESSION_TREND = [5, 8, 12, 9, 15, 20, 24];
const TREND_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

async function fetchStats() {
  loading.value = true;
  fetchError.value = "";
  try {
    const token = authStore.accessToken;
    const headers: Record<string, string> = token
      ? { Authorization: `Bearer ${token}` }
      : {};

    const [agentsRes, skillsRes, pluginsRes, sessionsRes] = await Promise.allSettled([
      fetch("/api/v1/agent", { headers }),
      fetch("/api/v1/skills", { headers }),
      fetch("/api/v1/plugins", { headers }),
      fetch("/api/v1/sessions", { headers }),
    ]);

    const allFailed = [agentsRes, skillsRes, pluginsRes, sessionsRes]
      .every((r) => r.status === "rejected" || (r.status === "fulfilled" && !r.value.ok));

    if (allFailed) {
      useMock.value = true;
      stats.value = MOCK_STATS;
      return;
    }

    stats.value = {
      agents: agentsRes.status === "fulfilled" && agentsRes.value.ok
        ? (await agentsRes.value.json()).length ?? 0 : 0,
      skills: skillsRes.status === "fulfilled" && skillsRes.value.ok
        ? (await skillsRes.value.json()).length ?? 0 : 0,
      plugins: pluginsRes.status === "fulfilled" && pluginsRes.value.ok
        ? (await pluginsRes.value.json()).length ?? 0 : 0,
      sessions: sessionsRes.status === "fulfilled" && sessionsRes.value.ok
        ? (await sessionsRes.value.json()).length ?? 0 : 0,
    };
  } catch (error) {
    useMock.value = true;
    stats.value = MOCK_STATS;
    fetchError.value = error instanceof Error ? error.message : "Failed to load stats";
  } finally {
    loading.value = false;
  }
}

const sessionTrendData = computed(() => ({
  labels: TREND_LABELS,
  datasets: [{
    label: "Sessions",
    data: MOCK_SESSION_TREND,
    borderColor: "#3b82f6",
    backgroundColor: "rgba(59, 130, 246, 0.1)",
    fill: true,
    tension: 0.3,
    pointRadius: 4,
    pointBackgroundColor: "#3b82f6",
  }],
}));

const sessionTrendOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: {
    y: { beginAtZero: true, ticks: { stepSize: 5 } },
  },
};

const resourceDistData = computed(() => ({
  labels: ["Agents", "Skills", "Plugins"],
  datasets: [{
    data: [stats.value.agents, stats.value.skills, stats.value.plugins],
    backgroundColor: ["#3b82f6", "#10b981", "#f59e0b"],
    borderWidth: 0,
  }],
}));

const resourceDistOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { position: "bottom" as const } },
};

const statCards = computed(() => [
  { label: "Agents", value: stats.value.agents, color: "#3b82f6" },
  { label: "Skills", value: stats.value.skills, color: "#10b981" },
  { label: "Plugins", value: stats.value.plugins, color: "#f59e0b" },
  { label: "Sessions", value: stats.value.sessions, color: "#8b5cf6" },
]);

onMounted(fetchStats);
</script>

<template>
  <div class="dashboard">
    <h2>Dashboard</h2>
    <p>Welcome back, {{ authStore.user?.displayName ?? "Admin" }}.</p>

    <el-alert
      v-if="useMock"
      title="Backend unavailable — showing mock data"
      type="info"
      show-icon
      :closable="false"
      style="margin-top: 16px"
    />
    <el-alert
      v-if="fetchError && !useMock"
      :title="fetchError"
      type="warning"
      show-icon
      closable
      style="margin-top: 16px"
    />

    <el-row :gutter="16" style="margin-top: 24px">
      <el-col v-for="card in statCards" :key="card.label" :span="6">
        <el-card shadow="hover">
          <template #header>{{ card.label }}</template>
          <div v-if="loading" class="stat-number">
            <el-skeleton :rows="0" animated style="width: 60px; margin: 0 auto" />
          </div>
          <div v-else class="stat-number" :style="{ color: card.color }">
            {{ card.value }}
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top: 24px">
      <el-col :span="16">
        <el-card shadow="hover">
          <template #header>Session Trend (7 days)</template>
          <div class="chart-container">
            <Line :data="sessionTrendData" :options="sessionTrendOptions" />
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header>Resource Distribution</template>
          <div class="chart-container">
            <Doughnut :data="resourceDistData" :options="resourceDistOptions" />
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.dashboard {
  padding: 8px;
}
.stat-number {
  font-size: 28px;
  font-weight: 700;
  text-align: center;
  padding: 12px 0;
}
.chart-container {
  height: 260px;
  position: relative;
}
</style>
