<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { NButton, NEmpty, NGrid, NGridItem, NInput, NTag, useDialog, useMessage } from "naive-ui";
import { SpacesApi, type Space } from "@/api";
import { usePageLifecycle } from "@/composables/pageCache";
import { useSpacesStore } from "@/stores/spaces";
import { roleLabel } from "@/utils";

const router = useRouter();
const message = useMessage();
const dialog = useDialog();
const spacesStore = useSpacesStore();
const name = ref("");
const loading = ref(false);

async function load() {
  await spacesStore.refresh();
}

async function create() {
  if (!name.value.trim()) return;
  loading.value = true;
  try {
    const space = await SpacesApi.create(name.value.trim());
    message.success("已创建团队空间");
    name.value = "";
    await load();
    router.push(`/spaces/${space.id}`);
  } catch (err) {
    message.error(err instanceof Error ? err.message : "创建失败");
  } finally {
    loading.value = false;
  }
}

function removeSpace(space: Space) {
  if (space.kind === "personal") {
    message.warning("个人空间不能删除，请到设置里改名称");
    return;
  }
  if (space.role !== "owner") {
    message.warning("只有所有者可以删除空间");
    return;
  }
  dialog.error({
    title: `删除「${space.name}」`,
    content: "文档、成员和 API 文档都会删除，且不可恢复。",
    positiveText: "确认删除",
    negativeText: "取消",
    onPositiveClick: async () => {
      try {
        await SpacesApi.remove(space.id);
        message.success("空间已删除");
        await load();
      } catch (err) {
        message.error(err instanceof Error ? err.message : "删除失败");
      }
    },
  });
}

usePageLifecycle({ enter: load });
</script>

<template>
  <div>
    <div class="page-head">
      <div>
        <div class="eyebrow">Workspace</div>
        <h1 class="page-title">工作空间</h1>
        <p class="page-desc">改名、公开在设置里完成；团队空间仅所有者可删除。</p>
      </div>
      <div class="create">
        <n-input v-model:value="name" placeholder="新团队空间名称" style="width: 220px" @keyup.enter="create" />
        <n-button type="primary" :loading="loading" @click="create">新建</n-button>
      </div>
    </div>

    <div v-if="!spacesStore.items.length" class="panel empty">
      <n-empty description="还没有空间" />
    </div>
    <n-grid v-else cols="1 640:2 1000:3" :x-gap="16" :y-gap="16">
      <n-grid-item v-for="space in spacesStore.items" :key="space.id">
        <article class="card">
          <div class="top">
            <div class="icon" :class="space.kind">{{ space.name.slice(0, 1) }}</div>
            <div class="tags">
              <n-tag size="small" :bordered="false">{{ space.kind === "personal" ? "个人" : "团队" }}</n-tag>
              <n-tag size="small" :bordered="false" :type="space.visibility === 'public' ? 'warning' : 'default'">
                {{ space.visibility === "public" ? "公开" : "私密" }}
              </n-tag>
            </div>
          </div>
          <h3>{{ space.name }}</h3>
          <p class="role">{{ roleLabel[space.role] }}</p>
          <div class="acts">
            <n-button size="small" type="primary" @click="router.push(`/spaces/${space.id}`)">进入</n-button>
            <n-button size="small" quaternary @click="router.push(`/spaces/${space.id}/settings`)">设置</n-button>
            <n-button
              v-if="space.kind === 'team' && space.role === 'owner'"
              size="small"
              quaternary
              type="error"
              @click="removeSpace(space)"
            >
              删除
            </n-button>
          </div>
        </article>
      </n-grid-item>
    </n-grid>
  </div>
</template>

<style scoped>
.create {
  display: flex;
  gap: 8px;
  flex: none;
}
.empty {
  padding: 64px 0;
}
.card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 18px;
  min-height: 168px;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-sm);
  transition: box-shadow 0.16s ease, transform 0.16s ease;
}
.card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}
.top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 10px;
}
.icon {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  font-weight: 700;
  font-size: 15px;
  background: #eff4ff;
  color: #1d4ed8;
}
.icon.team {
  background: #f0fdf9;
  color: #047857;
}
.tags {
  display: flex;
  gap: 6px;
}
h3 {
  margin: 14px 0 0;
  font-size: 15px;
  font-weight: 650;
  letter-spacing: -0.01em;
}
.role {
  color: var(--faint);
  font-size: 12.5px;
  margin: 6px 0 16px;
  flex: 1;
}
.acts {
  display: flex;
  gap: 4px;
  margin-left: -6px;
}
</style>
