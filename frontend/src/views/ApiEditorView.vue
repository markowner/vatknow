<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  NButton,
  NCard,
  NForm,
  NFormItem,
  NInput,
  NSelect,
  NSpace,
  NSwitch,
  NTag,
  useMessage,
} from "naive-ui";
import { DocsApi } from "@/api";
import { emptyOp, emptySpec, methodColor, parseOpenApi, serializeOpenApi, type OpenSpec } from "@/openapi";
import { useDocId, useSpaceId } from "@/composables/useRouteIds";

const route = useRoute();
const router = useRouter();
const message = useMessage();
const spaceId = useSpaceId();
const docId = useDocId();
const creating = computed(() => !docId.value);
const saving = ref(false);
const spec = reactive<OpenSpec>(emptySpec());
const currentIndex = ref(0);
const current = computed(() => spec.ops[currentIndex.value] || null);
const methods = ["GET", "POST", "PUT", "PATCH", "DELETE"].map((value) => ({ label: value, value }));
const ins = ["query", "path", "header"].map((value) => ({ label: value, value }));
const types = ["string", "integer", "number", "boolean"].map((value) => ({ label: value, value }));

function loadSpec(next: OpenSpec) {
  spec.title = next.title;
  spec.version = next.version;
  spec.description = next.description;
  spec.notes = next.notes;
  spec.servers = next.servers.length ? next.servers : ["https://api.example.com"];
  spec.ops = next.ops;
  currentIndex.value = 0;
}

async function load() {
  if (!docId.value) {
    loadSpec(emptySpec());
    return;
  }
  const doc = await DocsApi.get(docId.value);
  const parsed = parseOpenApi(doc.content_md || "") || emptySpec();
  if (!parsed.title) parsed.title = doc.title;
  loadSpec(parsed);
}

function addOp() {
  spec.ops.push(emptyOp());
  currentIndex.value = spec.ops.length - 1;
}

function removeOp(index: number) {
  spec.ops.splice(index, 1);
  currentIndex.value = Math.max(0, Math.min(currentIndex.value, spec.ops.length - 1));
}

function addParam() {
  current.value?.parameters.push({ name: "", in: "query", required: false, description: "", schema: { type: "string" } });
}

function addResponse() {
  current.value?.responses.push({ status: "400", description: "失败", example: "" });
}

function toggleBody(on: boolean) {
  if (!current.value) return;
  current.value.body = on
    ? { contentType: "application/json", example: "{\n  \n}", required: true, description: "" }
    : undefined;
}

async function save() {
  if (!spec.title.trim()) {
    message.warning("请填写文档名称");
    return;
  }
  saving.value = true;
  try {
    const json = serializeOpenApi(spec);
    if (creating.value) {
      const doc = await DocsApi.openapi(spaceId.value, json, spec.title);
      message.success("已创建 API 文档");
      router.push(`/spaces/${spaceId.value}/apis/${doc.id}`);
    } else {
      await DocsApi.update(docId.value, { title: spec.title, content_md: json });
      message.success("已保存");
      router.push(`/spaces/${spaceId.value}/apis/${docId.value}`);
    }
  } catch (err) {
    message.error(err instanceof Error ? err.message : "保存失败");
  } finally {
    saving.value = false;
  }
}

watch(docId, load);
onMounted(load);
</script>

<template>
  <div>
    <n-space justify="space-between" style="margin-bottom: 16px">
      <div>
        <h2 style="margin: 0">{{ creating ? "新建 API 文档" : "编辑 API 文档" }}</h2>
        <p class="hint">在页面上添加接口、参数、说明和备注，不必手写 OpenAPI。</p>
      </div>
      <n-space>
        <n-button @click="router.push(docId ? `/spaces/${spaceId}/apis/${docId}` : `/spaces/${spaceId}/apis`)">取消</n-button>
        <n-button type="primary" :loading="saving" @click="save">保存</n-button>
      </n-space>
    </n-space>

    <n-card title="文档信息" style="margin-bottom: 16px">
      <n-form label-placement="top">
        <div class="row3">
          <n-form-item label="文档名称">
            <n-input v-model:value="spec.title" placeholder="例如 用户中心 API" />
          </n-form-item>
          <n-form-item label="版本">
            <n-input v-model:value="spec.version" placeholder="1.0.0" />
          </n-form-item>
          <n-form-item label="Base URL">
            <n-input v-model:value="spec.servers[0]" placeholder="https://api.example.com" />
          </n-form-item>
        </div>
        <n-form-item label="说明">
          <n-input v-model:value="spec.description" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }" placeholder="这份文档给谁用、认证方式、环境说明" />
        </n-form-item>
        <n-form-item label="备注">
          <n-input v-model:value="spec.notes" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }" placeholder="内部备注，不适合放进对外说明的内容" />
        </n-form-item>
      </n-form>
    </n-card>

    <div class="editor">
      <aside>
        <n-space justify="space-between" align="center">
          <strong>接口</strong>
          <n-button size="small" type="primary" @click="addOp">添加接口</n-button>
        </n-space>
        <button
          v-for="(op, index) in spec.ops"
          :key="index"
          class="op"
          :class="{ active: index === currentIndex }"
          @click="currentIndex = index"
        >
          <span class="m" :style="{ color: methodColor(op.method) }">{{ op.method }}</span>
          <span class="p">{{ op.summary || op.path }}</span>
        </button>
        <p v-if="!spec.ops.length" class="hint">还没有接口，点右上角添加。</p>
      </aside>
      <section v-if="current">
        <n-space justify="space-between">
          <h3 style="margin: 0">接口详情</h3>
          <n-button size="small" type="error" ghost @click="removeOp(currentIndex)">删除此接口</n-button>
        </n-space>
        <n-form label-placement="top" style="margin-top: 12px">
          <div class="row3">
            <n-form-item label="接口名称">
              <n-input v-model:value="current.summary" placeholder="获取用户资料" />
            </n-form-item>
            <n-form-item label="方法">
              <n-select v-model:value="current.method" :options="methods" />
            </n-form-item>
            <n-form-item label="路径">
              <n-input v-model:value="current.path" placeholder="/users/{id}" />
            </n-form-item>
          </div>
          <n-form-item label="分组">
            <n-input :value="current.tags[0]" placeholder="用户" @update:value="(v) => (current.tags = [v || '默认'])" />
          </n-form-item>
          <n-form-item label="说明">
            <n-input v-model:value="current.description" type="textarea" :autosize="{ minRows: 2, maxRows: 5 }" placeholder="这个接口做什么、调用注意点" />
          </n-form-item>
          <n-form-item label="备注">
            <n-input v-model:value="current.notes" type="textarea" :autosize="{ minRows: 2, maxRows: 5 }" placeholder="内部备注，例如负责人、未上线、临时字段" />
          </n-form-item>
        </n-form>

        <h4>请求参数</h4>
        <div v-for="(param, i) in current.parameters" :key="i" class="param">
          <n-input v-model:value="param.name" placeholder="字段名" />
          <n-select v-model:value="param.in" :options="ins" />
          <n-select :value="param.schema?.type || 'string'" :options="types" @update:value="(v) => (param.schema = { ...param.schema, type: v })" />
          <n-input v-model:value="param.description" placeholder="说明" />
          <n-tag :type="param.required ? 'error' : 'default'" :bordered="false" style="cursor: pointer" @click="param.required = !param.required">
            {{ param.required ? "必填" : "选填" }}
          </n-tag>
          <n-button size="small" quaternary @click="current.parameters.splice(i, 1)">删除</n-button>
        </div>
        <n-button size="small" @click="addParam">添加参数</n-button>

        <h4>
          请求体
          <n-switch :value="Boolean(current.body)" @update:value="toggleBody" style="margin-left: 8px" />
        </h4>
        <template v-if="current.body">
          <n-form-item label="说明">
            <n-input v-model:value="current.body.description" placeholder="请求体用途" />
          </n-form-item>
          <n-form-item label="示例 JSON">
            <n-input v-model:value="current.body.example" type="textarea" :autosize="{ minRows: 6, maxRows: 12 }" />
          </n-form-item>
        </template>

        <h4>响应</h4>
        <div v-for="(item, i) in current.responses" :key="i" class="resp">
          <n-input v-model:value="item.status" placeholder="200" style="width: 90px" />
          <n-input v-model:value="item.description" placeholder="说明" />
          <n-button size="small" quaternary @click="current.responses.splice(i, 1)">删除</n-button>
          <n-input v-model:value="item.example" type="textarea" :autosize="{ minRows: 3, maxRows: 8 }" placeholder="响应示例（可选）" class="full" />
        </div>
        <n-button size="small" @click="addResponse">添加响应</n-button>
      </section>
      <section v-else class="empty">点左侧「添加接口」，用表单填写路径、字段和说明。</section>
    </div>
  </div>
</template>

<style scoped>
.hint {
  color: #6b7280;
  margin: 6px 0 0;
}
.row3 {
  display: grid;
  grid-template-columns: 1.4fr 0.7fr 1.4fr;
  gap: 12px;
}
.editor {
  display: grid;
  grid-template-columns: 260px 1fr;
  gap: 16px;
  min-height: 560px;
}
aside,
section {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 16px;
}
.op {
  width: 100%;
  display: flex;
  gap: 8px;
  margin-top: 8px;
  padding: 8px;
  border: 0;
  background: transparent;
  border-radius: 8px;
  cursor: pointer;
  text-align: left;
}
.op.active,
.op:hover {
  background: #ecfdf5;
}
.m {
  width: 52px;
  font-size: 12px;
  font-weight: 800;
}
.p {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.param,
.resp {
  display: grid;
  grid-template-columns: 1fr 110px 110px 1.4fr auto auto;
  gap: 8px;
  margin-bottom: 8px;
  align-items: center;
}
.resp {
  grid-template-columns: 90px 1fr auto;
}
.resp .full {
  grid-column: 1 / -1;
}
h4 {
  margin: 20px 0 10px;
}
.empty {
  color: #6b7280;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
