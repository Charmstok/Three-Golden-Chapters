<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { api } from "./api";
import AppIcon from "./components/AppIcon.vue";
import BookWorkspace from "./components/BookWorkspace.vue";
import ModelSettings from "./components/ModelSettings.vue";
import UploadPanel from "./components/UploadPanel.vue";
import type { Book, BookDetail, BookStatus, ModelConfig } from "./types";

const hash = window.location.hash.slice(1);
const view = ref<"library" | "settings">(
  hash === "settings" ? "settings" : "library",
);
const selectedId = ref(/^[a-f0-9]{32}$/.test(hash) ? hash : "");
const books = ref<Book[]>([]);
const detail = ref<BookDetail | null>(null);
const models = ref<ModelConfig | null>(null);
const search = ref("");
const filter = ref("all");
const sidebarOpen = ref(false);
const desktopCollapsed = ref(false);
const loading = ref(true);
const detailLoading = ref(false);
const uploading = ref(false);
const acting = ref(false);
const error = ref("");
const fileInput = ref<HTMLInputElement>();
let detailVersion = 0;
let polling = false;
let timer: ReturnType<typeof setInterval> | undefined;
const statusLabels: Record<BookStatus, string> = {
  ready: "待分析",
  queued: "排队中",
  running: "分析中",
  completed: "已完成",
  failed: "待重试",
};
const groups = [
  { id: "all", label: "全部" },
  { id: "ready", label: "待分析" },
  { id: "active", label: "分析中" },
  { id: "completed", label: "已完成" },
];
const activeCount = computed(
  () =>
    books.value.filter((book) => ["running", "queued"].includes(book.status))
      .length,
);
function matches(book: Book, group: string) {
  if (group === "all") return true;
  if (group === "ready") return ["ready", "failed"].includes(book.status);
  if (group === "active") return ["running", "queued"].includes(book.status);
  return book.status === group;
}
const filteredBooks = computed(() =>
  books.value.filter(
    (book) =>
      matches(book, filter.value) &&
      book.title.toLowerCase().includes(search.value.toLowerCase()),
  ),
);
function count(group: string) {
  return books.value.filter((book) => matches(book, group)).length;
}
function showError(cause: unknown) {
  error.value = cause instanceof Error ? cause.message : "操作失败，请重试。";
}
function acceptBook(book: BookDetail) {
  const index = books.value.findIndex((item) => item.id === book.id);
  if (index >= 0) books.value[index] = book;
  else books.value.unshift(book);
  if (selectedId.value === book.id) detail.value = book;
}
async function loadDetail(id: string) {
  const version = ++detailVersion;
  if (!id) {
    detail.value = null;
    detailLoading.value = false;
    return;
  }
  detailLoading.value = detail.value?.id !== id;
  try {
    const book = await api.book(id);
    if (version === detailVersion && selectedId.value === id) acceptBook(book);
  } catch (cause) {
    if (version === detailVersion) showError(cause);
  } finally {
    if (version === detailVersion) detailLoading.value = false;
  }
}
watch(selectedId, (id) => void loadDetail(id));
watch([view, selectedId], () => {
  const next = view.value === "settings" ? "settings" : selectedId.value;
  window.history.replaceState(
    null,
    "",
    next ? `#${next}` : window.location.pathname,
  );
  sidebarOpen.value = false;
});
function toggleNavigation() {
  if (window.matchMedia("(max-width: 800px)").matches)
    sidebarOpen.value = !sidebarOpen.value;
  else desktopCollapsed.value = !desktopCollapsed.value;
}
function library(group = "all") {
  view.value = "library";
  selectedId.value = "";
  filter.value = group;
  sidebarOpen.value = false;
}
function openBook(id: string) {
  view.value = "library";
  selectedId.value = id;
  sidebarOpen.value = false;
}
function settings() {
  view.value = "settings";
  sidebarOpen.value = false;
}
async function refreshModels() {
  try {
    models.value = await api.models();
  } catch (cause) {
    showError(cause);
  }
}
async function refresh() {
  if (polling) return;
  polling = true;
  try {
    books.value = await api.books();
    if (
      selectedId.value &&
      !books.value.some((book) => book.id === selectedId.value)
    )
      selectedId.value = "";
    else if (selectedId.value) await loadDetail(selectedId.value);
  } catch (cause) {
    showError(cause);
  } finally {
    polling = false;
    loading.value = false;
  }
}
async function upload(file: File) {
  if (uploading.value) return;
  if (!file.name.toLowerCase().endsWith(".epub")) {
    error.value = "请选择 EPUB 格式的电子书。";
    return;
  }
  if (file.size > 50 * 1024 * 1024) {
    error.value = "电子书不能超过 50 MB。";
    return;
  }
  uploading.value = true;
  error.value = "";
  try {
    const book = await api.upload(file);
    search.value = "";
    acceptBook(book);
    detail.value = book;
    openBook(book.id);
  } catch (cause) {
    showError(cause);
  } finally {
    uploading.value = false;
  }
}
function selectFile(event: Event) {
  const input = event.target as HTMLInputElement;
  if (input.files?.[0]) void upload(input.files[0]);
  input.value = "";
}
async function analyze(profileId: string) {
  if (!detail.value || acting.value) return;
  const id = detail.value.id;
  acting.value = true;
  ++detailVersion;
  error.value = "";
  try {
    acceptBook(await api.analyze(id, profileId));
  } catch (cause) {
    showError(cause);
  } finally {
    acting.value = false;
  }
}
async function deleteBook() {
  if (!detail.value || acting.value) return;
  const id = detail.value.id;
  acting.value = true;
  ++detailVersion;
  try {
    await api.delete(id);
    books.value = books.value.filter((book) => book.id !== id);
    if (selectedId.value === id) selectedId.value = "";
  } catch (cause) {
    showError(cause);
  } finally {
    acting.value = false;
  }
}
function formatDate(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}
function hashChange() {
  const id = window.location.hash.slice(1);
  view.value = id === "settings" ? "settings" : "library";
  selectedId.value = /^[a-f0-9]{32}$/.test(id) ? id : "";
}
onMounted(async () => {
  await Promise.allSettled([refresh(), refreshModels()]);
  timer = setInterval(() => {
    if (activeCount.value && !acting.value && !uploading.value) void refresh();
  }, 2000);
  window.addEventListener("hashchange", hashChange);
});
onUnmounted(() => {
  clearInterval(timer);
  window.removeEventListener("hashchange", hashChange);
});
</script>

<template>
  <div class="app-shell" :class="{ 'sidebar-collapsed': desktopCollapsed }">
    <header class="app-header">
      <button
        class="icon-button menu-toggle"
        aria-label="切换导航"
        @click="toggleNavigation"
      >
        <AppIcon name="menu" :size="23" />
      </button>
      <a class="brand" href="#" @click.prevent="library()"
        ><span class="brand-icon"><AppIcon name="book" :size="23" /></span
        ><strong>黄金三章</strong></a
      >
      <div class="header-actions">
        <span class="header-status" v-if="activeCount"
          ><i class="status-dot running" />{{ activeCount }} 个任务进行中</span
        ><button class="button" @click="settings">
          <AppIcon name="settings" :size="17" /><span>模型设置</span></button
        ><button
          class="button primary"
          :disabled="uploading"
          @click="fileInput?.click()"
        >
          <AppIcon name="plus" :size="18" /><span>{{
            uploading ? "正在上传…" : "上传书籍"
          }}</span>
        </button>
      </div>
      <input
        ref="fileInput"
        type="file"
        class="visually-hidden"
        accept=".epub,application/epub+zip"
        aria-label="上传 EPUB 文件"
        :disabled="uploading"
        @change="selectFile"
      />
    </header>
    <button
      v-if="sidebarOpen"
      class="sidebar-backdrop"
      aria-label="关闭导航"
      @click="sidebarOpen = false"
    />
    <aside class="sidebar" :class="{ open: sidebarOpen }">
      <nav class="main-nav" aria-label="主导航">
        <button :class="{ selected: view === 'library' }" @click="library()">
          <AppIcon name="book" /><span>我的书库</span
          ><small>{{ books.length }}</small></button
        ><button :class="{ selected: view === 'settings' }" @click="settings">
          <AppIcon name="settings" /><span>模型设置</span>
        </button>
      </nav>
      <section class="sidebar-section">
        <h2>书库概览</h2>
        <button
          v-for="group in groups.slice(1)"
          :key="group.id"
          class="sidebar-stat"
          @click="library(group.id)"
        >
          <span
            ><i
              class="status-dot"
              :class="group.id === 'active' ? 'running' : group.id"
            />{{ group.label }}</span
          ><small>{{ count(group.id) }}</small>
        </button>
      </section>
      <section v-if="books.length" class="sidebar-section recent-books">
        <h2>最近书籍</h2>
        <button
          v-for="book in books.slice(0, 5)"
          :key="book.id"
          :class="{ selected: view === 'library' && selectedId === book.id }"
          @click="openBook(book.id)"
        >
          <AppIcon name="book" :size="15" /><span>{{ book.title }}</span>
        </button>
      </section>
      <div class="sidebar-footer">
        小说开篇分析工具<br /><span>EPUB · 黄金三章</span>
      </div>
    </aside>
    <main class="main">
      <div v-if="error" class="notice error global-error" role="alert">
        <span>{{ error }}</span><button
          class="icon-button"
          aria-label="关闭提示"
          @click="error = ''"
        >
          <AppIcon name="close" :size="17" />
        </button>
      </div>
      <template v-if="view === 'settings'"
        ><ModelSettings
          v-if="models"
          :models="models"
          @updated="models = $event"
        />
        <div v-else class="loading-workspace">正在读取模型配置…</div></template
      >
      <template v-else>
        <div class="info-banner">
          <strong>黄金三章</strong
          ><span>上传 EPUB，提取前三章，拆解剧情、节奏与爆点。</span
          ><button
            v-if="!models?.profiles.length"
            class="text-button"
            @click="settings"
          >
            先配置模型 <AppIcon name="arrow" :size="15" />
          </button>
        </div>
        <template v-if="selectedId"
          ><button class="back-link" @click="library()">
            <AppIcon name="back" :size="17" />返回书库
          </button>
          <div v-if="detailLoading" class="loading-workspace" role="status">
            正在打开章节…
          </div>
          <BookWorkspace
            v-else-if="detail"
            :book="detail"
            :models="models"
            :busy="acting"
            @analyze="analyze"
            @delete="deleteBook"
            @settings="settings"
        /></template>
        <section v-else class="library-page" aria-label="我的书库">
          <div class="page-heading">
            <div>
              <h1>我的书库</h1>
              <p>
                {{ books.length }} 本书籍，{{ count("completed") }}
                份已完成分析。
              </p>
            </div>
          </div>
          <div class="library-toolbar">
            <div class="filter-tabs" aria-label="书籍筛选">
              <button
                v-for="group in groups"
                :key="group.id"
                :class="{ selected: filter === group.id }"
                :aria-pressed="filter === group.id"
                @click="filter = group.id"
              >
                {{ group.label }}<span>{{ count(group.id) }}</span>
              </button>
            </div>
            <label class="search-field"
              ><AppIcon name="search" :size="17" /><input
                v-model="search"
                placeholder="搜索书籍"
                aria-label="搜索书籍" /></label
            ><button
              class="icon-button"
              aria-label="刷新书库"
              title="刷新书库"
              @click="refresh"
            >
              <AppIcon name="refresh" :size="18" />
            </button>
          </div>
          <div class="book-table-wrap">
            <table class="book-table">
              <thead>
                <tr>
                  <th>书籍</th>
                  <th>章节</th>
                  <th class="paragraph-count-col">段落</th>
                  <th>状态</th>
                  <th class="date-col">上传时间</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="book in filteredBooks" :key="book.id">
                  <td>
                    <button class="book-link" @click="openBook(book.id)">
                      {{ book.title }}
                    </button>
                    <p class="book-meta">
                      <span class="file-tag">EPUB</span>{{ book.filename }}
                    </p>
                  </td>
                  <td>{{ book.chapter_count }}</td>
                  <td class="paragraph-count-col">
                    {{ book.paragraph_count.toLocaleString() }}
                  </td>
                  <td>
                    <span class="badge" :class="book.status"
                      ><i class="status-dot" :class="book.status" />{{
                        statusLabels[book.status]
                      }}<template v-if="book.status === 'running'">
                        {{ book.progress }}%</template
                      ></span
                    >
                  </td>
                  <td class="date-col">{{ formatDate(book.created_at) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-if="loading" class="empty-state" role="status">
            正在读取书库…
          </div>
          <div v-else-if="!books.length" class="empty-library">
            <AppIcon name="book" :size="38" />
            <h2>书库还是空的</h2>
            <p>上传第一本 EPUB，开始分析小说开篇。</p>
            <UploadPanel
              :busy="uploading"
              @upload="upload"
              @error="error = $event"
            />
          </div>
          <div v-else-if="!filteredBooks.length" class="empty-state">
            没有找到匹配的书籍
          </div>
          <div v-if="books.length" class="table-footer">
            共 {{ filteredBooks.length }} 本书籍<span
              >点击书名查看原文与分析</span
            >
          </div>
        </section>
      </template>
      <footer class="main-footer">
        <span>黄金三章</span><span>AI 分析仅供参考</span>
      </footer>
    </main>
  </div>
</template>
