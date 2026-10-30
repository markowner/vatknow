<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NButton, NSpace, NSpin, useMessage } from "naive-ui";
import { DocsApi, SharesApi, type Document } from "@/api";
import ApiConsole from "@/components/ApiConsole.vue";
import { useSpaceId, useDocId } from "@/composables/useRouteIds";

const route = useRoute();
const router = useRouter();
const message = useMessage();
const spaceId = useSpaceId();
const docId = useDocId();
const doc = ref<Document | null>(null);

async function load() {
  if (!docId.value) return;
  doc.value = await DocsApi.get(docId.value);
}

async function share() {
  try {
    const link = await SharesApi.create(spaceId.value, { document_id: docId.value });
    await navigator.clipboard.writeText(link.url.replace(":8000", ":3000"));
    message.success("对外文档链接已复制");
  } catch (err) {
    message.error(err instanceof Error ? err.message : "创建分享失败");
  }
}

watch([spaceId, docId], load);
onMounted(load);
</script>

<template>
  <n-spin :show="!doc">
    <div v-if="doc">
      <n-space justify="space-between" style="margin-bottom: 12px">
        <n-button quaternary @click="router.push(`/spaces/${spaceId}/apis`)">← 全部 API 文档</n-button>
        <n-space>
          <n-button @click="router.push(`/spaces/${spaceId}/apis/${doc.id}/edit`)">编辑接口</n-button>
          <n-button type="primary" @click="share">复制对外链接</n-button>
        </n-space>
      </n-space>
      <ApiConsole :spec="doc.content_md || ''" :space-id="spaceId" :document-id="doc.id" />
    </div>
  </n-spin>
</template>
