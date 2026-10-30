<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { NButton, NCard, NInput, NList, NListItem, NSpace, NSpin } from "naive-ui";
import { PublicApi } from "@/api";
import { renderMarkdown, sourceLabel } from "@/utils";
import PublicApiDoc from "@/components/PublicApiDoc.vue";

const route = useRoute();
const loading = ref(true);
const error = ref("");
const needPassword = ref(false);
const password = ref("");
const meta = ref<{ title: string; source_type: string | null; need_password: boolean; expires_at: string | null } | null>(null);
const data = ref<{
  kind: string;
  space_name: string;
  title: string;
  source_type?: string;
  content_md?: string | null;
  content_text?: string;
  items?: Array<{ id: string; title: string; source_type: string; slug: string | null }>;
} | null>(null);

const token = computed(() => String(route.params.token));

async function loadMeta() {
  try {
    meta.value = await PublicApi.shareMeta(token.value);
    needPassword.value = meta.value.need_password;
  } catch (err) {
    error.value = err instanceof Error ? err.message : "分享无效";
  } finally {
    loading.value = false;
  }
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    data.value = await PublicApi.share(token.value, password.value || undefined);
    needPassword.value = false;
  } catch (err) {
    const msg = err instanceof Error ? err.message : "分享无效";
    if (msg.includes("密码")) needPassword.value = true;
    error.value = msg;
    data.value = null;
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  await loadMeta();
  if (error.value || needPassword.value) return;
  await load();
});
</script>

<template>
  <div class="wrap" :class="{ wide: data?.kind === 'document' && data?.source_type === 'openapi' }">
    <n-spin :show="loading">
      <div v-if="needPassword && !data" class="gate">
        <div class="gate-card">
          <div class="eyebrow">受保护的外部文档</div>
          <h1>{{ meta?.title || "该分享需要密码" }}</h1>
          <p class="gate-tip">请输入访问密码继续查看。</p>
          <n-space :size="8">
            <n-input
              v-model:value="password"
              type="password"
              show-password-on="click"
              placeholder="访问密码"
              style="width: 220px"
              @keyup.enter="load"
            />
            <n-button type="primary" :loading="loading" @click="load">打开</n-button>
          </n-space>
          <p v-if="error" class="gate-err">{{ error }}</p>
          <p v-if="meta?.expires_at" class="gate-tip">
            链接有效期至 {{ new Date(meta.expires_at).toLocaleDateString() }}
          </p>
        </div>
      </div>

      <div v-else-if="error && !data" class="gate">
        <div class="gate-card">
          <div class="eyebrow">外部文档</div>
          <h1>{{ error }}</h1>
          <p class="gate-tip">链接可能已被关闭、已过期，或需要重新向文档所有者索取。</p>
        </div>
      </div>

      <template v-else-if="data">
        <PublicApiDoc
          v-if="data.kind === 'document' && data.source_type === 'openapi'"
          :spec="data.content_md || ''"
        />
        <n-card v-else :title="data.title">
          <p class="hint">来自空间：{{ data.space_name }}</p>
          <template v-if="data.kind === 'document'">
            <div v-if="data.source_type === 'markdown'" class="md-body" v-html="renderMarkdown(data.content_md || '')" />
            <pre v-else class="plain">{{ data.content_text }}</pre>
          </template>
          <n-list v-else>
            <n-list-item v-for="item in data.items" :key="item.id">
              {{ item.title }} · {{ sourceLabel[item.source_type] || item.source_type }}
            </n-list-item>
          </n-list>
        </n-card>
      </template>
    </n-spin>
  </div>
</template>

<style scoped>
.wrap {
  max-width: 980px;
  margin: 32px auto;
  padding: 0 16px 48px;
}
.wrap.wide {
  max-width: 1180px;
}
.gate {
  display: grid;
  place-items: center;
  min-height: 68vh;
}
.gate-card {
  width: 100%;
  max-width: 440px;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 32px;
  box-shadow: var(--shadow-md);
}
.gate-card h1 {
  margin: 6px 0 8px;
  font-size: 20px;
  font-weight: 650;
  letter-spacing: -0.02em;
}
.eyebrow {
  font-size: 11px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--accent);
  font-weight: 600;
}
.gate-tip {
  color: var(--muted);
  font-size: 13px;
  line-height: 1.6;
  margin: 0 0 16px;
}
.gate-err {
  color: #dc2626;
  font-size: 13px;
  margin: 12px 0 0;
}
.hint {
  color: #6b7280;
  margin-top: 0;
}
.plain {
  white-space: pre-wrap;
  line-height: 1.7;
}
</style>
