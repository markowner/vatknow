<script setup lang="ts">
import { computed } from "vue";
import { NButton, NForm, NFormItem, NGi, NGrid, NInput, NSelect, NSpace } from "naive-ui";
import ParamTable from "./ParamTable.vue";
import { type OpenOp, type OpenSpec } from "@/openapi";

const props = defineProps<{ spec: OpenSpec; op: OpenOp }>();
const emit = defineEmits<{ change: [] }>();

const methods = ["GET", "POST", "PUT", "PATCH", "DELETE"].map((value) => ({ label: value, value }));
const statuses = [
  { label: "未完成", value: "undone" },
  { label: "已完成", value: "done" },
];
const cats = computed(() => props.spec.categories.map((value) => ({ label: value, value })));

function onChange() {
  emit("change");
}

function syncPath() {
  const names = [...props.op.path.matchAll(/\{([^}/]+)\}/g)].map((item) => item[1]);
  for (const name of names) {
    if (!props.op.parameters.some((item) => item.in === "path" && item.name === name)) {
      props.op.parameters.push({ name, in: "path", required: true, description: "", schema: { type: "string" } });
    }
  }
  onChange();
}

function setTag(value: string) {
  props.op.tags = [value || "公共分类"];
  onChange();
}

function enableBody() {
  if (!props.op.body) {
    props.op.body = { contentType: "application/json", example: "{\n  \n}", required: true, description: "" };
  } else {
    props.op.body = undefined;
  }
  onChange();
}

function addResp() {
  props.op.responses.push({ status: "400", description: "", example: "" });
  onChange();
}

function prettyBody() {
  if (!props.op.body) return;
  try {
    props.op.body.example = JSON.stringify(JSON.parse(props.op.body.example || "{}"), null, 2);
    onChange();
  } catch {
    /* keep raw */
  }
}
</script>

<template>
  <div class="edit">
    <section class="card">
      <div class="card-h">基本信息</div>
      <n-form label-placement="top">
        <n-grid cols="2" :x-gap="16">
          <n-gi>
            <n-form-item label="接口名称">
              <n-input v-model:value="op.summary" placeholder="获取用户信息" @update:value="onChange" />
            </n-form-item>
          </n-gi>
          <n-gi>
            <n-form-item label="接口路径">
              <div class="pathline">
                <n-select v-model:value="op.method" :options="methods" style="width: 110px" @update:value="onChange" />
                <n-input v-model:value="op.path" placeholder="/user/{id}" @blur="syncPath" @update:value="onChange" />
              </div>
            </n-form-item>
          </n-gi>
          <n-gi>
            <n-form-item label="分类">
              <n-select :value="op.tags[0]" :options="cats" @update:value="(v) => setTag(String(v))" />
            </n-form-item>
          </n-gi>
          <n-gi>
            <n-form-item label="状态">
              <n-select v-model:value="op.status" :options="statuses" @update:value="onChange" />
            </n-form-item>
          </n-gi>
        </n-grid>
        <n-form-item label="说明（给调用方看）">
          <n-input v-model:value="op.description" type="textarea" :autosize="{ minRows: 3, maxRows: 8 }" placeholder="做什么、鉴权、分页、错误码" @update:value="onChange" />
        </n-form-item>
        <n-form-item label="备注（内部看）">
          <n-input v-model:value="op.notes" type="textarea" :autosize="{ minRows: 2, maxRows: 5 }" placeholder="负责人、是否上线" @update:value="onChange" />
        </n-form-item>
      </n-form>
    </section>

    <div class="card-h">请求参数</div>
    <ParamTable :params="op.parameters" location="path" title="Path" empty="路径写成 /user/{id}，失焦后自动生成" @change="onChange" />
    <ParamTable :params="op.parameters" location="query" title="Query" empty="没有 Query 参数" @change="onChange" />
    <ParamTable :params="op.parameters" location="header" title="Headers" empty="没有 Header" @change="onChange" />

    <section class="card">
      <div class="hd">
        <div class="card-h" style="margin: 0">Body</div>
        <n-space>
          <n-button v-if="op.body" size="tiny" @click="prettyBody">格式化 JSON</n-button>
          <n-button size="tiny" @click="enableBody">{{ op.body ? "删除 Body" : "添加 JSON Body" }}</n-button>
        </n-space>
      </div>
      <template v-if="op.body">
        <n-form label-placement="top">
          <n-grid cols="2" :x-gap="16">
            <n-gi><n-form-item label="类型"><n-input v-model:value="op.body.contentType" @update:value="onChange" /></n-form-item></n-gi>
            <n-gi><n-form-item label="说明"><n-input v-model:value="op.body.description" @update:value="onChange" /></n-form-item></n-gi>
          </n-grid>
          <n-form-item label="示例">
            <n-input v-model:value="op.body.example" type="textarea" :autosize="{ minRows: 8, maxRows: 16 }" @update:value="onChange" />
          </n-form-item>
        </n-form>
      </template>
      <p v-else class="empty">该接口没有请求体</p>
    </section>

    <section class="card">
      <div class="hd">
        <div class="card-h" style="margin: 0">返回数据</div>
        <n-button size="tiny" @click="addResp">添加响应</n-button>
      </div>
      <div v-for="(item, i) in op.responses" :key="i" class="resp">
        <div class="pathline">
          <n-input v-model:value="item.status" style="width: 90px" placeholder="200" @update:value="onChange" />
          <n-input v-model:value="item.description" placeholder="说明" @update:value="onChange" />
          <n-button size="tiny" quaternary type="error" @click="op.responses.splice(i, 1); onChange()">删除</n-button>
        </div>
        <n-input v-model:value="item.example" type="textarea" :autosize="{ minRows: 4, maxRows: 10 }" placeholder="返回示例 JSON" @update:value="onChange" />
      </div>
    </section>
  </div>
</template>

<style scoped>
.edit {
  display: grid;
  gap: 14px;
  padding: 8px 0 32px;
}
.card {
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 18px;
  background: #fff;
}
.card-h {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13.5px;
  font-weight: 650;
  color: var(--text);
  margin-bottom: 8px;
}
.card-h::before {
  content: "";
  width: 3px;
  height: 13px;
  border-radius: 2px;
  background: var(--accent);
}
.pathline,
.hd {
  display: flex;
  gap: 8px;
  align-items: center;
  width: 100%;
}
.hd {
  justify-content: space-between;
  margin-bottom: 10px;
}
.resp {
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 10px;
  margin-bottom: 10px;
  background: #fafbfc;
}
.empty {
  color: var(--faint);
  font-size: 13px;
  margin: 0;
}
</style>
