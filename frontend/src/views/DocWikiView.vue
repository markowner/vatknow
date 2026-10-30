<script setup lang="ts">
import { computed, h, onUnmounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  NButton,
  NEmpty,
  NIcon,
  NInput,
  NSpin,
  NTag,
  useDialog,
  useMessage,
} from "naive-ui";
import {
  AddOutline,
  FolderOutline,
  SearchOutline,
  ChevronBackOutline,
} from "@vicons/ionicons5";
import { DocSearchApi, DocsApi, SpacesApi, type DocSearchHit, type Document, type Space } from "@/api";
import { canEdit, documentPath, formatTime, renderMarkdown, sourceLabel } from "@/utils";
import DocTree from "@/components/DocTree.vue";
import { usePageLifecycle, useScrollMemory } from "@/composables/pageCache";
import { useSpaceId } from "@/composables/useRouteIds";

const route = useRoute();
const router = useRouter();
const message = useMessage();
const dialog = useDialog();

const spaceId = useSpaceId();
const space = ref<Space | null>(null);
const docs = ref<Document[]>([]);
const loading = ref(false);
const activeId = ref<string | null>(null);

const keyword = ref("");
const searchHits = ref<DocSearchHit[] | null>(null);
const searching = ref(false);
let searchTimer: number | undefined;

const active = computed(() => docs.value.find((d) => d.id === activeId.value) || null);
const canWrite = computed(() => canEdit(space.value?.role));

// 列表接口不返回正文，选中后再按需拉取详情。
const detail = ref<Document | null>(null);
const detailLoading = ref(false);

watch(
  activeId,
  async (id) => {
    detail.value = null;
    if (!id) return;
    detailLoading.value = true;
    try {
      detail.value = await DocsApi.get(id);
    } catch (err) {
      message.error(err instanceof Error ? err.message : "读取文档失败");
    } finally {
      detailLoading.value = false;
    }
  },
  { immediate: true },
);

const bodyHtml = computed(() => {
  if (!detail.value || detail.value.source_type !== "markdown") return "";
  return renderMarkdown(detail.value.content_md || "", { stripTitle: detail.value.title });
});

async function load() {
  if (!spaceId.value) return;
  loading.value = true;
  try {
    const [s, first] = await Promise.all([
      SpacesApi.get(spaceId.value),
      DocsApi.list(spaceId.value, { page: 1, page_size: 100 }),
    ]);
    space.value = s;
    // 目录要完整，超过一页时继续拉取，避免树里缺节点。
    const items = [...first.items];
    const pages = Math.ceil(first.total / 100);
    for (let page = 2; page <= pages; page += 1) {
      const next = await DocsApi.list(spaceId.value, { page, page_size: 100 });
      items.push(...next.items);
    }
    docs.value = items;
  } catch (err) {
    message.error(err instanceof Error ? err.message : "加载失败");
  } finally {
    loading.value = false;
  }
}

function runSearch(value: string) {
  keyword.value = value;
  window.clearTimeout(searchTimer);
  if (!value.trim()) {
    searchHits.value = null;
    return;
  }
  searchTimer = window.setTimeout(async () => {
    searching.value = true;
    try {
      const res = await DocSearchApi.query(spaceId.value, value.trim());
      searchHits.value = res.items;
    } catch {
      searchHits.value = [];
    } finally {
      searching.value = false;
    }
  }, 260);
}

function open(doc: Document) {
  // API 文档有专门的编辑工作台，目录里点开直接跳过去。
  if (doc.source_type === "openapi") {
    router.push(`/spaces/${spaceId.value}/apis/${doc.id}`);
    return;
  }
  activeId.value = doc.id;
  router.replace(documentPath(spaceId.value, doc));
}

function editActive() {
  if (!active.value) return;
  router.push(`/spaces/${spaceId.value}/docs/${active.value.id}/edit`);
}

/** 搜索结果只带 id，需要回到目录里取到完整文档再打开；目录里没有说明已被过滤，直接跳详情。 */
function openHit(hit: DocSearchHit) {
  keyword.value = "";
  searchHits.value = null;
  const doc = docs.value.find((d) => d.id === hit.id);
  if (doc) {
    open(doc);
    return;
  }
  router.replace(`/spaces/${spaceId.value}/docs/${hit.id}`);
}

async function move(id: string, parentId: string | null) {
  try {
    const updated = await DocsApi.update(id, { parent_id: parentId, move_parent: true });
    const idx = docs.value.findIndex((d) => d.id === id);
    if (idx >= 0) docs.value[idx] = { ...docs.value[idx], parent_id: updated.parent_id };
    message.success("已移动");
  } catch (err) {
    message.error(err instanceof Error ? err.message : "移动失败");
  }
}

function newFolder() {
  // 必须用 ref：普通变量在每次重渲染时会被读回初始值，输入的字会立刻消失。
  const name = ref("");
  dialog.create({
    title: "新建目录",
    content: () =>
      h(NInput, {
        value: name.value,
        placeholder: "目录名称，例如：产品手册",
        onUpdateValue: (v: string) => (name.value = v),
        onKeydown: (e: KeyboardEvent) => {
          if (e.key === "Enter") e.preventDefault();
        },
      }),
    positiveText: "创建",
    negativeText: "取消",
    onPositiveClick: async () => {
      if (!name.value.trim()) {
        message.warning("请填写目录名称");
        return false;
      }
      await DocsApi.createFolder(spaceId.value, name.value.trim());
      await load();
      message.success("目录已创建");
    },
  });
}

function newDoc() {
  router.push(`/spaces/${spaceId.value}/ingest`);
}

function backToList() {
  router.push(`/spaces/${spaceId.value}/docs/all`);
}

// 支持直接访问 /docs/:docId，此时按当前路由高亮
watch(
  [spaceId, () => route.params.docId],
  ([, id]) => {
    activeId.value = typeof id === "string" && id ? id : null;
  },
  { immediate: true },
);

watch(spaceId, (id, prev) => {
  if (!id || !prev || id === prev) return;
  keyword.value = "";
  searchHits.value = null;
  load();
});

// 支持 /docs?q=安装 这样的深链，方便从别处带着检索词跳进来。
watch(
  () => route.query.q,
  (q) => {
    if (typeof q === "string" && q.trim() && q !== keyword.value) runSearch(q);
  },
  { immediate: true },
);

// 从别的页面切回来时重新拉列表，保证目录树不会停留在旧数据上。
usePageLifecycle({ enter: load });
onUnmounted(() => window.clearTimeout(searchTimer));
useScrollMemory();
</script>

<template>
  <div class="wiki">
    <aside class="sider">
      <div class="sider-head">
        <div class="space-name">{{ space?.name || "文档" }}</div>
        <div class="sider-actions">
          <n-button v-if="canWrite" size="tiny" quaternary @click="newFolder">
            <template #icon><n-icon><FolderOutline /></n-icon></template>
            目录
          </n-button>
          <n-button v-if="canWrite" size="tiny" quaternary @click="newDoc">
            <template #icon><n-icon><AddOutline /></n-icon></template>
            文档
          </n-button>
        </div>
      </div>

      <div class="sider-search">
        <n-input
          size="small"
          :value="keyword"
          placeholder="搜索全文"
          clearable
          @update:value="runSearch"
        >
          <template #prefix><n-icon size="14"><SearchOutline /></n-icon></template>
        </n-input>
      </div>

      <div class="sider-body">
        <n-spin :show="searching">
          <!-- 有搜索词时展示全文命中结果，否则展示目录树 -->
          <template v-if="keyword.trim()">
            <div v-if="searchHits && !searchHits.length" class="no-hit">
              <n-empty size="small" description="没有找到相关内容" />
            </div>
            <button
              v-for="hit in searchHits || []"
              :key="hit.id"
              class="hit"
              @click="openHit(hit)"
            >
              <div class="hit-title">
                <span>{{ hit.title }}</span>
                <span class="hit-type">{{ sourceLabel[hit.source_type] || hit.source_type }}</span>
              </div>
              <p v-if="hit.snippet" class="hit-snippet">{{ hit.snippet }}</p>
            </button>
          </template>
          <DocTree
            v-else
            :docs="docs"
            :active-id="activeId || undefined"
            :editable="canWrite"
            @open="open"
            @move="move"
          />
        </n-spin>
      </div>
    </aside>

    <main class="main">
      <template v-if="active">
        <div class="main-bar">
          <n-button size="tiny" quaternary class="back" @click="backToList">
            <template #icon><n-icon><ChevronBackOutline /></n-icon></template>
            全部文档
          </n-button>
          <n-tag size="small" :bordered="false">{{ sourceLabel[active.source_type] || active.source_type }}</n-tag>
          <n-tag v-if="active.published === false" size="small" :bordered="false" type="warning">草稿</n-tag>
          <span class="time">{{ formatTime(active.updated_at) }}</span>
          <div class="grow" />
          <n-button size="small" @click="editActive">编辑</n-button>
        </div>

        <n-spin :show="detailLoading">
          <article v-if="detail" class="paper">
            <h1>{{ detail.title }}</h1>
            <div v-if="detail.source_type === 'markdown'" class="md-body" v-html="bodyHtml" />
            <iframe
              v-else-if="detail.source_type === 'pdf'"
              class="pdf"
              :src="`/api/v1/documents/${detail.id}/file`"
              title="PDF"
            />
            <pre v-else class="plain">{{ detail.content_text }}</pre>
          </article>
        </n-spin>
      </template>
      <div v-else class="welcome">
        <div class="welcome-inner">
          <n-icon size="30" class="welcome-icon"><FolderOutline /></n-icon>
          <h2>选择一篇文档</h2>
          <p>左侧是目录，可以拖动文档到目录里整理；顶部的搜索会检索正文内容。</p>
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
.wiki {
  display: grid;
  grid-template-columns: 264px minmax(0, 1fr);
  gap: 0;
  margin: -26px -32px;
  height: 100vh;
  background: #f6f7f9;
}
.sider {
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--line);
  background: #fff;
  min-height: 0;
}
.sider-head {
  padding: 16px 14px 10px;
  border-bottom: 1px solid var(--line-soft);
}
.space-name {
  font-size: 13px;
  font-weight: 700;
  color: var(--text);
  margin-bottom: 10px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sider-actions {
  display: flex;
  gap: 4px;
}
.sider-search {
  padding: 10px 12px;
  border-bottom: 1px solid var(--line-soft);
}
.sider-body {
  flex: 1;
  overflow: auto;
  min-height: 0;
}
.no-hit {
  padding: 28px 8px;
}
.hit {
  display: block;
  width: 100%;
  text-align: left;
  border: 0;
  background: transparent;
  padding: 9px 12px;
  cursor: pointer;
  border-bottom: 1px solid var(--line-soft);
}
.hit:hover {
  background: var(--line-soft);
}
.hit-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-2);
}
.hit-type {
  font-size: 11px;
  color: var(--faint);
  font-weight: 400;
  flex: none;
}
.hit-snippet {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.6;
  color: var(--muted);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.main {
  min-width: 0;
  overflow: auto;
  padding: 22px 28px 40px;
}
.main-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}
.back {
  margin-left: -8px;
}
.time {
  font-size: 12.5px;
  color: var(--faint);
}
.grow {
  flex: 1;
}
.paper {
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 40px 48px 56px;
  max-width: 860px;
  box-shadow: var(--shadow-sm);
}
.paper h1 {
  margin: 0 0 20px;
  font-size: 27px;
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1.3;
}
.plain {
  white-space: pre-wrap;
  line-height: 1.8;
  color: var(--text-2);
  font-size: 14.5px;
}
.pdf {
  width: 100%;
  height: calc(100vh - 160px);
  border: 1px solid var(--line);
  border-radius: 12px;
  background: #fff;
}
.welcome {
  display: grid;
  place-items: center;
  height: 100%;
}
.welcome-inner {
  text-align: center;
  max-width: 380px;
}
.welcome-icon {
  color: #cbd5e1;
}
.welcome-inner h2 {
  margin: 12px 0 8px;
  font-size: 17px;
  font-weight: 650;
}
.welcome-inner p {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.7;
}
@media (max-width: 900px) {
  .wiki {
    grid-template-columns: 1fr;
    margin: -20px -16px;
  }
  .sider {
    border-right: 0;
    border-bottom: 1px solid var(--line);
    max-height: 42vh;
  }
}
</style>
