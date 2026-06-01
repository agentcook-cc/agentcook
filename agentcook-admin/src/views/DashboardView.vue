<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useAuthStore } from "@/stores/auth";
import { javaClient, pythonClient } from "@/api/client";
import type { components as JavaComponents } from "@/api/types.java.gen";
import VChart from "vue-echarts";
import { use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { LineChart, PieChart } from "echarts/charts";
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
} from "echarts/components";
import type { ComposeOption } from "echarts/core";
import type { LineSeriesOption } from "echarts/charts";
import type { PieSeriesOption } from "echarts/charts";
import type {
  TitleComponentOption,
  TooltipComponentOption,
  LegendComponentOption,
  GridComponentOption,
} from "echarts/components";

use([CanvasRenderer, LineChart, PieChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent]);

type LineEChartsOption = ComposeOption<LineSeriesOption | TitleComponentOption | TooltipComponentOption | GridComponentOption>;
type PieEChartsOption = ComposeOption<PieSeriesOption | TitleComponentOption | TooltipComponentOption | LegendComponentOption>;

const authStore = useAuthStore();

interface DashboardStats {
  users: number;
  agents: number;
  plugins: number;
  sessions: number;
}

const stats = ref<DashboardStats>({ users: 0, agents: 0, plugins: 0, sessions: 0 });
const loading = ref(true);
const fetchError = ref("");
const useMock = ref(false);
const failedCards = ref<string[]>([]);

const MOCK_STATS: DashboardStats = { users: 8, agents: 3, plugins: 8, sessions: 24 };

type UserDto = JavaComponents["schemas"]["UserResponse"];
type PluginDto = JavaComponents["schemas"]["PluginResponse"];
type SessionDto = JavaComponents["schemas"]["SessionResponse"];

const MOCK_SESSION_TREND = [5, 8, 12, 9, 15, 20, 24];
const TREND_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

/**
 * Day 25 design-tokens consistency: read token values at runtime instead of
 * hard-coding hex strings, so the chart palette tracks `agentcook-design-tokens`
 * (e.g. dark-mode swap or brand re-skin propagates without touching this view).
 */
function tokenColor(name: string, fallback: string): string {
  if (typeof window === "undefined") return fallback;
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}
const PALETTE = {
  primary: tokenColor("--color-primary-500", "#3b82f6"),
  primaryAlpha: "rgba(59, 130, 246, 0.1)", // computed alpha derived from primary-500; rgba helper not needed at MVP
  success: tokenColor("--color-success-500", "#22c55e"),
  warning: tokenColor("--color-warning-500", "#f59e0b"),
  secondary: tokenColor("--color-secondary-500", "#8b5cf6"),
};

/**
 * Day 26: typed Promise.allSettled — each card resolves independently. A
 * failing endpoint shows mock for that card and is listed in failedCards so
 * the user knows it's not real data. All four failing falls back to MOCK_STATS.
 *
 * Mapping:
 * - Users   → Java GET /api/v1/users (array length)
 * - Agents  → Python GET /api/v1/agents (array length; A endpoint pending — falls back if 404)
 * - Plugins → Java GET /api/v1/plugins (array length)
 * - Sessions → Java GET /api/v1/sessions (array length)
 */
async function fetchStats() {
  loading.value = true;
  fetchError.value = "";
  failedCards.value = [];

  const [usersRes, agentsRes, pluginsRes, sessionsRes] = await Promise.allSettled([
    javaClient.get<UserDto[]>("/api/v1/users"),
    pythonClient.get<unknown[]>("/api/v1/agents"),
    javaClient.get<PluginDto[]>("/api/v1/plugins"),
    javaClient.get<SessionDto[]>("/api/v1/sessions"),
  ]);

  function countOrMark(
    res: PromiseSettledResult<unknown[]>,
    cardName: keyof DashboardStats,
  ): number {
    if (res.status === "fulfilled" && Array.isArray(res.value)) {
      return res.value.length;
    }
    failedCards.value.push(cardName);
    return MOCK_STATS[cardName];
  }

  stats.value = {
    users: countOrMark(usersRes, "users"),
    agents: countOrMark(agentsRes, "agents"),
    plugins: countOrMark(pluginsRes, "plugins"),
    sessions: countOrMark(sessionsRes, "sessions"),
  };

  if (failedCards.value.length === 4) {
    useMock.value = true;
    fetchError.value = "All backends unreachable — showing mock data";
  } else if (failedCards.value.length > 0) {
    fetchError.value = `Backend partial: ${failedCards.value.join(", ")} fell back to mock`;
  }

  loading.value = false;
}

const requestTrendOption = computed<LineEChartsOption>(() => ({
  tooltip: { trigger: "axis" },
  grid: { left: 40, right: 16, top: 16, bottom: 30 },
  xAxis: { type: "category", data: TREND_LABELS, boundaryGap: false },
  yAxis: { type: "value", min: 0, splitNumber: 4 },
  series: [
    {
      name: "Requests",
      type: "line",
      data: MOCK_SESSION_TREND,
      smooth: true,
      symbol: "circle",
      symbolSize: 6,
      lineStyle: { color: PALETTE.primary, width: 2 },
      itemStyle: { color: PALETTE.primary },
      areaStyle: { color: PALETTE.primaryAlpha },
    },
  ],
}));

const statusDistOption = computed<PieEChartsOption>(() => ({
  tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
  legend: { bottom: 0, left: "center" },
  series: [
    {
      type: "pie",
      radius: ["40%", "70%"],
      avoidLabelOverlap: true,
      label: { show: false },
      emphasis: { label: { show: true, fontSize: 14, fontWeight: "bold" } },
      data: [
        { value: stats.value.users, name: "Users", itemStyle: { color: PALETTE.primary } },
        { value: stats.value.agents, name: "Agents", itemStyle: { color: PALETTE.success } },
        { value: stats.value.plugins, name: "Plugins", itemStyle: { color: PALETTE.warning } },
      ],
    },
  ],
}));

const statCards = computed(() => [
  { key: "users" as const, label: "Users", value: stats.value.users, color: PALETTE.primary },
  { key: "agents" as const, label: "Agents", value: stats.value.agents, color: PALETTE.success },
  { key: "plugins" as const, label: "Plugins", value: stats.value.plugins, color: PALETTE.warning },
  { key: "sessions" as const, label: "Sessions", value: stats.value.sessions, color: PALETTE.secondary },
]);

function isCardMocked(key: string): boolean {
  return failedCards.value.includes(key);
}

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
      <el-col v-for="card in statCards" :key="card.key" :span="6">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>{{ card.label }}</span>
              <el-tag
                v-if="!loading && isCardMocked(card.key)"
                type="warning"
                size="small"
                effect="plain"
              >
                mock
              </el-tag>
            </div>
          </template>
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
          <template #header>Request Trend (7 days)</template>
          <div class="chart-container">
            <VChart :option="requestTrendOption" autoresize />
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header>Status Distribution</template>
          <div class="chart-container">
            <VChart :option="statusDistOption" autoresize />
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
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
