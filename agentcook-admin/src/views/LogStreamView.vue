<template>
  <div class="log-stream-view">
    <div class="page-header">
      <h2>Log Stream</h2>
      <div class="header-right">
        <el-tag v-if="dataSource === 'live'" type="success" size="small" effect="plain">
          live · /api/v1/logs/stream
        </el-tag>
        <el-tag v-else-if="dataSource === 'error'" type="danger" size="small" effect="plain">
          {{ connectionError || "runtime unreachable" }}
        </el-tag>
        <span class="counter">{{ visibleLines.length }}/{{ allLines.length }} lines</span>
      </div>
    </div>

    <div class="control-bar">
      <el-select v-model="minLevel" size="small" style="width: 140px">
        <el-option v-for="lv in LOG_LEVELS" :key="lv" :label="`≥ ${lv}`" :value="lv" />
      </el-select>
      <el-input
        v-model="search"
        placeholder="Search message..."
        clearable
        :prefix-icon="Search"
        size="small"
        style="width: 280px"
      />
      <el-switch v-model="autoScroll" active-text="Auto-scroll" inline-prompt size="small" />
      <el-button v-if="streaming" type="warning" size="small" :icon="VideoPause" @click="pause"> Pause </el-button>
      <el-button v-else type="primary" size="small" :icon="VideoPlay" @click="resume"> Resume </el-button>
      <el-button size="small" :icon="Delete" @click="clearLog">Clear</el-button>
    </div>

    <div ref="viewportRef" class="log-viewport" @scroll="onScroll">
      <div
        v-for="(line, idx) in visibleLines"
        :key="idx"
        class="log-line"
        :style="{ borderLeftColor: LEVEL_COLOR[line.level] }"
      >
        <span class="log-ts">{{ formatTs(line.ts) }}</span>
        <span class="log-level" :style="{ color: LEVEL_COLOR[line.level] }">
          {{ line.level }}
        </span>
        <span v-if="line.module" class="log-module">{{ line.module }}</span>
        <span class="log-msg">{{ line.message }}</span>
      </div>
      <el-empty v-if="visibleLines.length === 0" description="No matching log lines" :image-size="60" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from "vue";
import { Search, VideoPause, VideoPlay, Delete } from "@element-plus/icons-vue";
import { useAuthStore } from "@/stores/auth";
import {
  LOG_LEVELS,
  LEVEL_COLOR,
  fromLogFrame,
  shouldShow,
  type LogLevel,
  type LogLine,
  type RuntimeLogFrame,
} from "./monitoring/logTypes";

/**
 * Live tail of the runtime's log hub (`?follow=true`): replays recent
 * history, then streams new lines as they happen. fetch() is used instead
 * of EventSource so the Authorization header can be sent.
 */
const PYTHON_BASE = import.meta.env.VITE_PYTHON_API_BASE_URL || "";
const MAX_LINES = 2_000;

const viewportRef = ref<HTMLDivElement | null>(null);
const allLines = ref<LogLine[]>([]);
const minLevel = ref<LogLevel>("INFO");
const search = ref("");
const autoScroll = ref(true);
const streaming = ref(false);
const dataSource = ref<"live" | "error" | "connecting">("connecting");
const connectionError = ref("");
let controller: AbortController | null = null;

const visibleLines = computed(() => allLines.value.filter((line) => shouldShow(line, minLevel.value, search.value)));

function formatTs(iso: string) {
  try {
    return new Date(iso).toLocaleTimeString("zh-CN", { hour12: false });
  } catch {
    return iso;
  }
}

function append(line: LogLine) {
  allLines.value.push(line);
  if (allLines.value.length > MAX_LINES) allLines.value.splice(0, allLines.value.length - MAX_LINES);
  if (autoScroll.value) {
    nextTick(() => {
      if (viewportRef.value) viewportRef.value.scrollTop = viewportRef.value.scrollHeight;
    });
  }
}

async function connect() {
  controller?.abort();
  controller = new AbortController();
  streaming.value = true;
  dataSource.value = "connecting";
  connectionError.value = "";
  try {
    const token = useAuthStore().accessToken;
    const response = await fetch(`${PYTHON_BASE}/api/v1/logs/stream?follow=true&history=200`, {
      headers: { Accept: "text/event-stream", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      signal: controller.signal,
    });
    if (!response.ok || !response.body) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.message || `HTTP ${response.status}`);
    }
    dataSource.value = "live";
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n?/g, "\n");
      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        const block = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        for (const line of block.split("\n")) {
          if (!line.startsWith("data:")) continue;
          try {
            append(fromLogFrame(JSON.parse(line.slice(5).trim()) as RuntimeLogFrame));
          } catch {
            // not a log frame — ignore
          }
        }
        boundary = buffer.indexOf("\n\n");
      }
    }
  } catch (err) {
    if (controller?.signal.aborted) return;
    dataSource.value = "error";
    connectionError.value = err instanceof Error ? err.message : "connection failed";
  } finally {
    streaming.value = false;
  }
}

function pause() {
  controller?.abort();
  streaming.value = false;
}

function resume() {
  void connect();
}

function clearLog() {
  allLines.value = [];
}

function onScroll() {
  if (!viewportRef.value) return;
  const el = viewportRef.value;
  // Scrolling up pauses auto-scroll so we don't fight the reader.
  autoScroll.value = el.scrollHeight - el.scrollTop - el.clientHeight < 20;
}

onMounted(() => void connect());
onBeforeUnmount(() => controller?.abort());
</script>

<style scoped>
.log-stream-view {
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
  margin-bottom: 12px;
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
.counter {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  font-family: "JetBrains Mono", monospace;
}
.control-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  padding: 8px 0;
}
.log-viewport {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  background: var(--el-fill-color-lighter);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  padding: 8px;
}
.log-line {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 2px 8px;
  border-left: 3px solid transparent;
  font-family: "JetBrains Mono", monospace;
  font-size: 12px;
  line-height: 1.5;
}
.log-line:hover {
  background: white;
}
.log-ts {
  color: var(--el-text-color-secondary);
  flex-shrink: 0;
}
.log-level {
  font-weight: 700;
  flex-shrink: 0;
  width: 60px;
}
.log-module {
  color: var(--el-text-color-secondary);
  flex-shrink: 0;
}
.log-msg {
  color: var(--el-text-color-primary);
  word-break: break-word;
}
</style>
