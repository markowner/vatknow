<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NButton, NEmpty, NGi, NGrid, NTag } from "naive-ui";
import { DocsApi, type Document } from "@/api";
import { usePageLifecycle, useScrollMemory } from "@/composables/pageCache";
import { parseOpenApi } from "@/openapi";
import { formatTime } from "@/utils";
import ExternalAccessModal from "@/components/ExternalAccessModal.vue";
import { useSpaceId } from "@/composables/useRouteIds";

const route = useRoute();
const router = useRouter();
const spaceId = useSpaceId();
const docs = ref<Document[]>([]);
const loading = ref(false);
const sharing = ref<Document | null>(null);

function openShare(event: Event, doc: Document) {
  event.stopPropagation();
  sharing.value = doc;
}

async function load() {
  if (!spaceId.value) return;
  loading.value = true;
  try {
    const res = await DocsApi.list(spaceId.value, { source_type: "openapi", page: 1, page_size: 100 });
    docs.value = res.items;
  } finally {
    loading.value = false;
  }
}

function meta(doc: Document) {
  const fallback = doc.content_md ? parseOpenApi(doc.content_md) : null;
  return {
    endpoints: doc.endpoint_count ?? fallback?.ops.length ?? 0,
    version: doc.api_version || fallback?.version || "",
    desc: doc.api_summary || fallback?.description || "还没有说明，点进去添加接口即可。",
    server: doc.api_server || fallback?.servers[0] || "",
  };
}

watch(spaceId, load);
usePageLifecycle({ enter: load });
useScrollMemory();
</script>

<template>
  <div>
    <div class="page-head">
      <div>
        <div class="eyebrow">API Studio</div>
        <h1 class="page-title">API 文档</h1>
        <p class="page-desc">预览文档、编辑字段、在线调试，同一处完成。</p>
      </div>
      <div class="actions">
        <n-button @click="router.push(`/spaces/${spaceId}/ingest`)">导入 OpenAPI</n-button>
        <n-button type="primary" @click="router.push(`/spaces/${spaceId}/apis/new`)">新建项目</n-button>
      </div>
    </div>

    <div v-if="!loading && !docs.length" class="empty panel">
      <n-empty description="还没有 API 项目，可以直接在页面上添加接口。">
        <n-button type="primary" @click="router.push(`/spaces/${spaceId}/apis/new`)">新建项目</n-button>
      </n-empty>
    </div>
    <n-grid v-else cols="1 720:2 1120:3" :x-gap="16" :y-gap="16">
      <n-gi v-for="doc in docs" :key="doc.id">
        <article class="card" @click="router.push(`/spaces/${spaceId}/apis/${doc.id}`)">
          <div class="top">
            <h3>{{ doc.title }}</h3>
            <n-tag size="small" :bordered="false" type="info">{{ meta(doc).endpoints }} 个接口</n-tag>
          </div>
          <p class="desc">{{ meta(doc).desc }}</p>
          <div class="foot">
            <span v-if="meta(doc).version" class="chip">v{{ meta(doc).version }}</span>
            <code v-if="meta(doc).server" class="chip mono">{{ meta(doc).server }}</code>
            <button class="share" title="生成外部访问链接" @click="openShare($event, doc)">外链</button>
            <span class="time">{{ formatTime(doc.updated_at) }}</span>
          </div>
        </article>
      </n-gi>
    </n-grid>

    <ExternalAccessModal
      v-if="sharing"
      :show="Boolean(sharing)"
      :space-id="spaceId"
      :document-id="sharing.id"
      :title="sharing.title"
      @update:show="(value: boolean) => { if (!value) sharing = null }"
    />
  </div>
</template>

<style scoped>
.actions {
  display: flex;
  gap: 8px;
  flex: none;
}
.empty {
  padding: 64px 0;
}
.card {
  cursor: pointer;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 18px 18px 14px;
  min-height: 152px;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-sm);
  transition: transform 0.16s ease, box-shadow 0.16s ease, border-color 0.16s ease;
}
.card:hover {
  transform: translateY(-2px);
  border-color: #cfd8e6;
  box-shadow: var(--shadow-md);
}
.top {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: flex-start;
}
.top h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 650;
  letter-spacing: -0.01em;
  line-height: 1.4;
}
.desc {
  flex: 1;
  margin: 10px 0 16px;
  font-size: 13px;
  line-height: 1.65;
  color: var(--muted);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.foot {
  display: flex;
  gap: 6px;
  align-items: center;
  font-size: 11.5px;
  color: var(--faint);
  flex-wrap: wrap;
}
.chip {
  background: #f5f6f8;
  border: 1px solid var(--line-soft);
  padding: 1px 7px;
  border-radius: 6px;
  color: var(--text-2);
  max-width: 170px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.time {
  margin-left: auto;
}
.share {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 1px solid var(--line);
  background: #fff;
  color: var(--muted);
  font-size: 11.5px;
  padding: 2px 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: color 0.15s ease, border-color 0.15s ease, background 0.15s ease;
}
.share:hover {
  color: var(--accent);
  border-color: #bfdbfe;
  background: var(--accent-soft);
}
</style>
