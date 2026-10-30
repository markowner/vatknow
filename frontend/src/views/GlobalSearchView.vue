<script setup lang="ts">
import { nextTick, ref } from "vue";
import { useRouter } from "vue-router";
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
import { formatTime, sourceLabel } from "@/utils";
import { usePageLifecycle, useScrollMemory } from "@/composables/pageCache";

const router = useRouter();
const message = useMessage();
const q = ref("");
const loading = ref(false);
const hits = ref<SearchHit[] | null>(null);
const lastQuery = ref("");
const threadEl = ref<HTMLElement | null>(null);

/** 结果里出现过的空间，用来告诉用户这次都搜到了哪些库。 */
const hitSpaces = ref<string[]>([]);

const historyOpen = ref(false);
const historyItems = ref<SearchLog[]>([]);
const historyTotal = ref(0);
const historyPage = ref(1);
const historyLoading = ref(false);
const pageSize = 20;

async function loadHistory() {
  historyLoading.value = true;
  try {
    const res = await SearchApi.globalLogs(historyPage.value, pageSize);
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

async function search() {
  const query = q.value.trim();
  if (!query || loading.value) return;
  loading.value = true;
  lastQuery.value = query;
  try {
    const res = await SearchApi.queryAll(query);
    hits.value = res.items;
    // 按空间去重，保留入库顺序，让「搜到了哪几个库」一眼可见。
    hitSpaces.value = [...new Set(res.items.map((h) => h.space_name || "未知空间"))];
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
  hitSpaces.value = [];
}

function reuseHistory(item: SearchLog) {
  historyOpen.value = false;
  q.value = item.query;
  search();
}

/** 结果可能来自任意空间，必须跳到它自己的空间，否则会 403。 */
function openHit(hit: SearchHit) {
  const sid = hit.space_id;
  if (!sid) return;
  if (hit.source_type === "openapi") {
    router.push(`/spaces/${sid}/apis/${hit.document_id}`);
    return;
  }
  router.push(`/spaces/${sid}/docs/${hit.document_id}`);
}

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
        <div class="eyebrow">Global</div>
        <h1 class="page-title">全库检索</h1>
        <p class="page-desc">在你可见的所有空间里一次搜完，结果标注来源空间。Enter 检索，Shift + Enter 换行。</p>
      </div>
      <div class="head-actions">
        <n-button quaternary @click="openHistory">历史记录</n-button>
        <n-button v-if="hits" quaternary @click="clear">清空结果</n-button>
      </div>
    </div>

    <div class="panel shell">
      <div ref="threadEl" class="thread">
        <n-empty v-if="hits == null" description="输入关键词或一句话，在全部空间中检索，例如：权限模型怎么设计？" />
        <n-empty v-else-if="!hits.length" :description="`没有与「${lastQuery}」匹配的内容`" />
        <div v-else class="hits">
          <div class="meta-row">
            <p class="meta">「{{ lastQuery }}」共 {{ hits.length }} 条</p>
            <div class="space-chips">
              <n-tag v-for="name in hitSpaces" :key="name" size="tiny" :bordered="false" type="info">
                {{ name }}
              </n-tag>
            </div>
          </div>
          <article v-for="hit in hits" :key="hit.chunk_id" class="hit" @click="openHit(hit)">
            <div class="hit-title">
              {{ hit.document_title }}
              <n-tag size="tiny" :bordered="false" type="info">{{ hit.space_name || "未知空间" }}</n-tag>
              <n-tag v-if="hit.source_type" size="tiny" :bordered="false">
                {{ sourceLabel[hit.source_type] || hit.source_type }}
              </n-tag>
            </div>
            <p class="hit-body">{{ hit.content }}</p>
          </article>
        </div>
      </div>

      <div class="composer">
        <n-input
          v-model:value="q"
          type="textarea"
          placeholder="输入关键词或一段描述，在全部空间内检索…"
          :autosize="{ minRows: 3, maxRows: 10 }"
          @keydown="onKeydown"
        />
        <n-button type="primary" size="large" :loading="loading" :disabled="!q.trim()" @click="search">
          检索
        </n-button>
      </div>
    </div>

    <n-drawer v-model:show="historyOpen" :width="440" placement="right">
      <n-drawer-content title="全库检索历史" closable>
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
.meta-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.meta {
  color: var(--muted);
  margin: 0;
  font-size: 13px;
}
.space-chips {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
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
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
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
