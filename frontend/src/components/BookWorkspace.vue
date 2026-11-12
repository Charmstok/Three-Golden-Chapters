<script setup lang="ts">
import { computed, ref, watch } from "vue";
import AppIcon from "./AppIcon.vue";
import type { BookDetail, ModelConfig } from "../types";

const props = defineProps<{
  book: BookDetail;
  models: ModelConfig | null;
  busy: boolean;
}>();
const emit = defineEmits<{
  analyze: [profileId: string];
  delete: [];
  settings: [];
}>();
const chapterId = ref(1);
const view = ref<"analysis" | "source">("source");
const profileId = ref("");
const confirmDelete = ref(false);
const active = computed(() =>
  ["queued", "running"].includes(props.book.status),
);
const chapter = computed(
  () =>
    props.book.chapters.find((ch) => ch.id === chapterId.value) ||
    props.book.chapters[0],
);
const analysis = computed(() =>
  props.book.analyses.find((item) => item.chapter_id === chapter.value?.id),
);
const profile = computed(() =>
  props.models?.profiles.find((item) => item.id === profileId.value),
);
function selectedProfile() {
  const available = props.models?.profiles || [];
  return available.some((item) => item.id === props.book.profile_id)
    ? props.book.profile_id!
    : props.models?.default_profile || "";
}
const canAnalyze = computed(
  () => !!profile.value?.configured && !active.value && !props.busy,
);
watch(
  () => props.book.id,
  () => {
    chapterId.value = props.book.chapters[0]?.id || 1;
    view.value = props.book.analyses.length ? "analysis" : "source";
    profileId.value = selectedProfile();
    confirmDelete.value = false;
  },
  { immediate: true },
);
watch(
  () => props.models,
  () => {
    profileId.value = selectedProfile();
  },
  { immediate: true },
);
watch(
  () => props.book.analyses.length,
  (count, before) => {
    if (count > before) view.value = "analysis";
  },
);
</script>

<template>
  <section class="workspace" aria-label="书籍工作区">
    <header class="workspace-header">
      <div class="eyebrow">章节分析</div>
      <div class="workspace-title">
        <h2>{{ book.title }}</h2>
        <span class="file-tag">EPUB</span>
      </div>
      <p>
        {{ book.chapter_count }} 个章节 <span>·</span>
        {{ book.paragraph_count.toLocaleString() }} 个段落 <span>·</span>
        {{ book.filename }}
      </p>
      <div class="workspace-actions">
        <div class="model-select">
          <label for="model-profile">分析模型</label
          ><select
            id="model-profile"
            v-model="profileId"
            :disabled="active || busy"
          >
            <option
              v-for="item in models?.profiles"
              :key="item.id"
              :value="item.id"
            >
              {{ item.label }}
            </option>
          </select>
        </div>
        <button
          class="button primary"
          :disabled="!canAnalyze"
          @click="emit('analyze', profileId)"
        >
          <AppIcon :name="active ? 'clock' : 'spark'" :size="17" />{{
            active
              ? "正在分析"
              : book.status === "ready"
                ? "开始拆解"
                : "重新分析"
          }}
        </button>
        <a
          v-if="book.status === 'completed'"
          class="button"
          :href="`/api/books/${book.id}/report`"
          ><AppIcon name="download" :size="17" />Excel 报告</a
        >
        <button
          class="icon-button delete-book"
          title="删除书籍"
          aria-label="删除书籍"
          :disabled="active || busy"
          @click="confirmDelete = !confirmDelete"
        >
          <AppIcon name="trash" :size="17" />
        </button>
      </div>
      <div v-if="confirmDelete" class="delete-confirm" role="alert">
        <span>确认删除这本书及其分析报告？</span
        ><button class="text-button" @click="confirmDelete = false">取消</button
        ><button class="button danger" :disabled="busy" @click="emit('delete')">
          确认删除
        </button>
      </div>
      <div v-if="!profile?.configured" class="config-notice">
        <span>还没有可用的模型配置，添加接口地址和模型后即可开始分析。</span>
        <button class="text-button" @click="emit('settings')">
          前往模型设置
        </button>
      </div>
      <div
        v-if="active || book.status === 'failed'"
        class="progress-card"
        :class="{ failed: book.status === 'failed' }"
        role="status"
        aria-live="polite"
      >
        <div>
          <span>{{ book.message }}</span><strong>{{ book.progress }}%</strong>
        </div>
        <progress :value="book.progress" max="100" :aria-label="book.message" />
        <p v-if="book.error">{{ book.error }}</p>
        <p v-else>你可以离开页面，分析结果会自动保存。</p>
      </div>
    </header>
    <div class="reading-toolbar">
      <div class="chapter-tabs" role="tablist" aria-label="章节">
        <button
          v-for="ch in book.chapters"
          :key="ch.id"
          :class="{ selected: chapter?.id === ch.id }"
          role="tab"
          :aria-selected="chapter?.id === ch.id"
          @click="chapterId = ch.id"
        >
          第 {{ ch.no }} 章 <span>{{ ch.title }}</span><i
            v-if="book.analyses.some((a) => a.chapter_id === ch.id)"
            aria-label="已分析"
          />
        </button>
      </div>
      <div class="view-switch" aria-label="阅读视图">
        <button
          :class="{ selected: view === 'source' }"
          :aria-pressed="view === 'source'"
          @click="view = 'source'"
        >
          原文</button
        ><button
          :class="{ selected: view === 'analysis' }"
          :aria-pressed="view === 'analysis'"
          @click="view = 'analysis'"
        >
          拆解
        </button>
      </div>
    </div>
    <div
      v-if="chapter"
      class="reading-content"
      :key="`${book.id}-${chapter.id}-${view}`"
    >
      <template v-if="view === 'source'"
        ><div class="section-heading">
          <span>CHAPTER {{ String(chapter.no).padStart(2, "0") }}</span>
          <h3>{{ chapter.title }}</h3>
          <p>原文段落编号将与拆解结果逐一对应</p>
        </div>
        <div
          class="paragraph"
          v-for="p in chapter.paragraphs"
          :key="p.paragraph_id"
        >
          <span>{{ String(p.paragraph_id).padStart(2, "0") }}</span>
          <p>{{ p.text }}</p>
        </div></template
      >
      <template v-else-if="analysis"
        ><div class="section-heading analysis-heading">
          <span>STORY BREAKDOWN</span>
          <h3>{{ chapter.title }}</h3>
          <p>{{ analysis.chunks.length }} 个剧情块 · 内容、节奏与爆点</p>
          <a :href="`/api/books/${book.id}/analysis.json`" class="text-button"
            >下载分析 JSON <AppIcon name="download" :size="14"
          /></a>
        </div>
        <article
          v-for="chunk in analysis.chunks"
          :key="chunk.chunk_id"
          class="chunk"
        >
          <header>
            <span class="chunk-number">{{
              String(chunk.chunk_id).padStart(2, "0")
            }}</span>
            <div>
              <h4>{{ chunk.chunk_title }}</h4>
              <small
                >段落 {{ chunk.start_paragraph }} —
                {{ chunk.end_paragraph }}</small
              >
            </div>
          </header>
          <div class="chunk-summary">
            <p><b>剧情</b>{{ chunk.plot_summary }}</p>
            <p><b>节奏</b>{{ chunk.pacing_summary }}</p>
          </div>
          <div
            v-for="slice in chunk.slices"
            :key="slice.slice_id"
            class="slice"
          >
            <span class="slice-range"
              >{{ slice.start }}–{{ slice.end }} 段</span
            >
            <div>
              <p>{{ slice.content_summary }}</p>
              <dl>
                <div>
                  <dt>节奏</dt>
                  <dd>{{ slice.pacing_analysis }}</dd>
                </div>
                <div>
                  <dt>爆点</dt>
                  <dd>{{ slice.hook_extraction }}</dd>
                </div>
              </dl>
            </div>
          </div>
        </article>
        <p class="ai-note">内容由 AI 生成，请结合原文判断。</p></template
      >
      <div v-else class="empty-analysis">
        <span class="empty-symbol"><AppIcon name="spark" :size="30" /></span>
        <h3>{{ active ? "故事正在被拆解" : "暂无分析结果" }}</h3>
        <p>
          {{
            active
              ? "本章完成后，剧情、节奏与爆点会显示在这里。"
              : "选择模型后点击「开始拆解」，查看剧情、节奏和爆点。"
          }}
        </p>
        <button
          v-if="!active"
          class="button primary"
          :disabled="!canAnalyze"
          @click="emit('analyze', profileId)"
        >
          开始拆解 <AppIcon name="arrow" :size="16" />
        </button>
      </div>
    </div>
  </section>
</template>
