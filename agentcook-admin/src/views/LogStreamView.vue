<template>
  <div class="log-stream-view">
    <div class="page-header">
      <h2>Log Stream</h2>
      <div class="header-right">
        <el-tag v-if="dataSource === 'live'" type="success" size="small" effect="plain">
          live · /api/v1/logs/stream
        </el-tag>
        <el-tag v-else type="warning" size="small" effect="plain">
          mock · Python /api/v1/logs/stream unreachable
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
      <el-switch
        v-model="autoScroll"
        active-text="Auto-scroll"
        inline-prompt
        size="small"
      />
      <el-button
        v-if="streaming"
        type="warning"
        size="small"
        :icon="VideoPause"
        @click="pause"
      >
        Pause
      </el-button>
      <el-button v-else type="primary" size="small" :icon="VideoPlay" @click="resume">
        Resume
      </el-button>
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
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from "vue";
import { Search, VideoPause, VideoPlay, Delete } from "@element-plus/icons-vue";
import { useSseStream } from "@/composables/useSseStream";
import {
  LOG_LEVELS,
  LEVEL_COLOR,
  parseLogLine,
  shouldShow,
  makeMockLogStream,
  type LogLevel,
  type LogLine,
} from "./monitoring/logTypes";

const PYTHON_BASE =
  import.meta.env.VITE_PYTHON_API_BASE_URL || "http://localhost:8000";

const viewportRef = ref<HTMLDivElement | null>(null);
const allLines = ref<LogLine[]>([]);
const minLevel = ref<LogLevel>("INFO");
const search = ref("");
const autoScroll = ref(true);
const streaming = ref(false);
const dataSource = ref<"live" | "mock">("mock");

const { accumulated, running, error, start, cancel, reset } = useSseStream();

const visibleLines = computed(() =>
  allLines.value.filter((line) => shouldShow(line, minLevel.value, search.value)),
);

function formatTs(iso: string) {
  try {
    return new Date(iso).toLocaleTimeString("zh-CN", { hour12: false });
  } catch {
    return iso;
  }
}

// Each SSE chunk may contain N newline-separated log lines — re-parse on
// every reactive accumulated update; track the offset we've consumed so we
// don't re-emit existing lines.
let consumedOffset = 0;
watch(accumulated, (raw) => {
  if (!raw) return;
  const next = raw.slice(consumedOffset);
  consumedOffset = raw.length;
  for (const rawLine of next.split("\n")) {
    const parsed = parseLogLine(rawLine);
    if (parsed) allLines.value.push(parsed);
  }
  if (autoScroll.value) {
    nextTick(() => {
      if (viewportRef.value) {
        viewportRef.value.scrollTop = viewportRef.value.scrollHeight;
      }
    });
  }
});

watch(running, (r) => {
  streaming.value = r;
});

async function connect() {
  consumedOffset = 0;
  reset();
  try {
    await start({
      url: `${PYTHON_BASE}/api/v1/logs/stream`,
      heartbeatMs: 60_000,
    });
    dataSource.value = "live";
  } catch {
    dataSource.value = "mock";
    allLines.value = makeMockLogStream();
  }
}

function pause() {
  cancel();
  streaming.value = false;
}

function resume() {
  connect();
}

function clearLog() {
  allLines.value = [];
  consumedOffset = 0;
}

function onScroll() {
  if (!viewportRef.value) return;
  const atBottom =
    viewportRef.value.scrollHeight - viewportRef.value.scrollTop - viewportRef.value.clientHeight <
    20;
  // If user scrolls up manually, disable auto-scroll so we don't fight them.
  if (!atBottom) autoScroll.value = false;
}

onMounted(async () => {
  // First try the real SSE; if backend returns an error within 1s, fall back.
  const probe = setTimeout(() => {
    if (allLines.value.length === 0 && !running.value) {
      dataSource.value = "mock";
      allLines.value = makeMockLogStream();
    }
  }, 1500);
  await connect();
  if (error.value) {
    dataSource.value = "mock";
    if (allLines.value.length === 0) allLines.value = makeMockLogStream();
  }
  clearTimeout(probe);
});

onBeforeUnmount(() => cancel());
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
