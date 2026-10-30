<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NButton, NCard, NSpin } from "naive-ui";
import { PublicApi } from "@/api";
import { renderMarkdown } from "@/utils";
import PublicApiDoc from "@/components/PublicApiDoc.vue";

const route = useRoute();
const router = useRouter();
const loading = ref(true);
const error = ref("");
const post = ref<{ title: string; source_type: string; content_md: string | null; content_text: string } | null>(null);
const slug = computed(() => String(route.params.slug));

onMounted(async () => {
  try {
    post.value = await PublicApi.post(slug.value, String(route.params.key));
  } catch (err) {
    error.value = err instanceof Error ? err.message : "加载失败";
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <div class="wrap" :class="{ wide: post?.source_type === 'openapi' }">
    <n-button text @click="router.push(`/p/${slug}`)">← 返回列表</n-button>
    <n-spin :show="loading">
      <n-card v-if="error" style="margin-top: 12px">{{ error }}</n-card>
      <PublicApiDoc
        v-else-if="post?.source_type === 'openapi'"
        class="api"
        :spec="post.content_md || ''"
      />
      <n-card v-else-if="post" style="margin-top: 12px">
        <h1>{{ post.title }}</h1>
        <div v-if="post.source_type === 'markdown'" class="md-body" v-html="renderMarkdown(post.content_md || '')" />
        <pre v-else class="plain">{{ post.content_text }}</pre>
      </n-card>
    </n-spin>
  </div>
</template>

<style scoped>
.wrap {
  max-width: 960px;
  margin: 32px auto;
  padding: 0 16px 48px;
}
.wrap.wide {
  max-width: 1180px;
}
.api {
  margin-top: 12px;
}
.plain {
  white-space: pre-wrap;
  line-height: 1.7;
}
</style>
