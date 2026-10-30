<script setup lang="ts">
import { computed, h, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  NButton,
  NDataTable,
  NForm,
  NFormItem,
  NInput,
  NRadioButton,
  NRadioGroup,
  NSelect,
  NSpace,
  useDialog,
  useMessage,
} from "naive-ui";
import type { DataTableColumns } from "naive-ui";
import { SharesApi, SpacesApi, type Member, type ShareLink, type Space } from "@/api";
import { usePageLifecycle, useScrollMemory } from "@/composables/pageCache";
import { useSpacesStore } from "@/stores/spaces";
import { canAdmin, canEdit, formatTime, roleLabel } from "@/utils";
import { useSpaceId } from "@/composables/useRouteIds";

const route = useRoute();
const router = useRouter();
const message = useMessage();
const dialog = useDialog();
const spacesStore = useSpacesStore();
const spaceId = useSpaceId();
const space = ref<Space | null>(null);
const members = ref<Member[]>([]);
const shares = ref<ShareLink[]>([]);
const name = ref("");
const visibility = ref("private");
const slug = ref("");
const invite = ref({ email: "", role: "editor" });
const shareForm = ref({ password: "", expires_days: null as number | null });

const publicUrl = computed(() => (slug.value ? `${window.location.origin}/p/${slug.value}` : ""));
const publicApi = computed(() =>
  slug.value ? `${window.location.origin}/api/v1/public/spaces/${slug.value}/posts` : "",
);

async function load() {
  if (!spaceId.value) return;
  space.value = await SpacesApi.get(spaceId.value);
  name.value = space.value.name;
  visibility.value = space.value.visibility || "private";
  slug.value = space.value.slug || "";
  members.value = await SpacesApi.members(spaceId.value);
  shares.value = await SharesApi.list(spaceId.value);
}

async function saveSpace() {
  try {
    space.value = await SpacesApi.update(spaceId.value, {
      name: name.value,
      visibility: visibility.value,
      slug: slug.value || null,
    });
    slug.value = space.value.slug || "";
    visibility.value = space.value.visibility;
    await spacesStore.refresh();
    message.success("空间设置已保存");
  } catch (err) {
    message.error(err instanceof Error ? err.message : "保存失败");
  }
}

async function copy(text: string) {
  await navigator.clipboard.writeText(text);
  message.success("已复制");
}

async function add() {
  try {
    await SpacesApi.addMember(spaceId.value, invite.value.email, invite.value.role);
    invite.value.email = "";
    message.success("已邀请");
    await load();
  } catch (err) {
    message.error(err instanceof Error ? err.message : "邀请失败");
  }
}

async function createShare() {
  try {
    const link = await SharesApi.create(spaceId.value, {
      password: shareForm.value.password || undefined,
      expires_days: shareForm.value.expires_days || undefined,
    });
    shareForm.value.password = "";
    message.success("已创建分享链接");
    await navigator.clipboard.writeText(link.url.replace(":8000", ":3000"));
    await load();
  } catch (err) {
    message.error(err instanceof Error ? err.message : "创建失败");
  }
}

const columns = computed<DataTableColumns<Member>>(() => [
  { title: "名称", key: "name" },
  { title: "邮箱", key: "email" },
  {
    title: "角色",
    key: "role",
    render(row) {
      if (!canAdmin(space.value?.role) || space.value?.kind === "personal") return roleLabel[row.role];
      return h(NSelect, {
        value: row.role,
        size: "small",
        style: "width: 120px",
        options: [
          { label: "只读", value: "viewer" },
          { label: "编辑", value: "editor" },
          { label: "管理员", value: "admin" },
          { label: "所有者", value: "owner" },
        ],
        onUpdateValue: async (value: string) => {
          try {
            await SpacesApi.updateMember(spaceId.value, row.user_id, value);
            await load();
          } catch (err) {
            message.error(err instanceof Error ? err.message : "更新失败");
          }
        },
      });
    },
  },
  {
    title: "操作",
    key: "op",
    width: 100,
    render(row) {
      if (!canAdmin(space.value?.role) || space.value?.kind === "personal") return null;
      return h(
        NButton,
        {
          size: "small",
          type: "error",
          ghost: true,
          onClick: async () => {
            try {
              await SpacesApi.removeMember(spaceId.value, row.user_id);
              await load();
            } catch (err) {
              message.error(err instanceof Error ? err.message : "移除失败");
            }
          },
        },
        { default: () => "移除" },
      );
    },
  },
]);

const shareColumns = computed<DataTableColumns<ShareLink>>(() => [
  { title: "链接", key: "url", ellipsis: { tooltip: true } },
  { title: "密码", key: "has_password", width: 80, render: (row) => (row.has_password ? "有" : "无") },
  { title: "创建时间", key: "created_at", width: 180, render: (row) => formatTime(row.created_at) },
  {
    title: "操作",
    key: "op",
    width: 160,
    render(row) {
      return h(NSpace, {}, {
        default: () => [
          h(NButton, { size: "small", onClick: () => copy(row.url.replace(":8000", ":3000")) }, { default: () => "复制" }),
          canEdit(space.value?.role)
            ? h(
                NButton,
                {
                  size: "small",
                  type: "error",
                  ghost: true,
                  onClick: async () => {
                    await SharesApi.revoke(spaceId.value, row.id);
                    await load();
                  },
                },
                { default: () => "撤销" },
              )
            : null,
        ],
      });
    },
  },
]);

function destroy() {
  dialog.error({
    title: "删除团队空间",
    content: "文档与成员关系都会删除，且不可恢复。",
    positiveText: "确认删除",
    negativeText: "取消",
    onPositiveClick: async () => {
      await SpacesApi.remove(spaceId.value);
      await spacesStore.refresh();
      message.success("空间已删除");
      router.replace("/");
    },
  });
}

watch(spaceId, load);
usePageLifecycle({ enter: load });
useScrollMemory();
</script>

<template>
  <div class="settings">
    <div class="page-head">
      <div>
        <div class="eyebrow">Settings</div>
        <h1 class="page-title">空间设置</h1>
        <p class="page-desc">名称、可见性、分享链接与成员权限。</p>
      </div>
    </div>

    <section class="panel block">
      <header>
        <h3>空间信息</h3>
        <p>私密空间适合公司 Wiki；公开后已发布文档可通过页面与 API 对外。</p>
      </header>
      <n-form label-placement="left" label-width="90">
        <n-form-item label="名称">
          <n-space>
            <n-input v-model:value="name" :disabled="!canAdmin(space?.role)" style="width: 280px" />
            <n-button v-if="canAdmin(space?.role)" type="primary" @click="saveSpace">保存</n-button>
          </n-space>
        </n-form-item>
        <n-form-item label="可见性">
          <n-radio-group v-model:value="visibility" :disabled="!canAdmin(space?.role)" @update:value="saveSpace">
            <n-radio-button value="private">私密</n-radio-button>
            <n-radio-button value="public">公开</n-radio-button>
          </n-radio-group>
        </n-form-item>
        <n-form-item v-if="visibility === 'public'" label="公开别名">
          <n-input v-model:value="slug" placeholder="例如 blog 或 wiki" style="width: 280px" @blur="saveSpace" />
        </n-form-item>
      </n-form>
    </section>

    <section v-if="visibility === 'public' && slug" class="panel block">
      <header>
        <h3>博客 / 对外接口</h3>
        <p>已发布内容无需登录即可访问。</p>
      </header>
      <div class="links">
        <div>
          <span>公开页面</span>
          <a :href="publicUrl" target="_blank">{{ publicUrl }}</a>
          <n-button text type="primary" size="tiny" @click="copy(publicUrl)">复制</n-button>
        </div>
        <div>
          <span>文章列表 API</span>
          <code>{{ publicApi }}</code>
          <n-button text type="primary" size="tiny" @click="copy(publicApi)">复制</n-button>
        </div>
        <div>
          <span>单篇</span>
          <code>/api/v1/public/spaces/{{ slug }}/posts/&#123;id或slug&#125;</code>
        </div>
      </div>
    </section>

    <section class="panel block">
      <header>
        <h3>分享链接</h3>
        <p>即使空间是私密的，也可以生成带权限的访问链接，适合对外 API 文档。</p>
      </header>
      <n-space v-if="canEdit(space?.role)" style="margin-bottom: 12px">
        <n-input v-model:value="shareForm.password" placeholder="可选密码" style="width: 180px" />
        <n-button type="primary" @click="createShare">生成空间分享链接</n-button>
      </n-space>
      <n-data-table :columns="shareColumns" :data="shares" :pagination="false" :bordered="false" />
    </section>

    <section class="panel block">
      <header>
        <h3>成员</h3>
        <p v-if="space?.kind === 'personal'">个人空间不能邀请成员。公司 Wiki 请新建团队空间。</p>
        <p v-else>邀请已注册用户，并按角色控制读写。</p>
      </header>
      <template v-if="space?.kind !== 'personal'">
        <n-form v-if="canAdmin(space?.role)" inline class="invite">
          <n-form-item label="邮箱"><n-input v-model:value="invite.email" placeholder="已注册用户邮箱" /></n-form-item>
          <n-form-item label="角色">
            <n-select v-model:value="invite.role" style="width: 120px" :options="[
              { label: '只读', value: 'viewer' },
              { label: '编辑', value: 'editor' },
              { label: '管理员', value: 'admin' },
            ]" />
          </n-form-item>
          <n-form-item><n-button type="primary" @click="add">邀请</n-button></n-form-item>
        </n-form>
        <n-data-table :columns="columns" :data="members" :pagination="false" :bordered="false" />
      </template>
    </section>

    <section v-if="space?.kind === 'team' && space.role === 'owner'" class="panel block danger">
      <header>
        <h3>危险操作</h3>
        <p>删除后文档和成员都会消失，不可恢复。</p>
      </header>
      <n-button type="error" secondary @click="destroy">删除这个空间</n-button>
    </section>
    <section v-else-if="space?.kind === 'personal'" class="panel block">
      <header>
        <h3>删除</h3>
        <p>个人空间不能删除，可在上方修改名称。不需要的团队空间请回到「全部空间」删除。</p>
      </header>
    </section>
  </div>
</template>

<style scoped>
.settings {
  max-width: 880px;
}
.block {
  padding: 20px 22px;
  margin-bottom: 16px;
}
.block header {
  margin-bottom: 16px;
}
.block h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 650;
  letter-spacing: -0.01em;
}
.block header p {
  margin: 6px 0 0;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.6;
}
.links {
  display: grid;
  gap: 10px;
  font-size: 13px;
}
.links > div {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.links span {
  color: var(--faint);
  min-width: 92px;
  font-size: 12.5px;
}
.links code {
  background: #f5f6f8;
  padding: 3px 8px;
  border-radius: 6px;
  font-size: 12px;
}
.invite {
  margin-bottom: 12px;
}
.danger {
  border-color: #fecaca;
  background: #fffbfb;
}
</style>
