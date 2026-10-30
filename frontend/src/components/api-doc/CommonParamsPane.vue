<script setup lang="ts">
import { computed } from "vue";
import { NButton, NInput, NSelect, NSwitch, useMessage } from "naive-ui";
import { emptyCommonParam, type OpenParam } from "@/openapi";

/** 直接改传进来的数组：父组件用草稿副本，取消时才不会污染原文档。 */
const props = defineProps<{ params: OpenParam[] }>();
const message = useMessage();

const types = ["string", "integer", "number", "boolean"].map((value) => ({ label: value, value }));
// 公共参数对所有接口统一生效，path 参数没法定成公共的。
const locations = [
  { label: "Header", value: "header" },
  { label: "Query", value: "query" },
];

/** 常用名称列表，只是输入提示，下拉之外照样可以手打任意值。 */
const COMMON_HEADERS = [
  "Authorization",
  "Content-Type",
  "Accept",
  "Accept-Language",
  "User-Agent",
  "X-Api-Key",
  "X-Api-Version",
  "X-Tenant-Id",
  "X-Request-Id",
  "X-Trace-Id",
  "X-Timestamp",
  "X-Nonce",
  "X-Sign",
  "Cookie",
  "Referer",
  "Origin",
];
const COMMON_QUERIES = [
  "access_token",
  "api_key",
  "lang",
  "locale",
  "version",
  "client_id",
  "timestamp",
  "sign",
  "page",
  "page_size",
];

const unnamed = computed(() => props.params.some((item) => !item.name.trim()));

function nameOptions(param: OpenParam) {
  const list = param.in === "query" ? COMMON_QUERIES : COMMON_HEADERS;
  // 已经用过的名称不再提示，免得同一条重复加两次。
  const used = new Set(
    props.params.filter((item) => item !== param && item.name.trim()).map((item) => item.name.trim()),
  );
  return list
    .filter((name) => !used.has(name) || name === param.name.trim())
    .map((name) => ({ label: name, value: name }));
}

function add() {
  props.params.push(emptyCommonParam());
}

function remove(index: number) {
  props.params.splice(index, 1);
}

function toggleRequired(index: number, value: boolean) {
  const param = props.params[index];
  if (param) param.required = value;
}

/** 同位置重名会让请求里出现两个同名参数，保存前挡掉。 */
function checkDuplicate(index: number) {
  const param = props.params[index];
  if (!param || !param.name.trim()) return;
  const key = `${param.in}:${param.name.trim()}`;
  const clash = props.params.some(
    (item, i) => i !== index && item.name.trim() && `${item.in}:${item.name.trim()}` === key,
  );
  if (clash) message.warning(`「${param.name}」在 ${param.in} 里重复了`);
}
</script>

<template>
  <div class="common">
    <p class="hint">
      所有接口都会带上的参数，例如签名、租户标识、语言。接口里自己定义了同名同位置的参数时，以接口的定义为准。
    </p>
    <div class="head">
      <span>名称</span>
      <span>位置</span>
      <span>类型</span>
      <span>必填</span>
      <span>示例</span>
      <span>说明</span>
      <span />
    </div>
    <div v-for="(param, index) in params" :key="index" class="row">
      <n-select
        :value="param.name"
        size="small"
        filterable
        tag
        clearable
        :options="nameOptions(param)"
        placeholder="选常用或直接输入"
        :menu-props="{ style: 'min-width: 220px' }"
        @update:value="(v) => { param.name = String(v || ''); checkDuplicate(index); }"
      />
      <n-select v-model:value="param.in" size="small" :options="locations" />
      <n-select
        :value="param.schema?.type || 'string'"
        size="small"
        :options="types"
        @update:value="(v) => (param.schema = { ...param.schema, type: String(v) })"
      />
      <n-switch :value="Boolean(param.required)" size="small" @update:value="(v) => toggleRequired(index, Boolean(v))" />
      <n-input
        :value="String(param.schema?.example ?? '')"
        size="small"
        placeholder="示例值"
        @update:value="(v) => (param.schema = { ...param.schema, example: v })"
      />
      <n-input v-model:value="param.description" size="small" placeholder="说明" />
      <n-button size="tiny" quaternary type="error" @click="remove(index)">删</n-button>
    </div>
    <p v-if="!params.length" class="empty">还没有公共参数</p>
    <n-button size="small" dashed block @click="add">添加公共参数</n-button>
    <p v-if="unnamed" class="warn">有参数还没填名称，保存时会忽略。</p>
  </div>
</template>

<style scoped>
.hint {
  margin: 0 0 14px;
  color: var(--muted);
  font-size: 12.5px;
  line-height: 1.6;
}
.head,
.row {
  display: grid;
  grid-template-columns: 152px 96px 96px 52px 1fr 1.2fr 36px;
  gap: 8px;
  align-items: center;
}
.head {
  padding: 0 2px 6px;
  color: var(--faint);
  font-size: 12px;
}
.row {
  margin-bottom: 8px;
}
.empty {
  color: var(--faint);
  font-size: 13px;
  text-align: center;
  padding: 14px 0;
}
.warn {
  margin: 10px 0 0;
  color: #b45309;
  font-size: 12.5px;
}
</style>
