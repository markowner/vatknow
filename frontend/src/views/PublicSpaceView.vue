<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NCard, NEmpty, NList, NListItem, NSpin, NThing } from "naive-ui";
import { PublicApi } from "@/api";
import { formatTime, sourceLabel } from "@/utils";

const route = useRoute();
const router = useRouter();
const loading = ref(true);
const error = ref("");
const space = ref<{ name: string; slug: string; document_count: number } | null>(null);
const posts = ref<Array<{ id: string; slug: string | null; title: string; source_type: string; excerpt: string; updated_at: string }>>([]);

onMounted(async () => {
  try {
    const slug = String(route.params.slug);
    space.value = await PublicApi.space(slug);
    const res = await PublicApi.posts(slug);
    posts.value = res.items;
  } catch (err) {
    error.value = err instanceof Error ? err.message : "加载失败";
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <div class="wrap">
    <n-spin :show="loading">
      <n-card v-if="error">{{ error }}</n-card>
      <template v-else>
        <h1>{{ space?.name }}</h1>
        <p class="hint">公开空间 · {{ space?.document_count || 0 }} 篇已发布内容</p>
        <n-empty v-if="!posts.length" description="还没有已发布内容" />
        <n-list v-else>
          <n-list-item
            v-for="post in posts"
            :key="post.id"
            style="cursor: pointer"
            @click="router.push(`/p/${space?.slug}/${post.slug || post.id}`)"
          >
            <n-thing :title="post.title" :description="post.excerpt || formatTime(post.updated_at)">
              <template #header-extra>{{ sourceLabel[post.source_type] || post.source_type }}</template>
            </n-thing>
          </n-list-item>
        </n-list>
      </template>
    </n-spin>
  </div>
</template>

<style scoped>
.wrap {
  max-width: 860px;
  margin: 40px auto;
  padding: 0 16px 48px;
}
.hint {
  color: #6b7280;
  margin: 0 0 24px;
}
</style>
