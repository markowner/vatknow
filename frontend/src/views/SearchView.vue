<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  NButton,
  NDrawer,
  NDrawerContent,
  NEmpty,
  NInput,
  NSpin,
  NTag,
  useMessage,
} from "naive-ui";
import { SearchApi, type SearchHit, type SearchLog } from "@/api";
import { canAdmin, formatTime, sourceLabel } from "@/utils";
import { usePageLifecycle, useScrollMemory } from "@/composables/pageCache";
import { useSpacesStore } from "@/stores/spaces";
import { useSpaceId } from "@/composables/useRouteIds";

const route = useRoute();
const router = useRouter();
const message = useMessage();
const spacesStore = useSpacesStore();
const spaceId = useSpaceId();
const q = ref("");
const loading = ref(false);
const hits = ref<SearchHit[] | null>(null);
const lastQuery = ref("");
const threadEl = ref<HTMLElement | null>(null);

/** 当前空间的角色决定能不能看全空间的历史。 */
const role = computed(() => spacesStore.items.find((s) => s.id === spaceId.value)?.role);
const isAdmin = computed(() => canAdmin(role.value));

const historyOpen = ref(false);
/** 管理员可以切换「只看自己」和「看全空间」。 */
const historyScope = ref<"self" | "space">("self");
const historyItems = ref<SearchLog[]>([]);
const historyTotal = ref(0);
const historyPage = ref(1);
const historyLoading = ref(false);
const pageSize = 20;

async function loadHistory() {
  if (!spaceId.value) return;
  historyLoading.value = true;
  try {
    const res = await SearchApi.logs(spaceId.value, historyPage.value, pageSize, historyScope.value);
    historyItems.value = res.items;
    historyTotal.value = res.total;
  } catch (err) {
    message.error(err instanceof Error ? err.message : "读取历史失败");
  } finally {
    historyLoading.value = false;
  }
}

function openHistory() {
  historyOpen.value = true;
  historyPage.value = 1;
  loadHistory();
}

function switchScope(scope: "self" | "space") {
  historyScope.value = scope;
  historyPage.value = 1;
  loadHistory();
}

/** 点历史条目就把当时的问题填回输入框并重新检索。 */
function reuseHistory(item: SearchLog) {
  historyOpen.value = false;
  q.value = item.query;
  search();
}

async function search() {
  const query = q.value.trim();
  if (!query || loading.value || !spaceId.value) return;
  loading.value = true;
  lastQuery.value = query;
  try {
    const res = await SearchApi.query(spaceId.value, query);
    hits.value = res.items;
    await nextTick();
    if (threadEl.value) threadEl.value.scrollTop = 0;
  } catch (err) {
    message.error(err instanceof Error ? err.message : "检索失败");
  } finally {
    loading.value = false;
  }
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    search();
  }
}

function clear() {
  hits.value = null;
  lastQuery.value = "";
  q.value = "";
}

/** API 文档有自己的工作台，检索结果不能直接扔到普通文档页。 */
function openHit(hit: SearchHit) {
  // 跨库检索的结果可能来自别的空间，必须跳到它自己的空间，否则会 403。
  const target = hit.space_id || spaceId.value;
  if (hit.source_type === "openapi") {
    router.push(`/spaces/${target}/apis/${hit.document_id}`);
    return;
  }
  router.push(`/spaces/${target}/docs/${hit.document_id}`);
}

/**
 * 切到别的空间时组件实例是复用的（keep-alive），不清理就会把上一个空间的
 * 检索结果留在页面上，点进去还会跳到错误的空间。
 */
watch(spaceId, (id, prev) => {
  if (!id || !prev || id === prev) return;
  hits.value = null;
  lastQuery.value = "";
  q.value = "";
  historyOpen.value = false;
  historyScope.value = "self";
  historyPage.value = 1;
  historyItems.value = [];
  historyTotal.value = 0;
});

// 切回本页时刷新一次历史，刚搜过的东西要能立刻看到。
usePageLifecycle({
  enter: () => {
    if (historyOpen.value) loadHistory();
  },
});
useScrollMemory();
</script>

<template>
  <div class="search-page">
    <div class="page-head">
      <div>
        <div class="eyebrow">Search</div>
        <h1 class="page-title">知识检索</h1>
        <p class="page-desc">在当前空间文档中搜索。Enter 检索，Shift + Enter 换行。</p>
      </div>
      <div class="head-actions">
        <n-button quaternary @click="openHistory">历史记录</n-button>
        <n-button v-if="hits" quaternary @click="clear">清空结果</n-button>
      </div>
    </div>

    <div class="panel shell">
      <div ref="threadEl" class="thread">
        <n-empty v-if="hits == null" description="在下方输入关键词或一句话，例如：权限模型怎么设计？" />
        <n-empty v-else-if="!hits.length" :description="`没有与「${lastQuery}」匹配的内容`" />
        <div v-else class="hits">
          <p class="meta">「{{ lastQuery }}」共 {{ hits.length }} 条</p>
          <article v-for="hit in hits" :key="hit.chunk_id" class="hit" @click="openHit(hit)">
            <div class="hit-title">
              {{ hit.document_title }}
              <n-tag v-if="hit.source_type" size="tiny" :bordered="false">{{ sourceLabel[hit.source_type] || hit.source_type }}</n-tag>
            </div>
            <p class="hit-body">{{ hit.content }}</p>
          </article>
        </div>
      </div>

      <div class="composer">
        <n-input
          v-model:value="q"
          type="textarea"
          placeholder="输入关键词或一段描述，在当前空间内检索…"
          :autosize="{ minRows: 3, maxRows: 10 }"
          @keydown="onKeydown"
        />
        <n-button type="primary" size="large" :loading="loading" :disabled="!q.trim()" @click="search">
          检索
        </n-button>
      </div>
    </div>

    <n-drawer v-model:show="historyOpen" :width="440" placement="right">
      <n-drawer-content title="检索历史" closable>
        <div v-if="isAdmin" class="scope-tabs">
          <button :class="{ on: historyScope === 'self' }" @click="switchScope('self')">我的</button>
          <button :class="{ on: historyScope === 'space' }" @click="switchScope('space')">全空间</button>
        </div>
        <n-spin :show="historyLoading">
          <n-empty v-if="!historyItems.length" description="还没有检索记录" />
          <div v-else class="history-list">
            <button v-for="item in historyItems" :key="item.id" class="history-item" @click="reuseHistory(item)">
              <div class="hi-top">
                <span class="hi-query">{{ item.query }}</span>
                <span class="hi-count">{{ item.hit_count }} 条</span>
              </div>
              <div class="hi-meta">
                <span>{{ formatTime(item.created_at) }}</span>
                <span v-if="historyScope === 'space' && item.user_name">· {{ item.user_name }}</span>
              </div>
              <div v-if="item.hits.length" class="hi-docs">
                {{ item.hits.slice(0, 3).map((h) => h.document_title).join("、") }}
                <span v-if="item.hits.length > 3">等 {{ item.hits.length }} 篇</span>
              </div>
            </button>
          </div>
        </n-spin>
        <div v-if="historyTotal > pageSize" class="pager">
          <n-button size="small" :disabled="historyPage <= 1" @click="historyPage -= 1; loadHistory()">上一页</n-button>
          <span>{{ historyPage }} / {{ Math.ceil(historyTotal / pageSize) }}</span>
          <n-button
            size="small"
            :disabled="historyPage >= Math.ceil(historyTotal / pageSize)"
            @click="historyPage += 1; loadHistory()"
          >
            下一页
          </n-button>
        </div>
      </n-drawer-content>
    </n-drawer>
  </div>
</template>

<style scoped>
.search-page {
  height: calc(100vh - 52px);
  display: flex;
  flex-direction: column;
}
.shell {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.thread {
  flex: 1;
  overflow: auto;
  padding: 22px 24px;
}
.meta {
  color: var(--muted);
  margin: 0 0 12px;
  font-size: 13px;
}
.hit {
  padding: 14px 16px;
  border: 1px solid var(--line);
  border-radius: 10px;
  margin-bottom: 10px;
  cursor: pointer;
  background: #fff;
  transition: border-color 0.15s, background 0.15s;
}
.hit:hover {
  border-color: #bfdbfe;
  background: #f8fbff;
}
.hit-title {
  font-weight: 600;
  margin-bottom: 6px;
  color: var(--text-1);
}
.hit-body {
  margin: 0;
  color: var(--text-2);
  line-height: 1.7;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.composer {
  display: grid;
  grid-template-columns: 1fr 96px;
  gap: 12px;
  align-items: end;
  padding: 14px 18px 18px;
  border-top: 1px solid var(--line-soft);
  background: #fafbfc;
}
.head-actions {
  display: flex;
  gap: 6px;
  flex: none;
}
.scope-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 14px;
  padding: 3px;
  background: var(--line-soft);
  border-radius: 9px;
}
.scope-tabs button {
  flex: 1;
  border: 0;
  background: transparent;
  padding: 6px 10px;
  border-radius: 7px;
  font-size: 13px;
  color: var(--muted);
  cursor: pointer;
}
.scope-tabs button.on {
  background: #fff;
  color: var(--text-1);
  font-weight: 600;
  box-shadow: var(--shadow-sm);
}
.history-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.history-item {
  display: block;
  width: 100%;
  text-align: left;
  border: 1px solid var(--line);
  background: #fff;
  border-radius: 10px;
  padding: 11px 13px;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}
.history-item:hover {
  border-color: #bfdbfe;
  background: #f8fbff;
}
.hi-top {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
}
.hi-query {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--text-1);
  word-break: break-word;
}
.hi-count {
  flex: none;
  font-size: 11.5px;
  color: var(--faint);
}
.hi-meta {
  margin-top: 4px;
  font-size: 11.5px;
  color: var(--faint);
}
.hi-docs {
  margin-top: 6px;
  font-size: 12px;
  color: var(--muted);
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-top: 16px;
  font-size: 12.5px;
  color: var(--muted);
}
</style>
