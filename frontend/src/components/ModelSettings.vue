<script setup lang="ts">
import { computed, ref } from "vue";
import { api } from "../api";
import type {
  ModelConfig,
  ModelProfile,
  ModelInput,
  ModelProbe,
} from "../types";
import AppIcon from "./AppIcon.vue";

const props = defineProps<{ models: ModelConfig | null }>();
const emit = defineEmits<{ updated: [models: ModelConfig] }>();
const editingId = ref<string>();
const formOpen = ref(!props.models?.profiles.length);
const label = ref("");
const baseUrl = ref("");
const apiKey = ref("");
const showKey = ref(false);
const hasStoredKey = ref(false);
const clearKey = ref(false);
const model = ref("");
const apiFormat = ref<"auto" | "chat_completions" | "responses">("auto");
const effectiveFormat = computed(() =>
  apiFormat.value !== "auto"
    ? apiFormat.value
    : baseUrl.value.trim().replace(/\/+$/, "").endsWith("/responses")
      ? "responses"
      : "chat_completions",
);
const temperature = ref<number | string>(0.2);
const maxTokens = ref<number | string>(10000);
const tokenField = ref<"max_tokens" | "max_completion_tokens">("max_tokens");
const timeout = ref(180);
const extraBody = ref("{}");
const makeDefault = ref(true);
const availableModels = ref<string[]>([]);
const busy = ref("");
const message = ref("");
const messageType = ref("success");
const deletingId = ref("");

function notify(text: string, type = "success") {
  message.value = text;
  messageType.value = type;
}
function fail(error: unknown) {
  notify(
    error instanceof Error ? error.message : "操作失败，请重试。",
    "error",
  );
}
function edit(profile?: ModelProfile) {
  editingId.value = profile?.id;
  label.value = profile?.label || "";
  baseUrl.value = profile?.base_url || "";
  apiKey.value = "";
  showKey.value = false;
  hasStoredKey.value = profile?.has_api_key || false;
  clearKey.value = false;
  model.value = profile?.model || "";
  apiFormat.value = profile?.params.api_format || "auto";
  temperature.value = profile?.params.temperature ?? (profile ? "" : 0.2);
  maxTokens.value = profile?.params.max_tokens ?? (profile ? "" : 10000);
  tokenField.value = profile?.params.token_limit_field || "max_tokens";
  timeout.value = profile?.params.timeout_s || 180;
  extraBody.value = JSON.stringify(profile?.params.extra_body || {}, null, 2);
  makeDefault.value = profile
    ? props.models?.default_profile === profile.id
    : !props.models?.profiles.length;
  availableModels.value = [];
  message.value = "";
  deletingId.value = "";
  formOpen.value = true;
}
function parameters() {
  let extra: unknown;
  try {
    extra = JSON.parse(extraBody.value || "{}");
  } catch {
    throw new Error("额外参数必须是有效的 JSON 对象。");
  }
  if (!extra || typeof extra !== "object" || Array.isArray(extra))
    throw new Error("额外参数必须是 JSON 对象。");
  return {
    api_format: apiFormat.value,
    temperature: temperature.value === "" ? null : Number(temperature.value),
    max_tokens: maxTokens.value === "" ? null : Number(maxTokens.value),
    token_limit_field: tokenField.value,
    timeout_s: Number(timeout.value),
    extra_body: extra as Record<string, unknown>,
  };
}
function connection(): ModelProbe {
  return {
    base_url: baseUrl.value.trim(),
    api_key: apiKey.value || undefined,
    clear_api_key: clearKey.value,
    saved_id: editingId.value,
    model: model.value.trim(),
    params: parameters(),
  };
}
async function save() {
  if (busy.value) return;
  busy.value = "save";
  message.value = "";
  try {
    const probe = connection();
    const input: ModelInput = {
      label: label.value.trim(),
      base_url: probe.base_url,
      api_key: probe.api_key,
      clear_api_key: probe.clear_api_key,
      model: probe.model,
      params: probe.params,
      make_default: makeDefault.value,
    };
    emit("updated", await api.saveModel(input, editingId.value));
    apiKey.value = "";
    formOpen.value = false;
    notify("模型配置已保存，立即生效。");
  } catch (error) {
    fail(error);
  } finally {
    busy.value = "";
  }
}
async function discover() {
  if (busy.value) return;
  busy.value = "discover";
  message.value = "";
  try {
    const result = await api.discoverModels(connection());
    availableModels.value = result.models;
    notify(
      result.models.length
        ? `已获取 ${result.models.length} 个模型，可在模型 ID 中输入或选择。`
        : "服务未提供模型列表，请手动填写模型 ID。",
    );
  } catch (error) {
    fail(error);
  } finally {
    busy.value = "";
  }
}
async function test() {
  if (busy.value) return;
  busy.value = "test";
  message.value = "";
  try {
    const result = await api.testModel(connection());
    notify(`连接成功 · ${result.latency_ms} ms`);
  } catch (error) {
    fail(error);
  } finally {
    busy.value = "";
  }
}
async function setDefault(id: string) {
  busy.value = "default";
  try {
    emit("updated", await api.defaultModel(id));
    notify("默认模型已更新。");
  } catch (error) {
    fail(error);
  } finally {
    busy.value = "";
  }
}
async function remove(id: string) {
  busy.value = "delete";
  try {
    await api.deleteModel(id);
    const next = await api.models();
    emit("updated", next);
    deletingId.value = "";
    if (editingId.value === id || !next.profiles.length) {
      edit();
    }
    notify("模型配置已删除。");
  } catch (error) {
    fail(error);
  } finally {
    busy.value = "";
  }
}
</script>

<template>
  <section class="settings-page" aria-label="模型设置">
    <div class="page-heading">
      <div>
        <h1>模型设置</h1>
        <p>管理 OpenAI 兼容接口，在书籍分析时自由切换。</p>
      </div>
      <button class="button primary" :disabled="!!busy" @click="edit()">
        <AppIcon name="plus" :size="17" />添加模型
      </button>
    </div>
    <div
      v-if="message"
      class="notice"
      :class="messageType"
      role="status"
      aria-live="polite"
    >
      {{ message }}
    </div>
    <div v-if="models?.profiles.length" class="model-list">
      <div class="model-list-label">
        已配置模型 <span>{{ models.profiles.length }}</span>
      </div>
      <article
        v-for="profile in models.profiles"
        :key="profile.id"
        class="model-row"
      >
        <div class="model-row-info">
          <div>
            <strong>{{ profile.label }}</strong><span
              v-if="models.default_profile === profile.id"
              class="badge blue"
              >默认</span
            >
          </div>
          <p>
            {{ profile.model }} <span>·</span>
            {{ profile.has_api_key ? "已设置密钥" : "无密钥" }}
          </p>
          <small>{{ profile.base_url }}</small>
        </div>
        <div class="row-actions">
          <button
            v-if="models.default_profile !== profile.id"
            class="text-button"
            :disabled="!!busy"
            @click="setDefault(profile.id)"
          >
            设为默认</button
          ><button
            class="text-button"
            :disabled="!!busy"
            @click="edit(profile)"
          >
            编辑</button
          ><button
            class="text-button muted"
            :disabled="!!busy"
            @click="deletingId = deletingId === profile.id ? '' : profile.id"
          >
            删除
          </button>
        </div>
        <div v-if="deletingId === profile.id" class="delete-confirm">
          <span>删除「{{ profile.label }}」？已启动的分析将继续执行。</span
          ><button class="text-button" @click="deletingId = ''">取消</button
          ><button
            class="button danger"
            :disabled="!!busy"
            @click="remove(profile.id)"
          >
            确认删除
          </button>
        </div>
      </article>
    </div>
    <form v-if="formOpen" class="model-form" @submit.prevent="save">
      <div class="form-heading">
        <h2>{{ editingId ? "编辑模型" : "添加模型" }}</h2>
        <span>{{
          effectiveFormat === "responses" ? "Responses" : "Chat Completions"
        }}</span>
      </div>
      <fieldset :disabled="!!busy">
        <div class="form-grid">
          <label class="form-field"
            >配置名称<input
              v-model="label"
              required
              maxlength="100"
              placeholder="例如：日常分析 / 本地模型"
          /></label>
          <label class="form-field full-width"
            >Base URL<input
              v-model="baseUrl"
              required
              type="url"
              placeholder="https://your-api.example/v1"
            /><small
              >可填写 API 根地址，或完整的 /responses、/chat/completions
              地址。</small
            ></label
          >
          <label class="form-field full-width"
            >接口格式
            <select v-model="apiFormat" aria-label="接口格式">
              <option value="auto">
                自动识别（完整 Responses 地址会自动匹配）
              </option>
              <option value="chat_completions">Chat Completions</option>
              <option value="responses">Responses</option>
            </select>
            <small>{{
              effectiveFormat === "responses"
                ? "当前使用 Responses，发送 input 并读取 output 文本。"
                : "当前使用 Chat Completions；使用 Responses 根地址时请选择 Responses。"
            }}</small>
          </label>
          <div class="form-field full-width">
            <label for="api-key"
              >API Key <span class="optional">可选</span></label
            >
            <div class="key-input">
              <input
                id="api-key"
                v-model="apiKey"
                :type="showKey ? 'text' : 'password'"
                autocomplete="new-password"
                :disabled="clearKey"
                :placeholder="
                  hasStoredKey
                    ? '已保存密钥，留空保持不变'
                    : '输入 API Key；无认证的本地服务可留空'
                "
                maxlength="4096"
              /><button
                type="button"
                class="text-button"
                @click="showKey = !showKey"
              >
                {{ showKey ? "隐藏" : "显示" }}
              </button>
            </div>
            <label v-if="hasStoredKey" class="checkbox-label"
              ><input
                type="checkbox"
                v-model="clearKey"
                @change="apiKey = ''"
              />清除已保存的密钥</label
            ><small>密钥保存在服务端，保存后不会回传浏览器。</small>
          </div>
          <div class="form-field full-width">
            <label for="model-id">模型 ID</label>
            <div class="inline-input">
              <input
                id="model-id"
                v-model="model"
                required
                maxlength="200"
                list="available-models"
                placeholder="填写服务提供的模型名称或接入点 ID"
              /><button
                type="button"
                class="button"
                :disabled="!baseUrl.trim()"
                @click="discover"
              >
                {{ busy === "discover" ? "正在获取…" : "获取模型" }}
              </button>
            </div>
            <datalist id="available-models">
              <option
                v-for="id in availableModels"
                :key="id"
                :value="id"
              /></datalist
            ><small>不支持获取列表的服务，可以直接手动填写。</small>
          </div>
        </div>
        <details class="advanced-settings">
          <summary>高级参数</summary>
          <div class="form-grid">
            <label class="form-field"
              >温度<input
                v-model="temperature"
                type="number"
                min="0"
                max="2"
                step="0.1"
                placeholder="留空不发送"
              /><small>不支持温度的模型请留空。</small></label
            ><label class="form-field"
              >最大输出 Token<input
                v-model="maxTokens"
                type="number"
                min="1"
                max="131072"
                placeholder="留空使用服务默认值" /></label
            ><label class="form-field"
              >输出上限字段<select
                v-model="tokenField"
                aria-label="输出上限字段"
              >
                <option value="max_tokens">max_tokens</option>
                <option value="max_completion_tokens">
                  max_completion_tokens
                </option>
              </select></label
            ><label class="form-field"
              >请求超时（秒）<input
                v-model="timeout"
                required
                type="number"
                min="1"
                max="600" /></label
            ><label class="form-field full-width"
              >额外请求参数（JSON）<textarea
                v-model="extraBody"
                rows="4"
                spellcheck="false"
                placeholder="{}"
              /><small
                >按服务需要设置 thinking、reasoning_effort
                等参数；默认不添加厂商专用参数。</small
              ></label
            >
          </div>
        </details>
        <label class="checkbox-label default-checkbox"
          ><input
            type="checkbox"
            v-model="makeDefault"
          />设为默认分析模型</label
        >
        <div class="form-footer">
          <span>连接测试会发送一次简短模型请求。</span>
          <div>
            <button
              type="button"
              class="button"
              :disabled="!baseUrl.trim() || !model.trim()"
              @click="test"
            >
              {{ busy === "test" ? "正在测试…" : "测试连接" }}</button><button
              v-if="models?.profiles.length"
              type="button"
              class="button"
              @click="
                formOpen = false;
                apiKey = '';
              "
            >
              取消</button
            ><button type="submit" class="button primary">
              {{ busy === "save" ? "正在保存…" : "保存配置" }}
            </button>
          </div>
        </div>
      </fieldset>
    </form>
    <p class="settings-footnote">配置保存后立即生效，重启服务后仍会保留。</p>
  </section>
</template>
