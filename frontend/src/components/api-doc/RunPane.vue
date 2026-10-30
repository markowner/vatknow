<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import { NButton, NInput, NTag, useMessage } from "naive-ui";
import { ApiProxy } from "@/api";
import { buildUrl, mergeCommonParams, type OpenOp, type OpenParam } from "@/openapi";
import MethodBadge from "./MethodBadge.vue";

const props = defineProps<{
  op: OpenOp;
  server: string;
  spaceId: string;
  documentId: string;
  commonParams?: OpenParam[];
}>();

const message = useMessage();
const values = reactive<Record<string, string>>({});
const bodyText = ref("");
const sending = ref(false);
const result = ref<{ status_code: number; elapsed_ms: number; headers: Record<string, string>; body: string; error: string | null } | null>(null);

/** 公共参数与接口参数合并后再渲染，调试时的请求才和真实调用一致。 */
const allParams = computed(() =>
  mergeCommonParams(props.op.parameters, (props.commonParams || []).filter((item) => item.in !== "path")),
);

function fill() {
  bodyText.value = props.op.body?.example || "";
  result.value = null;
  for (const param of allParams.value) {
    const key = `${param.in}:${param.name}`;
    const sample = param.schema?.example ?? param.schema?.default;
    values[key] = sample === undefined ? values[key] || "" : String(sample);
  }
}

watch([() => props.op, allParams], fill, { immediate: true });

const previewUrl = computed(() => buildUrl(props.server, props.op.path, allParams.value, values));
const pathParams = computed(() => props.op.parameters.filter((item) => item.in === "path"));
const queryParams = computed(() => props.op.parameters.filter((item) => item.in === "query"));
const headerParams = computed(() => props.op.parameters.filter((item) => item.in === "header"));

/**
 * 公共参数单独成组展示，别和接口自己的参数混在一起。
 * 接口自己定义了同名参数时已被覆盖，这里就不再重复列出。
 */
const commonRows = computed(() => {
  const own = new Set(props.op.parameters.map((item) => `${item.in}:${item.name}`));
  return (props.commonParams || []).filter(
    (item) => item.name.trim() && item.in !== "path" && !own.has(`${item.in}:${item.name}`),
  );
});

async function send() {
  if (!props.documentId) {
    message.warning("请先保存文档");
    return;
  }
  sending.value = true;
  result.value = null;
  const headers: Record<string, string> = {};
  for (const param of allParams.value) {
    if (param.in !== "header") continue;
    const value = values[`header:${param.name}`];
    if (value) headers[param.name] = value;
  }
  if (props.op.body && !["GET", "HEAD"].includes(props.op.method)) {
    headers["Content-Type"] = props.op.body.contentType || "application/json";
  }
  try {
    result.value = await ApiProxy.send(props.spaceId, {
      document_id: props.documentId,
      method: props.op.method,
      url: previewUrl.value,
      headers,
      body: ["GET", "HEAD"].includes(props.op.method) ? null : bodyText.value,
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

async function copyCurl() {
  const parts = [`curl -X ${props.op.method} '${previewUrl.value}'`];
  for (const param of allParams.value) {
    if (param.in !== "header") continue;
    const value = values[`header:${param.name}`];
    if (value) parts.push(`  -H '${param.name}: ${value.replace(/'/g, "'\\''")}'`);
  }
  if (props.op.body && bodyText.value && !["GET", "HEAD"].includes(props.op.method)) {
    parts.push(`  -H 'Content-Type: ${props.op.body.contentType || "application/json"}'`);
    parts.push(`  -d '${bodyText.value.replace(/'/g, "'\\''")}'`);
  }
  await navigator.clipboard.writeText(parts.join(" \\\n"));
  message.success("已复制 curl");
}

function pretty(text: string) {
  try {
    return JSON.stringify(JSON.parse(text), null, 2);
  } catch {
    return text;
  }
}

function formatBody() {
  try {
    bodyText.value = JSON.stringify(JSON.parse(bodyText.value || "{}"), null, 2);
  } catch {
    message.warning("JSON 无法格式化");
  }
}
</script>

<template>
  <div class="run">
    <div class="url">
      <MethodBadge :method="op.method" large />
      <code>{{ previewUrl }}</code>
      <n-button type="primary" :loading="sending" @click="send">发送</n-button>
      <n-button @click="copyCurl">curl</n-button>
    </div>
    <div class="split">
      <div class="pane">
        <h4>请求</h4>
        <!-- 公共参数来自文档级配置，放在最上面：每次调试都要填，位置固定才好找 -->
        <template v-if="commonRows.length">
          <h5>公共参数 <i>文档级，所有接口都带</i></h5>
          <div v-for="item in commonRows" :key="'common-' + item.in + item.name" class="field">
            <label>
              {{ item.name }}
              <em v-if="item.required">*</em>
              <span>{{ item.in === "query" ? "Query" : "Header" }}{{ item.description ? " · " + item.description : "" }}</span>
            </label>
            <n-input v-model:value="values[`${item.in}:${item.name}`]" :placeholder="String(item.schema?.example ?? item.name)" />
          </div>
        </template>
        <template v-for="block in [
          { title: 'Path', rows: pathParams, loc: 'path' },
          { title: 'Query', rows: queryParams, loc: 'query' },
          { title: 'Headers', rows: headerParams, loc: 'header' },
        ]" :key="block.title">
          <template v-if="block.rows.length">
            <h5>{{ block.title }}</h5>
            <div v-for="item in block.rows" :key="block.loc + item.name" class="field">
              <label>{{ item.name }} <em v-if="item.required">*</em> <span>{{ item.description }}</span></label>
              <n-input v-model:value="values[`${block.loc}:${item.name}`]" :placeholder="String(item.schema?.example ?? item.name)" />
            </div>
          </template>
        </template>
        <template v-if="op.body">
          <div class="hd">
            <h5>Body</h5>
            <n-button size="tiny" @click="formatBody">格式化</n-button>
          </div>
          <n-input v-model:value="bodyText" type="textarea" :autosize="{ minRows: 8, maxRows: 18 }" />
        </template>
      </div>
      <div class="pane dark">
        <h4>响应</h4>
        <div v-if="!result" class="empty">填好左侧参数后点发送。服务端代发，不依赖浏览器 CORS。</div>
        <template v-else>
          <n-tag :type="result.error || result.status_code >= 400 ? 'error' : 'success'" :bordered="false">
            {{ result.error ? "失败" : result.status_code }} · {{ result.elapsed_ms }} ms
          </n-tag>
          <pre>{{ result.error || pretty(result.body) || "空响应" }}</pre>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.run {
  padding: 8px 0 24px;
}
.url {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 14px;
}
.url :deep(.badge) {
  flex: none;
}
.url code {
  flex: 1;
  background: #f8fafc;
  padding: 10px 12px;
  border-radius: 8px;
  overflow: auto;
  white-space: nowrap;
  font-size: 13px;
}
.split {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  min-height: 420px;
}
.pane {
  border: 1px solid #e2e8f4;
  border-radius: 14px;
  padding: 14px 16px;
  background: #fff;
}
.pane.dark {
  background: #0b1220;
  border-color: #0b1220;
  color: #e7e5e4;
}
.pane.dark h4 {
  color: #cbd5e1;
}
h4 {
  margin: 0 0 12px;
  font-size: 13px;
}
h5 {
  margin: 12px 0 8px;
  font-size: 12px;
  color: #64748b;
}
.hd {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.field {
  margin-bottom: 10px;
}
.field label {
  display: block;
  font-size: 13px;
  margin-bottom: 4px;
}
.field span,
.empty {
  color: #94a3b8;
  font-weight: 400;
  font-size: 12px;
}
h5 i {
  color: #94a3b8;
  font-style: normal;
  font-weight: 400;
  margin-left: 6px;
}
em {
  color: #ef4444;
  font-style: normal;
}
pre {
  margin: 10px 0 0;
  white-space: pre-wrap;
  font-size: 12px;
  line-height: 1.55;
  color: #bbf7d0;
}
@media (max-width: 1100px) {
  .split {
    grid-template-columns: 1fr;
  }
}
</style>
