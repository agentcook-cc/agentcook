<template>
  <el-dialog
    v-model="visible"
    title="Create Plugin"
    width="560px"
    :close-on-click-modal="false"
    @close="reset"
  >
    <el-alert
      v-if="errorMessage"
      :title="errorMessage"
      type="error"
      show-icon
      closable
      style="margin-bottom: 16px"
      @close="errorMessage = ''"
    />

    <el-upload
      ref="uploadRef"
      drag
      action=""
      :auto-upload="false"
      :limit="1"
      accept=".zip"
      :on-change="handleFileChange"
      :on-exceed="handleExceed"
      :file-list="fileList"
    >
      <el-icon class="upload-icon"><UploadFilled /></el-icon>
      <div class="el-upload__text">
        Drop the plugin zip here, or <em>click to browse</em>
      </div>
      <template #tip>
        <div class="upload-tip">
          Only .zip ≤ {{ formatMb(MAX_BYTES) }}. Must contain a top-level
          <code>plugin.json</code> matching <code>agent-plugin-spec v1</code>.
        </div>
      </template>
    </el-upload>

    <el-progress
      v-if="uploading"
      :percentage="progress"
      :status="progress === 100 ? 'success' : undefined"
      style="margin-top: 16px"
    />

    <template #footer>
      <el-button @click="visible = false" :disabled="uploading">Cancel</el-button>
      <el-button
        type="primary"
        :loading="uploading"
        :disabled="!selectedFile"
        @click="handleUpload"
      >
        Upload
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed } from "vue";
import { UploadFilled } from "@element-plus/icons-vue";
import { ElMessage, type UploadFile, type UploadInstance } from "element-plus";
import axios from "axios";
import { javaClient } from "@/api/client";
import type { components } from "@/api/types.java.gen";

type PluginResponseDto = components["schemas"]["PluginResponse"];

interface Props {
  modelValue: boolean;
}
const props = defineProps<Props>();
const emit = defineEmits<{
  "update:modelValue": [value: boolean];
  created: [plugin: PluginResponseDto];
}>();

const MAX_BYTES = 10 * 1024 * 1024; // 10 MB

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit("update:modelValue", v),
});

const uploadRef = ref<UploadInstance | null>(null);
const fileList = ref<UploadFile[]>([]);
const selectedFile = ref<File | null>(null);
const uploading = ref(false);
const progress = ref(0);
const errorMessage = ref("");

function formatMb(bytes: number) {
  return `${Math.round(bytes / 1024 / 1024)} MB`;
}

function reset() {
  fileList.value = [];
  selectedFile.value = null;
  uploading.value = false;
  progress.value = 0;
  errorMessage.value = "";
  uploadRef.value?.clearFiles();
}

function handleFileChange(uploadFile: UploadFile) {
  const file = uploadFile.raw;
  if (!file) return;
  if (!file.name.toLowerCase().endsWith(".zip")) {
    errorMessage.value = "Only .zip files are accepted";
    fileList.value = [];
    return;
  }
  if (file.size > MAX_BYTES) {
    errorMessage.value = `File exceeds ${formatMb(MAX_BYTES)} limit`;
    fileList.value = [];
    return;
  }
  selectedFile.value = file;
  errorMessage.value = "";
}

function handleExceed() {
  ElMessage.warning("Only one file at a time — replace by re-dropping");
}

function describeError(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const status = err.response?.status;
    const serverMessage = (err.response?.data as { message?: string } | undefined)?.message;
    if (status === 400) return serverMessage || "Invalid plugin.json schema";
    if (status === 413) return "File too large for backend";
    if (status === 500) {
      return (
        serverMessage ||
        "Backend POST /api/v1/plugins not ready (D Day 27 morning task). Try later."
      );
    }
    if (status === 404 || err.code === "ERR_NETWORK") {
      return "Java backend unreachable on /api/v1/plugins (Day 27 reverse fact-check #1)";
    }
    return serverMessage || err.message;
  }
  return err instanceof Error ? err.message : "Unknown upload error";
}

async function handleUpload() {
  if (!selectedFile.value) return;
  uploading.value = true;
  errorMessage.value = "";
  progress.value = 0;

  const formData = new FormData();
  formData.append("file", selectedFile.value);

  try {
    const created = await javaClient.raw.post<PluginResponseDto>(
      "/api/v1/plugins",
      formData,
      {
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: (e) => {
          if (e.total) progress.value = Math.round((e.loaded / e.total) * 100);
        },
      },
    );
    progress.value = 100;
    ElMessage.success(`Plugin "${created.data.name ?? selectedFile.value.name}" uploaded`);
    emit("created", created.data);
    visible.value = false;
    reset();
  } catch (err) {
    errorMessage.value = describeError(err);
  } finally {
    uploading.value = false;
  }
}
</script>

<style scoped>
.upload-icon {
  font-size: 56px;
  color: var(--el-color-primary);
}
.upload-tip {
  margin-top: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.upload-tip code {
  background: var(--el-fill-color-light);
  padding: 1px 4px;
  border-radius: 3px;
  font-family: "JetBrains Mono", monospace;
  font-size: 11px;
}
</style>
