<script setup lang="ts">
import { NButton, NInput, NTag, useMessage } from "naive-ui";
import { envNameFromUrl, type OpenEnv } from "@/openapi";

/** 直接改传进来的数组：父组件用草稿副本，取消时才不会污染原文档。 */
const props = defineProps<{ environments: OpenEnv[] }>();
const message = useMessage();

function add() {
  props.environments.push({ name: `环境 ${props.environments.length + 1}`, url: "" });
}

function remove(index: number) {
  if (props.environments.length <= 1) {
    message.warning("至少保留一个环境");
    return;
  }
  props.environments.splice(index, 1);
}

function setDefault(index: number) {
  const [item] = props.environments.splice(index, 1);
  props.environments.unshift(item);
}

/** 名称为空时用主机名兜底，避免保存出一堆无名环境。 */
function blurName(index: number) {
  const env = props.environments[index];
  if (env && !env.name.trim() && env.url.trim()) env.name = envNameFromUrl(env.url.trim());
}
</script>

<template>
  <div class="envs">
    <p class="hint">一套 Base URL 对应一个环境。列表第一项是默认环境，预览和调试默认用它。</p>
    <div class="head">
      <span>名称</span>
      <span>Base URL</span>
      <span />
    </div>
    <div v-for="(env, index) in environments" :key="index" class="row">
      <n-input v-model:value="env.name" size="small" placeholder="开发" @blur="blurName(index)" />
      <n-input v-model:value="env.url" size="small" placeholder="https://api.example.com" />
      <div class="ops">
        <n-tag v-if="index === 0" size="small" :bordered="false" type="success">默认</n-tag>
        <n-button v-else size="tiny" quaternary @click="setDefault(index)">设为默认</n-button>
        <n-button size="tiny" quaternary type="error" @click="remove(index)">删除</n-button>
      </div>
    </div>
    <n-button size="small" dashed block @click="add">添加环境</n-button>
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
  grid-template-columns: 160px 1fr 190px;
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
.ops {
  display: flex;
  gap: 4px;
  align-items: center;
  justify-content: flex-end;
}
</style>
