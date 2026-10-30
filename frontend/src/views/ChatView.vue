<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  NButton,
  NDrawer,
  NDrawerContent,
  NEmpty,
  NInput,
  NSpace,
  NSpin,
  NTag,
  useMessage,
} from "naive-ui";
import { ChatApi, type ChatLog, type Citation } from "@/api";
import { canAdmin, formatTime } from "@/utils";
import { usePageLifecycle, useScrollMemory } from "@/composables/pageCache";
import { useSpacesStore } from "@/stores/spaces";
import { useSpaceId } from "@/composables/useRouteIds";

type Turn = { role: "user" | "assistant"; content: string; citations?: Citation[] };

const route = useRoute();
const router = useRouter();
const message = useMessage();
const spacesStore = useSpacesStore();
const spaceId = useSpaceId();
const question = ref("");
const loading = ref(false);
const turns = ref<Turn[]>([]);
const threadEl = ref<HTMLElement | null>(null);

const role = computed(() => spacesStore.items.find((s) => s.id === spaceId.value)?.role);
const isAdmin = computed(() => canAdmin(role.value));

const historyOpen = ref(false);
const historyScope = ref<"self" | "space">("self");
const historyItems = ref<ChatLog[]>([]);
const historyTotal = ref(0);
const historyPage = ref(1);
const historyLoading = ref(false);
const pageSize = 20;

async function loadHistory() {
  if (!spaceId.value) return;
  historyLoading.value = true;
  try {
    const res = await ChatApi.logs(spaceId.value, historyPage.value, pageSize, historyScope.value);
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

/** 点历史条目把问题和当时的回答一起放回会话里，方便接着追问。 */
function reuseHistory(item: ChatLog) {
  historyOpen.value = false;
  turns.value.push({ role: "user", content: item.question });
  turns.value.push({
    role: "assistant",
    content: item.answer,
    citations: item.citations.map((c) => ({ ...c, chunk_id: c.document_id, snippet: "" })),
  });
  scrollBottom();
}

async function scrollBottom() {
  await nextTick();
  if (threadEl.value) threadEl.value.scrollTop = threadEl.value.scrollHeight;
}

async function ask() {
  const q = question.value.trim();
  if (!q || loading.value || !spaceId.value) return;
  question.value = "";
  const history = turns.value.map((t) => ({ role: t.role, content: t.content }));
  turns.value.push({ role: "user", content: q });
  await scrollBottom();
  loading.value = true;
  try {
    const res = await ChatApi.ask(spaceId.value, q, history);
    turns.value.push({ role: "assistant", content: res.answer, citations: res.citations });
  } catch (err) {
    message.error(err instanceof Error ? err.message : "问答失败");
  } finally {
    loading.value = false;
    await scrollBottom();
  }
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    ask();
  }
}

function clear() {
  turns.value = [];
}

/**
 * 切到别的空间时组件实例是复用的（keep-alive），不清空就会把上一个空间的
 * 对话留在页面上，追问时还会用错空间的上下文。
 */
watch(spaceId, (id, prev) => {
  if (!id || !prev || id === prev) return;
  turns.value = [];
  question.value = "";
  historyOpen.value = false;
  historyScope.value = "self";
  historyPage.value = 1;
  historyItems.value = [];
  historyTotal.value = 0;
});

// 切回本页时刷新一次历史，刚问过的东西要能立刻看到。
usePageLifecycle({
  enter: () => {
    if (historyOpen.value) loadHistory();
  },
});
useScrollMemory();
</script>

<template>
  <div class="chat-page">
    <div class="page-head">
      <div>
        <div class="eyebrow">Chat</div>
        <h1 class="page-title">知识库问答</h1>
        <p class="page-desc">只根据当前空间文档作答，并附带来源。Enter 发送，Shift + Enter 换行。</p>
      </div>
      <div class="head-actions">
        <n-button quaternary @click="openHistory">历史记录</n-button>
        <n-button v-if="turns.length" quaternary @click="clear">清空会话</n-button>
      </div>
    </div>

    <div class="panel shell">
      <div ref="threadEl" class="thread">
        <n-empty v-if="!turns.length" description="在下方输入问题，例如：这份资料的核心结论是什么？" />
        <div v-for="(turn, idx) in turns" :key="idx" class="turn" :class="turn.role">
          <div class="chat-bubble" :class="turn.role">{{ turn.content }}</div>
          <n-space v-if="turn.citations?.length" class="cites" :size="8">
            <n-tag
              v-for="c in turn.citations"
              :key="c.chunk_id"
              size="small"
              round
              style="cursor: pointer"
              @click="router.push(`/spaces/${spaceId}/docs/${c.document_id}`)"
            >
              {{ c.document_title }}
            </n-tag>
          </n-space>
        </div>
        <div v-if="loading" class="turn assistant">
          <div class="chat-bubble assistant">正在检索知识库并生成回答…</div>
        </div>
      </div>

      <div class="composer">
        <n-input
          v-model:value="question"
          type="textarea"
          placeholder="向知识库提问，可输入较长的问题或粘贴一段文字…"
          :autosize="{ minRows: 3, maxRows: 10 }"
          @keydown="onKeydown"
        />
        <n-button type="primary" size="large" :loading="loading" :disabled="!question.trim()" @click="ask">
          发送
        </n-button>
      </div>
    </div>

    <n-drawer v-model:show="historyOpen" :width="480" placement="right">
      <n-drawer-content title="问答历史" closable>
        <div v-if="isAdmin" class="scope-tabs">
          <button :class="{ on: historyScope === 'self' }" @click="switchScope('self')">我的</button>
          <button :class="{ on: historyScope === 'space' }" @click="switchScope('space')">全空间</button>
        </div>
        <n-spin :show="historyLoading">
          <n-empty v-if="!historyItems.length" description="还没有问答记录" />
          <div v-else class="history-list">
            <button v-for="item in historyItems" :key="item.id" class="history-item" @click="reuseHistory(item)">
              <div class="hi-q">{{ item.question }}</div>
              <div class="hi-a">{{ item.answer }}</div>
              <div class="hi-meta">
                <span>{{ formatTime(item.created_at) }}</span>
                <span v-if="historyScope === 'space' && item.user_name">· {{ item.user_name }}</span>
                <span v-if="item.citations.length">· {{ item.citations.length }} 处引用</span>
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
.chat-page {
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
.turn {
  margin-bottom: 16px;
  display: flex;
  flex-direction: column;
}
.turn.user {
  align-items: flex-end;
}
.turn.assistant {
  align-items: flex-start;
}
.cites {
  margin-top: 8px;
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
.hi-q {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--text-1);
  word-break: break-word;
}
.hi-a {
  margin-top: 5px;
  font-size: 12.5px;
  color: var(--text-2);
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.hi-meta {
  margin-top: 7px;
  font-size: 11.5px;
  color: var(--faint);
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
