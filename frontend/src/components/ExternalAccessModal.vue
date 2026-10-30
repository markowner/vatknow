<script setup lang="ts">
import { computed, ref, watch } from "vue";
import {
  NAlert,
  NButton,
  NCheckbox,
  NCheckboxGroup,
  NInput,
  NInputNumber,
  NModal,
  NRadioButton,
  NRadioGroup,
  NSpace,
  NSpin,
  NTag,
  useMessage,
} from "naive-ui";
import { DocsApi, SharesApi, type ShareLink } from "@/api";
import { parseOpenApi } from "@/openapi";

const props = defineProps<{
  show: boolean;
  spaceId: string;
  documentId: string;
  title?: string;
}>();
const emit = defineEmits<{ "update:show": [value: boolean] }>();

const message = useMessage();
const loading = ref(false);
const saving = ref(false);
const error = ref("");
const link = ref<ShareLink | null>(null);

const endpoints = ref<string[]>([]);
const scope = ref<"all" | "pick">("all");
const picked = ref<string[]>([]);
const password = ref("");
const usePassword = ref(false);
const expiresDays = ref<number | null>(null);
// 记录打开弹窗时的有效期，未改动就不提交，避免每次保存都把倒计时重置。
const initialExpires = ref<number | null>(null);

const selectedCount = computed(() => (scope.value === "all" ? endpoints.value.length : picked.value.length));

function remainingDays(value: string | null): number | null {
  if (!value) return null;
  const diff = new Date(value).getTime() - Date.now();
  if (diff <= 0) return null;
  return Math.max(1, Math.ceil(diff / 86400000));
}

function resetForm() {
  password.value = "";
  usePassword.value = Boolean(link.value?.has_password);
  // 必须回填剩余天数，否则保存时 clear_expiry 会把已有有效期悄悄清掉。
  expiresDays.value = remainingDays(link.value?.expires_at ?? null);
  initialExpires.value = expiresDays.value;
  scope.value = link.value?.endpoint_keys?.length ? "pick" : "all";
  picked.value = link.value?.endpoint_keys ? [...link.value.endpoint_keys] : [];
}

async function prepare() {
  loading.value = true;
  error.value = "";
  try {
    const [doc, existing] = await Promise.all([
      DocsApi.get(props.documentId),
      SharesApi.forDocument(props.spaceId, props.documentId),
    ]);
    endpoints.value =
      doc.source_type === "openapi" && doc.content_md
        ? (parseOpenApi(doc.content_md)?.ops || [])
            .filter((op) => op.status === "done")
            .map((op) => `${op.method} ${op.path}`)
        : [];
    link.value = existing;
    resetForm();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "无法读取外部链接";
  } finally {
    loading.value = false;
  }
}

function payload() {
  return {
    password: usePassword.value && password.value ? password.value : undefined,
    expires_days: expiresDays.value || undefined,
    endpoint_keys: scope.value === "pick" ? picked.value : null,
  };
}

async function create() {
  if (scope.value === "pick" && !picked.value.length) {
    error.value = "请至少选择一个接口";
    return;
  }
  saving.value = true;
  error.value = "";
  try {
    link.value = await SharesApi.create(props.spaceId, { document_id: props.documentId, ...payload() });
    message.success("外部链接已生成");
  } catch (err) {
    error.value = err instanceof Error ? err.message : "生成链接失败";
  } finally {
    saving.value = false;
  }
}

async function update() {
  if (!link.value) return;
  if (scope.value === "pick" && !picked.value.length) {
    error.value = "请至少选择一个接口";
    return;
  }
  saving.value = true;
  error.value = "";
  try {
    const body = payload();
    const expiryTouched = expiresDays.value !== initialExpires.value;
    link.value = await SharesApi.update(props.spaceId, link.value.id, {
      ...body,
      expires_days: expiryTouched ? body.expires_days : undefined,
      clear_password: !usePassword.value,
      clear_expiry: expiryTouched && !expiresDays.value,
      clear_endpoint_keys: scope.value === "all",
    });
    initialExpires.value = remainingDays(link.value.expires_at);
    message.success("设置已保存");
  } catch (err) {
    error.value = err instanceof Error ? err.message : "保存失败";
  } finally {
    saving.value = false;
  }
}

async function revoke() {
  if (!link.value) return;
  saving.value = true;
  try {
    await SharesApi.revoke(props.spaceId, link.value.id);
    link.value = null;
    resetForm();
    message.success("已关闭外部访问");
  } catch (err) {
    error.value = err instanceof Error ? err.message : "关闭链接失败";
  } finally {
    saving.value = false;
  }
}

async function copy() {
  if (!link.value) return;
  await navigator.clipboard.writeText(link.value.url);
  message.success("链接已复制");
}

function open() {
  window.open(link.value?.url, "_blank", "noopener");
}

watch(
  () => [props.show, props.documentId] as const,
  ([show]) => {
    if (show) prepare();
  },
  { immediate: true },
);
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    style="width: 560px"
    :title="`外部访问 · ${title || 'API 文档'}`"
    :bordered="false"
    @update:show="(value: boolean) => emit('update:show', value)"
  >
    <n-spin :show="loading">
      <n-alert v-if="error" type="error" :bordered="false" style="margin-bottom: 12px">{{ error }}</n-alert>

      <template v-if="link">
        <p class="lead">拿到链接的人无需登录即可查看。可以加密码、设有效期，或只开放部分接口。</p>
        <div class="row">
          <n-input :value="link.url" readonly />
          <n-button type="primary" ghost @click="copy">复制</n-button>
        </div>
        <div class="status">
          <n-tag v-if="link.has_password" size="small" :bordered="false" type="warning">需要密码</n-tag>
          <n-tag v-else size="small" :bordered="false">无需密码</n-tag>
          <n-tag v-if="link.expires_at" size="small" :bordered="false" type="info">
            有效期至 {{ new Date(link.expires_at).toLocaleDateString() }}
          </n-tag>
          <n-tag v-else size="small" :bordered="false">长期有效</n-tag>
          <n-tag size="small" :bordered="false" type="success">{{ selectedCount }} 个接口</n-tag>
        </div>
        <div class="foot">
          <n-button text type="primary" @click="open">在新窗口打开</n-button>
          <n-button text type="error" @click="revoke">关闭外部访问</n-button>
        </div>
      </template>

      <template v-else-if="!loading">
        <p class="lead">生成一个公开链接分享给外部调用方。只有标记为「已完成」的接口会出现在页面上。</p>
      </template>

      <div class="settings">
        <div class="field">
          <div class="label">访问密码</div>
          <n-radio-group v-model:value="usePassword" size="small">
            <n-radio-button :value="false">无需密码</n-radio-button>
            <n-radio-button :value="true">设置密码</n-radio-button>
          </n-radio-group>
          <n-input
            v-if="usePassword"
            v-model:value="password"
            type="password"
            show-password-on="click"
            :placeholder="link?.has_password ? '留空则保持现有密码' : '访问密码'"
            style="margin-top: 8px"
          />
        </div>

        <div class="field">
          <div class="label">有效期</div>
          <n-space align="center" :size="8">
            <n-input-number v-model:value="expiresDays" :min="1" :max="365" placeholder="长期有效" style="width: 160px" />
            <span class="unit">天</span>
            <n-button v-if="expiresDays" text type="primary" size="tiny" @click="expiresDays = null">清除</n-button>
          </n-space>
          <p class="tip">留空表示长期有效，从保存时开始计算。</p>
        </div>

        <div class="field">
          <div class="label">开放接口</div>
          <n-radio-group v-model:value="scope" size="small">
            <n-radio-button value="all">全部已完成（{{ endpoints.length }}）</n-radio-button>
            <n-radio-button value="pick" :disabled="!endpoints.length">仅指定接口</n-radio-button>
          </n-radio-group>
          <div v-if="scope === 'pick'" class="picker">
            <n-checkbox-group v-model:value="picked">
              <n-checkbox v-for="key in endpoints" :key="key" :value="key" :label="key" />
            </n-checkbox-group>
          </div>
          <p v-if="!endpoints.length" class="tip">这个项目还没有已完成的接口。</p>
        </div>
      </div>

      <div class="actions">
        <n-button v-if="link" type="primary" :loading="saving" @click="update">保存设置</n-button>
        <n-button v-else type="primary" :loading="saving" :disabled="loading" @click="create">生成外部访问链接</n-button>
      </div>
    </n-spin>
  </n-modal>
</template>

<style scoped>
.lead {
  margin: 0 0 12px;
  color: var(--text-2);
  font-size: 13.5px;
  line-height: 1.65;
}
.row {
  display: flex;
  gap: 8px;
}
.status {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 10px;
}
.foot {
  display: flex;
  justify-content: space-between;
  margin-top: 10px;
}
.settings {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--line-soft);
  display: grid;
  gap: 16px;
}
.label {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text-2);
  margin-bottom: 8px;
}
.tip {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--faint);
}
.unit {
  font-size: 13px;
  color: var(--muted);
}
.picker {
  margin-top: 10px;
  max-height: 200px;
  overflow: auto;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 10px 12px;
  display: grid;
  gap: 6px;
}
.picker :deep(.n-checkbox__label) {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
}
.actions {
  margin-top: 18px;
  display: flex;
  justify-content: flex-end;
}
</style>
