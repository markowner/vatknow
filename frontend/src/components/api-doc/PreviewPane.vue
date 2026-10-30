<script setup lang="ts">
import { computed } from "vue";
import { NButton, NTag, useMessage } from "naive-ui";
import MethodBadge from "./MethodBadge.vue";
import { type OpenOp, type OpenParam, type OpenSpec } from "@/openapi";
import { renderMarkdown } from "@/utils";

const props = defineProps<{ spec: OpenSpec; op: OpenOp; external?: boolean }>();
const message = useMessage();

const pathParams = computed(() => props.op.parameters.filter((item) => item.in === "path"));
const queryParams = computed(() => props.op.parameters.filter((item) => item.in === "query"));
const headerParams = computed(() => props.op.parameters.filter((item) => item.in === "header"));
/** 项目级公共说明是 Markdown，渲染成 HTML 再展示。 */
const descHtml = computed(() => renderMarkdown(props.op.description || ""));

/** 标出哪些参数来自全局公共参数，避免调用方以为漏看了接口定义。 */
const commonKeys = computed(
  () => new Set((props.spec.commonParams || []).map((item) => `${item.in}:${item.name}`)),
);
function isCommon(param: OpenParam) {
  return commonKeys.value.has(`${param.in}:${param.name}`);
}

function example(param: OpenParam) {
  const value = param.schema?.example ?? param.schema?.default;
  return value === undefined || value === "" ? "—" : String(value);
}

async function copy(text: string) {
  await navigator.clipboard.writeText(text);
  message.success("已复制");
}
</script>

<template>
  <div class="preview">
    <section class="card">
      <div class="card-h">基本信息</div>
      <div class="kv">
        <div><span class="kv-label">接口名称</span><b>{{ op.summary }}</b></div>
        <div v-if="!external">
          <span class="kv-label">状态</span>
          <n-tag size="small" :type="op.status === 'done' ? 'success' : 'warning'" :bordered="false" round>
            {{ op.status === "done" ? "已完成" : "未完成" }}
          </n-tag>
        </div>
        <div v-else><span class="kv-label">版本</span>{{ spec.version || "—" }}</div>
        <div class="wide">
          <span class="kv-label">请求</span>
          <div class="req">
            <MethodBadge :method="op.method" />
            <code>{{ spec.servers[0] }}{{ op.path }}</code>
            <n-button size="tiny" quaternary @click="copy(`${spec.servers[0] || ''}${op.path}`)">复制</n-button>
          </div>
        </div>
        <div><span class="kv-label">分组</span>{{ op.tags[0] || "公共分类" }}</div>
        <div v-if="!external"><span class="kv-label">版本</span>{{ spec.version || "—" }}</div>
      </div>
    </section>

    <section v-if="op.description" class="card">
      <div class="card-h">说明</div>
      <div class="md-body" v-html="descHtml" />
    </section>
    <section v-if="op.notes && !external" class="card note">
      <div class="card-h">备注</div>
      <pre class="md">{{ op.notes }}</pre>
    </section>

    <section class="card">
      <div class="card-h">请求参数</div>
      <p v-if="!pathParams.length && !queryParams.length && !headerParams.length && !op.body" class="empty">没有请求参数</p>
      <template v-for="block in [
        { title: 'Path', rows: pathParams },
        { title: 'Query', rows: queryParams },
        { title: 'Headers', rows: headerParams },
      ]" :key="block.title">
        <template v-if="block.rows.length">
          <div class="group-label">{{ block.title }}</div>
          <table>
            <thead>
              <tr><th>名称</th><th>类型</th><th>必填</th><th>示例</th><th>说明</th></tr>
            </thead>
            <tbody>
              <tr v-for="item in block.rows" :key="item.name">
                <td class="name">
                  {{ item.name }}
                  <n-tag v-if="isCommon(item)" size="tiny" :bordered="false" type="info">公共</n-tag>
                </td>
                <td><code class="type">{{ item.schema?.type || "string" }}</code></td>
                <td class="flag" :class="{ on: item.required }">{{ item.required ? "是" : "否" }}</td>
                <td class="ex">{{ example(item) }}</td>
                <td class="desc">{{ item.description || "—" }}</td>
              </tr>
            </tbody>
          </table>
        </template>
      </template>
      <div class="body-row">
        <div class="group-label">Body</div>
        <p v-if="!op.body" class="empty">无</p>
      </div>
      <template v-if="op.body">
        <p class="meta">{{ op.body.contentType }}{{ op.body.required ? " · 必填" : "" }}{{ op.body.description ? " · " + op.body.description : "" }}</p>
        <pre class="code">{{ op.body.example || "{}" }}</pre>
      </template>
    </section>

    <section class="card">
      <div class="card-h">返回数据</div>
      <div v-for="item in op.responses" :key="item.status" class="resp">
        <div class="resp-h">
          <n-tag size="small" :type="String(item.status).startsWith('2') ? 'success' : 'error'" :bordered="false">
            {{ item.status }}
          </n-tag>
          {{ item.description || "无说明" }}
        </div>
        <pre v-if="item.example" class="code">{{ item.example }}</pre>
        <p v-else class="empty">暂无返回示例</p>
      </div>
      <p v-if="!op.responses.length" class="empty">未填写返回说明</p>
    </section>
  </div>
</template>

<style scoped>
.preview {
  display: grid;
  gap: 14px;
  padding: 8px 0 28px;
}
.card {
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 16px 18px 18px;
  background: #fff;
}
.card.note {
  background: #f8fbff;
  border-color: #d7e5fb;
}
.card-h {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13.5px;
  font-weight: 650;
  color: var(--text);
  margin-bottom: 14px;
}
.card-h::before {
  content: "";
  width: 3px;
  height: 13px;
  border-radius: 2px;
  background: var(--accent);
}
.kv {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px 24px;
  font-size: 13px;
}
.kv .kv-label {
  display: block;
  color: var(--faint);
  font-size: 12px;
  margin-bottom: 4px;
}
.wide {
  grid-column: 1 / -1;
}
.req {
  display: flex;
  gap: 8px;
  align-items: center;
}
.req :deep(.badge) {
  flex: none;
}
.req code {
  background: #f8fafc;
  padding: 4px 8px;
  border-radius: 6px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.group-label {
  margin: 16px 0 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--muted);
  letter-spacing: 0.01em;
}
.group-label:first-of-type {
  margin-top: 0;
}
table {
  width: 100%;
  border-collapse: collapse;
}
thead th {
  padding: 8px 10px;
  font-size: 12px;
  font-weight: 500;
  color: var(--faint);
  text-align: left;
  background: #fafbfc;
  border-top: 1px solid var(--line-soft);
  border-bottom: 1px solid var(--line-soft);
}
thead th:first-child {
  border-top-left-radius: 8px;
}
thead th:last-child {
  border-top-right-radius: 8px;
}
tbody td {
  padding: 11px 10px;
  font-size: 13px;
  text-align: left;
  border-bottom: 1px solid var(--line-soft);
  vertical-align: top;
}
tbody tr:last-child td {
  border-bottom: 0;
}
.name {
  font-weight: 600;
  color: var(--text);
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, "SF Mono", Menlo, monospace);
}
.req-dot {
  display: none;
}
code.type {
  color: #7c3aed;
  background: #f7f4ff;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 12px;
}
.flag {
  color: var(--faint);
  font-size: 12.5px;
}
.flag.on {
  color: var(--text-2);
  font-weight: 600;
}
.ex {
  color: var(--text-2);
  font-size: 12.5px;
}
.desc {
  color: var(--muted);
}
.body-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
}
.body-row .group-label {
  margin-bottom: 0;
}
.empty,
.meta {
  color: var(--faint);
  font-size: 13px;
}
.md,
.code {
  background: #f8fafc;
  padding: 12px 14px;
  border-radius: 8px;
  white-space: pre-wrap;
  font-size: 13px;
  line-height: 1.65;
  margin: 0;
  border: 1px solid var(--line-soft);
}
.resp {
  margin-top: 10px;
}
.resp-h {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 6px;
  font-size: 13px;
}
</style>
