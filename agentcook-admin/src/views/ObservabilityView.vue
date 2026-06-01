<template>
  <div class="observability-view">
    <div class="page-header">
      <h2>Observability</h2>
      <div class="header-right">
        <el-tag size="small" type="info" effect="plain">
          embedded · refreshed live
        </el-tag>
        <el-button :icon="Refresh" link @click="reloadIframe">Reload</el-button>
        <el-button :icon="TopRight" link tag="a" :href="activeUrl" target="_blank">
          Open in new tab
        </el-button>
      </div>
    </div>

    <p class="hint">
      Tabs embed the local Jaeger / Prometheus UIs. URLs are configurable via
      <code>VITE_JAEGER_URL</code> / <code>VITE_PROMETHEUS_URL</code> (Phase 4
      will point at staging/prod subdomains).
    </p>

    <el-tabs v-model="activeTab" type="card" class="obs-tabs" @tab-change="onTabChange">
      <el-tab-pane label="Traces · Jaeger" name="traces">
        <iframe
          :key="`jaeger-${reloadCounter}`"
          :src="JAEGER_URL"
          class="obs-iframe"
          title="Jaeger UI"
          @load="markLoaded('traces')"
          @error="markError('traces')"
        />
        <el-empty
          v-if="status.traces === 'error'"
          :description="`Cannot reach ${JAEGER_URL} — start docker-compose first.`"
          :image-size="60"
          class="iframe-fallback"
        />
      </el-tab-pane>
      <el-tab-pane label="Metrics · Prometheus" name="metrics">
        <iframe
          :key="`prom-${reloadCounter}`"
          :src="PROMETHEUS_URL"
          class="obs-iframe"
          title="Prometheus UI"
          @load="markLoaded('metrics')"
          @error="markError('metrics')"
        />
        <el-empty
          v-if="status.metrics === 'error'"
          :description="`Cannot reach ${PROMETHEUS_URL} — start docker-compose first.`"
          :image-size="60"
          class="iframe-fallback"
        />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from "vue";
import { Refresh, TopRight } from "@element-plus/icons-vue";

type Tab = "traces" | "metrics";
type LoadState = "loading" | "loaded" | "error";

const JAEGER_URL =
  import.meta.env.VITE_JAEGER_URL || "http://localhost:16686/";
const PROMETHEUS_URL =
  import.meta.env.VITE_PROMETHEUS_URL || "http://localhost:9090/";

const activeTab = ref<Tab>("traces");
const reloadCounter = ref(0);
const status = ref<Record<Tab, LoadState>>({ traces: "loading", metrics: "loading" });

const activeUrl = computed(() => (activeTab.value === "traces" ? JAEGER_URL : PROMETHEUS_URL));

function reloadIframe() {
  status.value[activeTab.value] = "loading";
  reloadCounter.value += 1;
}

function markLoaded(tab: Tab) {
  status.value[tab] = "loaded";
}

function markError(tab: Tab) {
  status.value[tab] = "error";
}

function onTabChange() {
  // No-op for now; future Phase 5 could lazy-mount iframes for perf.
}
</script>

<style scoped>
.observability-view {
  padding: 24px;
  display: flex;
  flex-direction: column;
  height: calc(100vh - 0px);
  box-sizing: border-box;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.page-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.hint {
  margin: 0 0 12px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.hint code {
  background: var(--el-fill-color-light);
  padding: 1px 4px;
  border-radius: 3px;
  font-family: "JetBrains Mono", monospace;
  font-size: 11px;
}
.obs-tabs {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.obs-tabs :deep(.el-tabs__content) {
  flex: 1;
  min-height: 0;
}
.obs-tabs :deep(.el-tab-pane) {
  height: 100%;
}
.obs-iframe {
  width: 100%;
  height: 100%;
  min-height: 540px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  background: white;
}
.iframe-fallback {
  margin-top: 12px;
}
</style>
