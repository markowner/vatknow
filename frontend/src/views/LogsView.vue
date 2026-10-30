<script setup lang="ts">
import { computed, h, reactive, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { NDataTable, NTabPane, NTabs, NTag, useMessage } from "naive-ui";
import type { DataTableColumns } from "naive-ui";
import { ChatApi, LogsApi, SearchApi, type AuditLog, type ChatLog, type SearchLog } from "@/api";
import { usePageLifecycle, useScrollMemory } from "@/composables/pageCache";
import { formatTime } from "@/utils";
import { useSpaceId } from "@/composables/useRouteIds";

const route = useRoute();
const message = useMessage();
const spaceId = useSpaceId();

/** 三个页签各自独立分页，切来切去不会互相冲掉页码。 */
const tab = ref<"audit" | "search" | "chat">("audit");

const audit = reactive({ rows: [] as AuditLog[], total: 0, page: 1, page_size: 20, loading: false });
const search = reactive({ rows: [] as SearchLog[], total: 0, page: 1, page_size: 20, loading: false });
const chat = reactive({ rows: [] as ChatLog[], total: 0, page: 1, page_size: 20, loading: false });

const auditColumns: DataTableColumns<AuditLog> = [
  { title: "时间", key: "created_at", width: 190, render: (row) => formatTime(row.created_at) },
  { title: "操作", key: "action", width: 140 },
  {
    title: "结果",
    key: "status_code",
    width: 90,
    render: (row) =>
      h(NTag, { size: "small", type: row.status_code < 400 ? "success" : "error", bordered: false }, { default: () => String(row.status_code) }),
  },
  { title: "方法", key: "method", width: 80 },
  { title: "路径", key: "path", ellipsis: { tooltip: true } },
  { title: "IP", key: "ip", width: 140, render: (row) => row.ip || "-" },
];

const searchColumns: DataTableColumns<SearchLog> = [
  { title: "时间", key: "created_at", width: 170, render: (row) => formatTime(row.created_at) },
  { title: "用户", key: "user_name", width: 120, render: (row) => row.user_name || "-" },
  { title: "检索词", key: "query", ellipsis: { tooltip: true } },
  {
    title: "命中",
    key: "hit_count",
    width: 80,
    render: (row) => h(NTag, { size: "small", bordered: false, type: row.hit_count ? "success" : "default" }, { default: () => String(row.hit_count) }),
  },
  {
    title: "命中文档",
    key: "hits",
    ellipsis: { tooltip: true },
    render: (row) => row.hits.map((item) => item.document_title).join("、") || "-",
  },
];

const chatColumns: DataTableColumns<ChatLog> = [
  { title: "时间", key: "created_at", width: 170, render: (row) => formatTime(row.created_at) },
  { title: "用户", key: "user_name", width: 120, render: (row) => row.user_name || "-" },
  { title: "问题", key: "question", ellipsis: { tooltip: true } },
  { title: "回答", key: "answer", ellipsis: { tooltip: true } },
  {
    title: "引用",
    key: "citations",
    width: 90,
    render: (row) =>
      h(
        NTag,
        { size: "small", bordered: false, type: row.citations.length ? "info" : "default" },
        { default: () => `${row.citations.length} 处` },
      ),
  },
];

async function loadAudit() {
  if (!spaceId.value) return;
  audit.loading = true;
  try {
    const res = await LogsApi.list(spaceId.value, audit.page, audit.page_size);
    audit.rows = res.items;
    audit.total = res.total;
  } catch (err) {
    message.error(err instanceof Error ? err.message : "加载日志失败，需要管理员权限");
  } finally {
    audit.loading = false;
  }
}

/** 管理页本身就要管理员权限，所以这里固定按全空间读，不用再切 self。 */
async function loadSearch() {
  if (!spaceId.value) return;
  search.loading = true;
  try {
    const res = await SearchApi.logs(spaceId.value, search.page, search.page_size, "space");
    search.rows = res.items;
    search.total = res.total;
  } catch (err) {
    message.error(err instanceof Error ? err.message : "加载检索日志失败");
  } finally {
    search.loading = false;
  }
}

async function loadChat() {
  if (!spaceId.value) return;
  chat.loading = true;
  try {
    const res = await ChatApi.logs(spaceId.value, chat.page, chat.page_size, "space");
    chat.rows = res.items;
    chat.total = res.total;
  } catch (err) {
    message.error(err instanceof Error ? err.message : "加载问答日志失败");
  } finally {
    chat.loading = false;
  }
}

function loadCurrent() {
  if (tab.value === "audit") loadAudit();
  else if (tab.value === "search") loadSearch();
  else loadChat();
}

// 只有真的换了空间才重置页码：离开本页时 id 变空、回来后又被填上，
// 那不是换空间，重置会把用户的分页位置白白清掉。
watch(spaceId, (id, prev) => {
  if (!id || !prev || id === prev) return;
  audit.page = 1;
  search.page = 1;
  chat.page = 1;
  loadCurrent();
});

// 切页签时才去拉那份数据，避免一进来就打三个请求。
watch(tab, loadCurrent);

usePageLifecycle({ enter: loadCurrent });
useScrollMemory();
</script>

<template>
  <div>
    <div class="page-head">
      <div>
        <div class="eyebrow">Audit</div>
        <h1 class="page-title">日志</h1>
        <p class="page-desc">
          记录本空间的写操作，以及检索、问答的完整历史。检索和问答是读取行为，不进操作日志，单独成表。仅管理员可见。
        </p>
      </div>
    </div>
    <div class="panel table-card">
      <n-tabs v-model:value="tab" type="line" animated>
        <n-tab-pane name="audit" tab="操作日志">
          <n-data-table
            :columns="auditColumns"
            :data="audit.rows"
            :loading="audit.loading"
            remote
            :bordered="false"
            :pagination="{
              page: audit.page,
              pageSize: audit.page_size,
              itemCount: audit.total,
              onChange: (page: number) => { audit.page = page; loadAudit(); },
              onUpdatePageSize: (size: number) => { audit.page_size = size; audit.page = 1; loadAudit(); },
              showSizePicker: true,
              pageSizes: [20, 50, 100],
            }"
          />
        </n-tab-pane>
        <n-tab-pane name="search" tab="检索日志">
          <n-data-table
            :columns="searchColumns"
            :data="search.rows"
            :loading="search.loading"
            remote
            :bordered="false"
            :pagination="{
              page: search.page,
              pageSize: search.page_size,
              itemCount: search.total,
              onChange: (page: number) => { search.page = page; loadSearch(); },
              onUpdatePageSize: (size: number) => { search.page_size = size; search.page = 1; loadSearch(); },
              showSizePicker: true,
              pageSizes: [20, 50, 100],
            }"
          />
        </n-tab-pane>
        <n-tab-pane name="chat" tab="问答日志">
          <n-data-table
            :columns="chatColumns"
            :data="chat.rows"
            :loading="chat.loading"
            remote
            :bordered="false"
            :pagination="{
              page: chat.page,
              pageSize: chat.page_size,
              itemCount: chat.total,
              onChange: (page: number) => { chat.page = page; loadChat(); },
              onUpdatePageSize: (size: number) => { chat.page_size = size; chat.page = 1; loadChat(); },
              showSizePicker: true,
              pageSizes: [20, 50, 100],
            }"
          />
        </n-tab-pane>
      </n-tabs>
    </div>
  </div>
</template>

<style scoped>
.table-card {
  padding: 6px 8px 8px;
  overflow: hidden;
}
:deep(.n-tabs-nav) {
  padding: 0 10px;
}
</style>
