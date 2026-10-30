<script setup lang="ts">
import { computed } from "vue";
import { NButton, NInput, NSelect, NSwitch } from "naive-ui";
import type { OpenParam } from "@/openapi";

const props = defineProps<{
  params: OpenParam[];
  location: "path" | "query" | "header";
  title: string;
  empty: string;
}>();
const emit = defineEmits<{ change: [] }>();
const types = ["string", "integer", "number", "boolean", "array", "object"].map((value) => ({ label: value, value }));
const rows = computed(() => props.params.map((item, index) => ({ item, index })).filter(({ item }) => item.in === props.location));

function add() {
  props.params.push({
    name: "",
    in: props.location,
    required: props.location === "path",
    description: "",
    schema: { type: "string", example: "" },
  });
  emit("change");
}

function remove(index: number) {
  props.params.splice(index, 1);
  emit("change");
}

function setExample(param: OpenParam, value: string) {
  param.schema = { ...param.schema, example: value };
  emit("change");
}

function setType(param: OpenParam, value: string) {
  param.schema = { ...param.schema, type: value };
  emit("change");
}
</script>

<template>
  <div class="block">
    <div class="hd">
      <b>{{ title }}</b>
      <n-button size="tiny" secondary @click="add">添加</n-button>
    </div>
    <table>
      <thead>
        <tr>
          <th style="width: 18%">名称</th>
          <th style="width: 120px">类型</th>
          <th style="width: 72px">必填</th>
          <th style="width: 18%">示例</th>
          <th>说明</th>
          <th style="width: 56px" />
        </tr>
      </thead>
      <tbody>
        <tr v-if="!rows.length">
          <td colspan="6" class="empty">{{ empty }}</td>
        </tr>
        <tr v-for="row in rows" :key="row.index">
          <td><n-input v-model:value="row.item.name" size="small" placeholder="字段名" @update:value="emit('change')" /></td>
          <td>
            <n-select
              size="small"
              :value="row.item.schema?.type || 'string'"
              :options="types"
              @update:value="(v) => setType(row.item, String(v))"
            />
          </td>
          <td>
            <n-switch size="small" :value="Boolean(row.item.required)" @update:value="(v) => { row.item.required = v; emit('change') }" />
          </td>
          <td>
            <n-input
              size="small"
              :value="String(row.item.schema?.example ?? '')"
              placeholder="示例"
              @update:value="(v) => setExample(row.item, v)"
            />
          </td>
          <td><n-input v-model:value="row.item.description" size="small" placeholder="说明" @update:value="emit('change')" /></td>
          <td><n-button size="tiny" quaternary type="error" @click="remove(row.index)">删</n-button></td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.block {
  margin: 0 0 12px;
  border: 1px solid var(--line);
  border-radius: 12px;
  overflow: hidden;
  background: #fff;
}
.hd {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 9px 12px;
  background: #fafbfc;
  border-bottom: 1px solid var(--line-soft);
}
.hd b {
  font-size: 12.5px;
  font-weight: 650;
  color: var(--text-2);
}
table {
  width: 100%;
  border-collapse: collapse;
}
th,
td {
  padding: 8px 10px;
  text-align: left;
  font-size: 13px;
  border-top: 1px solid var(--line-soft);
}
thead th {
  border-top: 0;
}
th {
  color: var(--faint);
  font-weight: 500;
  font-size: 12px;
}
.empty {
  color: var(--faint);
  text-align: center;
  padding: 16px;
}
</style>
