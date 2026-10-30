<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import { NButton, NEmpty, NInput, NSelect, NTag } from "naive-ui";
import { ApiProxy } from "@/api";
import { buildUrl, methodColor, parseOpenApi, type OpenOp } from "@/openapi";

const props = defineProps<{
  spec: string;
  spaceId?: string;
  documentId?: string;
}>();

const parsed = computed(() => parseOpenApi(props.spec));
const keyword = ref("");
const server = ref("");
const auth = ref("");
const current = ref<OpenOp | null>(null);
const values = reactive<Record<string, string>>({});
const bodyText = ref("");
const sending = ref(false);
const result = ref<{ status_code: number; elapsed_ms: number; headers: Record<string, string>; body: string; error: string | null } | null>(null);

watch(
  parsed,
  (spec) => {
    if (!spec) return;
    if (!server.value || !spec.servers.includes(server.value)) server.value = spec.servers[0] || "";
    if (!current.value && spec.ops[0]) selectOp(spec.ops[0]);
  },
  { immediate: true },
);

const groups = computed(() => {
  const spec = parsed.value;
  if (!spec) return [];
  const map = new Map<string, OpenOp[]>();
  const q = keyword.value.trim().toLowerCase();
  for (const op of spec.ops) {
    const hay = `${op.method} ${op.path} ${op.summary}`.toLowerCase();
    if (q && !hay.includes(q)) continue;
    const tag = op.tags[0] || "default";
    if (!map.has(tag)) map.set(tag, []);
    map.get(tag)!.push(op);
  }
  return [...map.entries()];
});

function selectOp(op: OpenOp) {
  current.value = op;
  bodyText.value = op.body?.example || "";
  result.value = null;
  for (const param of op.parameters) {
    const key = `${param.in}:${param.name}`;
    if (values[key] === undefined) {
      const sample = param.schema?.example ?? param.schema?.default;
      values[key] = sample === undefined ? "" : String(sample);
    }
  }
}

const previewUrl = computed(() => {
  if (!current.value) return "";
  return buildUrl(server.value, current.value.path, current.value.parameters, values);
});

async function send() {
  if (!current.value || !props.spaceId || !props.documentId) return;
  sending.value = true;
  result.value = null;
  const headers: Record<string, string> = {};
  if (auth.value.trim()) headers.Authorization = auth.value.trim().startsWith("Bearer ")
    ? auth.value.trim()
    : `Bearer ${auth.value.trim()}`;
  for (const param of current.value.parameters) {
    if (param.in === "header") {
      const value = values[`header:${param.name}`];
      if (value) headers[param.name] = value;
    }
  }
  if (current.value.body && !["GET", "HEAD"].includes(current.value.method)) {
    headers["Content-Type"] = current.value.body.contentType || "application/json";
  }
  try {
    result.value = await ApiProxy.send(props.spaceId, {
      document_id: props.documentId,
      method: current.value.method,
      url: previewUrl.value,
      headers,
      body: ["GET", "HEAD"].includes(current.value.method) ? null : bodyText.value,
    });
  } catch (err) {
    result.value = {
      status_code: 0,
      elapsed_ms: 0,
      headers: {},
      body: "",
      error: err instanceof Error ? err.message : "请求失败",
    };
  } finally {
    sending.value = false;
  }
}

function pretty(text: string) {
  try {
    return JSON.stringify(JSON.parse(text), null, 2);
  } catch {
    return text;
  }
}

const canProxy = computed(() => Boolean(props.spaceId && props.documentId));
</script>

<template>
  <div v-if="!parsed" class="empty">无法解析 OpenAPI 文档，请确认是 JSON 格式。</div>
  <div v-else class="console">
    <aside class="side">
      <div class="brand">
        <div class="name">{{ parsed.title }}</div>
        <div class="ver">{{ parsed.version || "OpenAPI" }} · {{ parsed.ops.length }} 个接口</div>
      </div>
      <n-input v-model:value="keyword" size="small" placeholder="搜索路径 / 方法 / 摘要" />
      <div class="groups">
        <div v-for="[tag, ops] in groups" :key="tag" class="group">
          <div class="tag">{{ tag }}</div>
          <button
            v-for="op in ops"
            :key="op.method + op.path"
            class="op"
            :class="{ active: current === op }"
            @click="selectOp(op)"
          >
            <span class="m" :style="{ color: methodColor(op.method) }">{{ op.method }}</span>
            <span class="p">{{ op.path }}</span>
          </button>
        </div>
        <n-empty v-if="!groups.length" description="没有匹配接口" />
      </div>
    </aside>
    <section class="main">
      <header class="head">
        <div>
          <div class="line">
            <span class="badge" :style="{ background: methodColor(current?.method || 'GET') }">{{ current?.method }}</span>
            <code class="path">{{ current?.path }}</code>
          </div>
          <div class="summary">{{ current?.summary }}</div>
        </div>
        <div class="tools">
          <n-select v-model:value="server" :options="parsed.servers.map((item) => ({ label: item, value: item }))" style="width: 280px" />
          <n-input v-model:value="auth" placeholder="Bearer Token / API Key" style="width: 240px" />
        </div>
      </header>
      <p v-if="parsed.description || current?.description" class="desc">{{ current?.description || parsed.description }}</p>
      <p v-if="parsed.notes" class="notes">文档备注：{{ parsed.notes }}</p>
      <p v-if="current?.notes" class="notes">接口备注：{{ current.notes }}</p>
      <div class="urlbar">
        <code>{{ previewUrl }}</code>
      </div>
      <div class="grid">
        <div class="panel">
          <h4>请求参数</h4>
          <div v-if="!current?.parameters.length" class="muted">没有参数</div>
          <div v-for="param in current?.parameters || []" :key="param.in + param.name" class="field">
            <label>
              <span>{{ param.name }}</span>
              <n-tag size="small" :bordered="false">{{ param.in }}</n-tag>
              <n-tag v-if="param.required" size="small" type="error" :bordered="false">必填</n-tag>
            </label>
            <div v-if="param.description" class="muted">{{ param.description }}</div>
            <n-input v-model:value="values[`${param.in}:${param.name}`]" :placeholder="param.name" />
          </div>
          <template v-if="current?.body">
            <h4>请求体 · {{ current.body.contentType }}</h4>
            <p v-if="current.body.description" class="muted">{{ current.body.description }}</p>
            <n-input v-model:value="bodyText" type="textarea" :autosize="{ minRows: 10, maxRows: 18 }" />
          </template>
          <div class="send">
            <n-button type="primary" size="large" :loading="sending" :disabled="!canProxy || !current" @click="send">
              发送请求
            </n-button>
            <span v-if="!canProxy" class="muted">公开分享页不经过服务端代理，请在空间内打开以在线调试。</span>
          </div>
        </div>
        <div class="panel">
          <h4>响应</h4>
          <div v-if="!result" class="muted">
            填写参数后点击发送。服务端会代发请求，可绕过浏览器 CORS。
            <div v-if="current?.responses.length" class="expects">
              <div v-for="item in current.responses" :key="item.status">
                <n-tag size="small" :bordered="false">{{ item.status }}</n-tag>
                {{ item.description }}
              </div>
            </div>
          </div>
          <template v-else>
            <div class="status">
              <n-tag :type="result.error || result.status_code >= 400 ? 'error' : 'success'" :bordered="false">
                {{ result.error ? "失败" : result.status_code }}
              </n-tag>
              <span>{{ result.elapsed_ms }} ms</span>
            </div>
            <pre v-if="result.error" class="out error">{{ result.error }}</pre>
            <pre class="out">{{ pretty(result.body) || "空响应" }}</pre>
          </template>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.console {
  height: calc(100vh - 96px);
  display: grid;
  grid-template-columns: 280px 1fr;
  background: #07111a;
  color: #e8f4f1;
  border-radius: 14px;
  overflow: hidden;
  border: 1px solid #163042;
}
.side {
  background: #0b1822;
  border-right: 1px solid #163042;
  padding: 16px 12px;
  overflow: auto;
}
.brand .name {
  font-weight: 700;
  font-size: 15px;
}
.ver,
.muted,
.desc,
.summary {
  color: #8aa4b0;
  font-size: 12px;
}
.ver {
  margin: 4px 0 12px;
}
.groups {
  margin-top: 12px;
}
.tag {
  font-size: 11px;
  letter-spacing: 0.08em;
  color: #5eead4;
  margin: 10px 8px 6px;
  text-transform: uppercase;
}
.op {
  width: 100%;
  display: flex;
  gap: 8px;
  align-items: center;
  background: transparent;
  border: 0;
  color: inherit;
  text-align: left;
  padding: 8px 8px;
  border-radius: 8px;
  cursor: pointer;
}
.op:hover,
.op.active {
  background: #123041;
}
.m {
  font-size: 11px;
  font-weight: 800;
  width: 52px;
  flex: none;
}
.p {
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.main {
  padding: 18px 20px;
  overflow: auto;
}
.head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}
.line {
  display: flex;
  gap: 10px;
  align-items: center;
}
.badge {
  color: #042f2e;
  font-size: 12px;
  font-weight: 800;
  padding: 3px 8px;
  border-radius: 6px;
}
.path {
  font-size: 18px;
}
.tools {
  display: flex;
  gap: 8px;
}
.desc,
.notes {
  margin: 10px 0 0;
  line-height: 1.6;
}
.notes {
  color: #fbbf24;
  font-size: 12px;
}
.urlbar {
  background: #102230;
  border: 1px solid #1d3b4d;
  border-radius: 8px;
  padding: 10px 12px;
  margin: 12px 0 16px;
  overflow: auto;
}
.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
.panel {
  background: #0e1c27;
  border: 1px solid #1d3b4d;
  border-radius: 12px;
  padding: 14px;
  min-height: 360px;
}
.panel h4 {
  margin: 0 0 12px;
}
.field {
  margin-bottom: 10px;
}
.field label {
  display: flex;
  gap: 6px;
  align-items: center;
  margin-bottom: 4px;
  font-size: 12px;
}
.send {
  margin-top: 16px;
  display: flex;
  gap: 12px;
  align-items: center;
}
.status {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 10px;
}
.out {
  background: #071018;
  color: #d1fae5;
  padding: 12px;
  border-radius: 8px;
  min-height: 240px;
  overflow: auto;
  white-space: pre-wrap;
  font-size: 12px;
}
.out.error {
  color: #fecaca;
  min-height: auto;
  margin-bottom: 8px;
}
.expects {
  margin-top: 12px;
  display: grid;
  gap: 8px;
}
.empty {
  padding: 24px;
  color: #6b7280;
}
@media (max-width: 1100px) {
  .console,
  .grid,
  .head {
    display: block;
  }
  .tools {
    margin-top: 12px;
  }
}
</style>
