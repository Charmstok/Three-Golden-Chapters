<script setup lang="ts">
import { ref } from "vue";
import AppIcon from "./AppIcon.vue";
defineProps<{ busy: boolean }>();
const emit = defineEmits<{ upload: [file: File]; error: [message: string] }>();
const input = ref<HTMLInputElement>();
const dragging = ref(false);

function select(file?: File) {
  if (!file) return;
  if (!file.name.toLowerCase().endsWith(".epub")) {
    emit("error", "请选择 EPUB 格式的电子书。");
    return;
  }
  if (file.size > 50 * 1024 * 1024) {
    emit("error", "电子书不能超过 50 MB。");
    return;
  }
  emit("upload", file);
}
function drop(event: DragEvent) {
  dragging.value = false;
  select(event.dataTransfer?.files[0]);
}
function change(event: Event) {
  select((event.target as HTMLInputElement).files?.[0]);
  if (input.value) input.value.value = "";
}
</script>

<template>
  <button
    class="upload-panel"
    :class="{ dragging }"
    :disabled="busy"
    @click="input?.click()"
    @dragover.prevent="dragging = true"
    @dragleave.prevent="dragging = false"
    @drop.prevent="!busy && drop($event)"
  >
    <span class="upload-symbol"
      ><AppIcon :name="busy ? 'clock' : 'upload'" :size="24"
    /></span>
    <span
      ><strong>{{ busy ? "正在提取前三章…" : "上传 EPUB 电子书" }}</strong
      ><small>{{
        busy
          ? "上传完成后将自动打开章节预览"
          : "点击上传，或将 EPUB 电子书拖到这里 · 最大 50 MB"
      }}</small></span
    >
    <span v-if="!busy" class="upload-action"
      >上传书籍 <AppIcon name="arrow" :size="17"
    /></span>
  </button>
  <input
    ref="input"
    class="visually-hidden"
    type="file"
    accept=".epub,application/epub+zip"
    aria-label="选择 EPUB 电子书"
    :disabled="busy"
    @change="change"
  />
</template>
