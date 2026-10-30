<script setup lang="ts">
import { computed, h, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NButton, NDataTable, NInput, NSelect, NSpace, NTag, useDialog, useMessage } from "naive-ui";
import type { DataTableColumns } from "naive-ui";
import { DocsApi, SpacesApi, type Document, type Space } from "@/api";
import { canEdit, documentPath, formatTime, sourceLabel } from "@/utils";
import { usePageLifecycle, useScrollMemory } from "@/composables/pageCache";
import { useSpaceId } from "@/composables/useRouteIds";

const route = useRoute();
const router = useRouter();
const message = useMessage();
const dialog = useDialog();
const spaceId = useSpaceId();
const space = ref<Space | null>(null);
const loading = ref(false);
const rows = ref<Document[]>([]);
const total = ref(0);
const query = reactive({ q: "", source_type: null as string | null, page: 1, page_size: 20 });

const columns = computed<DataTableColumns<Document>>(() => [
  {
    title: "标题",
    key: "title",
    ellipsis: { tooltip: true },
    render(row) {
      return h(
        "a",
        {
          style: "color:#2563eb;cursor:pointer",
          onClick: () =>
            router.push(documentPath(spaceId.value, row)),
        },
        row.title,
      );
    },
  },
  {
    title: "类型",
    key: "source_type",
    width: 120,
    render: (row) => h(NTag, { size: "small", bordered: false }, { default: () => sourceLabel[row.source_type] || row.source_type }),
  },
  {
    title: "发布",
    key: "published",
    width: 90,
    render: (row) => h(NTag, { size: "small", type: row.published === false ? "default" : "success", bordered: false }, { default: () => (row.published === false ? "草稿" : "已发布") }),
  },
  { title: "更新时间", key: "updated_at", width: 200, render: (row) => formatTime(row.updated_at) },
  {
    title: "操作",
    key: "actions",
    width: 160,
    render(row) {
      return h(NSpace, {}, {
        default: () => [
          h(
            NButton,
            {
              size: "small",
              onClick: () =>
                router.push(documentPath(spaceId.value, row)),
            },
            { default: () => "打开" },
          ),
          canEdit(space.value?.role)
            ? h(NButton, { size: "small", type: "error", ghost: true, onClick: () => remove(row) }, { default: () => "删除" })
            : null,
        ],
      });
    },
  },
]);

async function load() {
  if (!spaceId.value) return;
  loading.value = true;
  try {
    space.value = await SpacesApi.get(spaceId.value);
    const res = await DocsApi.list(spaceId.value, {
      q: query.q || undefined,
      source_type: query.source_type || undefined,
      is_folder: false,
      page: query.page,
      page_size: query.page_size,
    });
    rows.value = res.items;
    total.value = res.total;
  } catch (err) {
    message.error(err instanceof Error ? err.message : "加载失败");
  } finally {
    loading.value = false;
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
      message.success("目录已创建");
      await load();
    },
  });
}

function remove(row: Document) {
  dialog.warning({
    title: "删除文档",
    content: `确定删除「${row.title}」？对应分块也会删除。`,
    positiveText: "删除",
    negativeText: "取消",
    onPositiveClick: async () => {
      await DocsApi.remove(row.id);
      message.success("已删除");
      await load();
    },
  });
}

watch(spaceId, (id, prev) => {
  if (!id || !prev || id === prev) return;
  query.page = 1;
  load();
});
usePageLifecycle({ enter: load });
useScrollMemory();
</script>

<template>
  <div>
    <div class="page-head">
      <div>
        <div class="eyebrow">Documents</div>
        <h1 class="page-title">文档</h1>
        <p class="page-desc">空间内的全部资料，支持搜索与按来源筛选。</p>
      </div>
      <div v-if="canEdit(space?.role)" class="head-actions">
        <n-button @click="newFolder">新建目录</n-button>
        <n-button type="primary" @click="router.push(`/spaces/${spaceId}/ingest`)">收录</n-button>
      </div>
    </div>
    <div class="panel table-card">
      <div class="filters">
        <n-input v-model:value="query.q" placeholder="搜索标题" style="width: 220px" clearable @keyup.enter="query.page = 1; load()" />
        <n-select
          v-model:value="query.source_type"
          clearable
          placeholder="全部类型"
          style="width: 140px"
          :options="[
            { label: 'Markdown', value: 'markdown' },
            { label: 'PDF', value: 'pdf' },
            { label: '网页', value: 'web' },
            { label: 'API 文档', value: 'openapi' },
          ]"
          @update:value="query.page = 1; load()"
        />
        <n-button @click="query.page = 1; load()">筛选</n-button>
      </div>
      <n-data-table
        :columns="columns"
        :data="rows"
        :loading="loading"
        remote
        :bordered="false"
        :pagination="{
          page: query.page,
          pageSize: query.page_size,
          itemCount: total,
          onChange: (page: number) => { query.page = page; load(); },
          onUpdatePageSize: (size: number) => { query.page_size = size; query.page = 1; load(); },
          showSizePicker: true,
          pageSizes: [20, 50, 100],
        }"
      />
    </div>
  </div>
</template>

<style scoped>
.head-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.table-card {
  padding: 12px 12px 8px;
}
.filters {
  display: flex;
  gap: 8px;
  padding: 2px 2px 14px;
}
</style>
