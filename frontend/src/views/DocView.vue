<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NButton, NDropdown, NInput, NSpin, NSwitch, NTag, useDialog, useMessage } from "naive-ui";
import { DocsApi, SharesApi, SpacesApi, type Document, type Space } from "@/api";
import { canEdit, formatTime, renderMarkdown, sourceLabel } from "@/utils";
import { usePageLifecycle } from "@/composables/pageCache";
import { useSpaceId, useDocId } from "@/composables/useRouteIds";

const route = useRoute();
const router = useRouter();
const message = useMessage();
const dialog = useDialog();
const spaceId = useSpaceId();
const docId = useDocId();
const space = ref<Space | null>(null);
const doc = ref<Document | null>(null);
const title = ref("");
const content = ref("");
const slug = ref("");
const published = ref(true);
const editing = ref(false);
const saving = ref(false);

async function load() {
  if (!spaceId.value || !docId.value) return;
  space.value = await SpacesApi.get(spaceId.value);
  doc.value = await DocsApi.get(docId.value);
  if (doc.value.source_type === "openapi") {
    await router.replace(`/spaces/${spaceId.value}/apis/${doc.value.id}`);
    return;
  }
  title.value = doc.value.title;
  content.value = doc.value.content_md || doc.value.content_text || "";
  slug.value = doc.value.slug || "";
  published.value = doc.value.published !== false;
  editing.value = route.path.endsWith("/edit");
}

async function save() {
  if (!doc.value) return;
  saving.value = true;
  try {
    doc.value = await DocsApi.update(doc.value.id, {
      title: title.value,
      slug: slug.value || null,
      published: published.value,
      content_md: doc.value.source_type === "markdown" ? content.value : undefined,
    });
    editing.value = false;
    message.success("已保存并重新索引");
    router.replace(`/spaces/${spaceId.value}/docs/${doc.value.id}`);
  } catch (err) {
    message.error(err instanceof Error ? err.message : "保存失败");
  } finally {
    saving.value = false;
  }
}

async function togglePublish(value: boolean) {
  if (!doc.value) return;
  try {
    doc.value = await DocsApi.update(doc.value.id, { published: value });
    published.value = value;
    message.success(value ? "已发布，公开空间可见" : "已取消发布");
  } catch (err) {
    published.value = !value;
    message.error(err instanceof Error ? err.message : "更新失败");
  }
}

async function shareDoc() {
  try {
    const link = await SharesApi.create(spaceId.value, { document_id: docId.value });
    const url = link.url.replace(":8000", ":3000");
    await navigator.clipboard.writeText(url);
    message.success("分享链接已复制");
  } catch (err) {
    message.error(err instanceof Error ? err.message : "创建分享失败");
  }
}

function remove() {
  dialog.warning({
    title: "删除文档",
    content: "删除后不可恢复。",
    positiveText: "删除",
    negativeText: "取消",
    onPositiveClick: async () => {
      await DocsApi.remove(docId.value);
      message.success("已删除");
      router.replace(`/spaces/${spaceId.value}/docs`);
    },
  });
}

function onMore(key: string) {
  if (key === "share") shareDoc();
  if (key === "delete") remove();
}

function onKey(e: KeyboardEvent) {
  if (editing.value && (e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") {
    e.preventDefault();
    save();
  }
}

watch([spaceId, docId], load);
// 这里可能有正在编辑、还没保存的正文，切回来不能重拉数据把它冲掉，
// 只需要把全局 ⌘S 监听跟着页面进出。
usePageLifecycle({
  enter: () => window.addEventListener("keydown", onKey),
  leave: () => window.removeEventListener("keydown", onKey),
});
</script>

<template>
  <n-spin :show="!doc">
    <div v-if="doc" class="page">
      <header class="bar">
        <button class="back" @click="router.push(`/spaces/${spaceId}/docs/${docId}`)">← 文档</button>
        <n-tag size="small" :bordered="false">{{ sourceLabel[doc.source_type] }}</n-tag>
        <n-tag size="small" :bordered="false" :type="published ? 'success' : 'default'">
          {{ published ? "已发布" : "草稿" }}
        </n-tag>
        <span class="time">{{ formatTime(doc.updated_at) }}</span>
        <div class="grow" />
        <template v-if="canEdit(space?.role)">
          <label class="pub">
            发布
            <n-switch size="small" :value="published" @update:value="togglePublish" />
          </label>
          <n-button v-if="!editing" @click="editing = true">编辑</n-button>
          <n-button v-else type="primary" :loading="saving" @click="save">保存</n-button>
          <n-dropdown
            :options="[
              { label: '复制分享链接', key: 'share' },
              { label: '删除文档', key: 'delete' },
            ]"
            @select="onMore"
          >
            <n-button>更多</n-button>
          </n-dropdown>
        </template>
      </header>

      <article class="paper" :class="{ editing }">
        <n-input v-if="editing" v-model:value="title" class="title-input" placeholder="无标题" />
        <h1 v-else>{{ doc.title }}</h1>
        <n-input v-if="editing" v-model:value="slug" class="slug" placeholder="对外地址，可选" />

        <template v-if="editing && doc.source_type === 'markdown'">
          <div class="split">
            <n-input v-model:value="content" type="textarea" placeholder="用 Markdown 写正文" :autosize="{ minRows: 18 }" />
            <div class="md-body preview" v-html="renderMarkdown(content, { stripTitle: title })" />
          </div>
        </template>
        <div
          v-else-if="doc.source_type === 'markdown'"
          class="md-body"
          v-html="renderMarkdown(doc.content_md || '', { stripTitle: doc.title })"
        />
        <div v-else class="plain">{{ doc.content_text }}</div>
      </article>
    </div>
  </n-spin>
</template>

<style scoped>
.page {
  margin: -26px -32px;
  min-height: 100vh;
  background: #f6f7f9;
}
.bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 24px;
  background: rgba(255, 255, 255, 0.92);
  border-bottom: 1px solid #e8eaee;
  position: sticky;
  top: 0;
  z-index: 2;
}
.back {
  border: 0;
  background: transparent;
  color: #6b7280;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 6px;
}
.back:hover {
  background: #f3f4f6;
  color: #111;
}
.time,
.pub {
  color: #9ca3af;
  font-size: 13px;
}
.pub {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-right: 4px;
}
.grow {
  flex: 1;
}
.paper {
  max-width: 800px;
  margin: 32px auto 56px;
  background: #fff;
  border: 1px solid #e8eaee;
  border-radius: 16px;
  padding: 48px 56px 64px;
  box-shadow: var(--shadow-sm);
}
.paper.editing {
  max-width: 1180px;
}
h1 {
  margin: 0 0 8px;
  font-size: 30px;
  line-height: 1.3;
  font-weight: 700;
  letter-spacing: -0.025em;
}
.title-input {
  margin-bottom: 12px;
  font-size: 28px;
}
.slug {
  max-width: 320px;
  margin-bottom: 18px;
}
.split {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-top: 8px;
}
.preview {
  min-height: 420px;
  padding: 8px 4px;
}
.plain {
  white-space: pre-wrap;
  line-height: 1.8;
  color: #374151;
  font-size: 15px;
}
@media (max-width: 900px) {
  .paper {
    margin: 12px;
    padding: 24px 20px 36px;
  }
  .split {
    grid-template-columns: 1fr;
  }
}
</style>
