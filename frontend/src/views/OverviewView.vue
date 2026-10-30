<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NButton, NEmpty, NGi, NGrid, NTag } from "naive-ui";
import { DocsApi, SpacesApi, type Document, type Space, type SpaceStats } from "@/api";
import { usePageLifecycle, useScrollMemory } from "@/composables/pageCache";
import { canEdit, documentPath, formatTime, sourceLabel } from "@/utils";
import { useSpaceId } from "@/composables/useRouteIds";

const route = useRoute();
const router = useRouter();
const spaceId = useSpaceId();
const space = ref<Space | null>(null);
const stats = ref<SpaceStats | null>(null);
const recent = ref<Document[]>([]);

async function load() {
  if (!spaceId.value) return;
  space.value = await SpacesApi.get(spaceId.value);
  stats.value = await SpacesApi.stats(spaceId.value);
  // 「最近文档」只列真正的文档，目录不进这个列表。
  const res = await DocsApi.list(spaceId.value, { page: 1, page_size: 6, is_folder: false });
  recent.value = res.items;
}

const cards = computed(() => [
  { label: "文档", value: stats.value?.document_count || 0 },
  { label: "知识分块", value: stats.value?.chunk_count || 0 },
  { label: "成员", value: stats.value?.member_count || 0 },
  { label: "网页资料", value: stats.value?.by_source?.web || 0 },
]);

watch(spaceId, load);
usePageLifecycle({ enter: load });
useScrollMemory();
</script>

<template>
  <div>
    <div class="page-head">
      <div>
        <div class="eyebrow">Overview</div>
        <h1 class="page-title">{{ space?.name || "空间总览" }}</h1>
        <p class="page-desc">文档、检索和问答都限定在当前空间内。</p>
      </div>
      <n-button v-if="canEdit(space?.role)" type="primary" @click="router.push(`/spaces/${spaceId}/ingest`)">收录知识</n-button>
    </div>

    <n-grid cols="2 800:4" :x-gap="16" :y-gap="16">
      <n-gi v-for="item in cards" :key="item.label">
        <div class="stat">
          <span>{{ item.label }}</span>
          <b class="num">{{ item.value }}</b>
        </div>
      </n-gi>
    </n-grid>

    <section class="panel list">
      <header>
        <span>最近文档</span>
        <n-button text type="primary" size="small" @click="router.push(`/spaces/${spaceId}/docs`)">查看全部</n-button>
      </header>
      <n-empty v-if="!recent.length" description="还没有文档，先去收录" style="padding: 32px 0" />
      <button v-for="doc in recent" :key="doc.id" class="row" @click="router.push(documentPath(spaceId, doc))">
        <span class="dot" />
        <div class="row-main">
          <strong>{{ doc.title }}</strong>
          <p>{{ formatTime(doc.updated_at) }}</p>
        </div>
        <n-tag size="small" :bordered="false">{{ sourceLabel[doc.source_type] }}</n-tag>
      </button>
    </section>
  </div>
</template>

<style scoped>
.stat {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 16px 18px;
  box-shadow: var(--shadow-sm);
}
.stat span {
  color: var(--muted);
  font-size: 12.5px;
}
.stat b {
  display: block;
  margin-top: 10px;
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.03em;
  line-height: 1;
}
.list {
  margin-top: 16px;
  padding: 6px 8px 10px;
}
.list header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 12px 8px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--faint);
}
.row {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 12px;
  border: 0;
  background: transparent;
  text-align: left;
  padding: 11px 12px;
  border-radius: 10px;
  cursor: pointer;
}
.row:hover {
  background: #f7f8fa;
}
.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #cbd5e1;
  flex: none;
  margin-left: 4px;
}
.row-main {
  flex: 1;
  min-width: 0;
}
.row strong {
  display: block;
  font-size: 13.5px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.row p {
  margin: 3px 0 0;
  color: var(--faint);
  font-size: 11.5px;
}
</style>
