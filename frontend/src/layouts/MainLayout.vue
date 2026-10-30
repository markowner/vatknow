<script setup lang="ts">
import { computed, h, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  NDropdown,
  NIcon,
  NLayout,
  NLayoutContent,
  NLayoutSider,
  NMenu,
  NSelect,
} from "naive-ui";
import type { MenuOption } from "naive-ui";
import {
  BookOutline,
  ChatbubblesOutline,
  ChevronDownOutline,
  CloudUploadOutline,
  CodeSlashOutline,
  HomeOutline,
  LogOutOutline,
  PersonOutline,
  PeopleOutline,
  SearchOutline,
  SettingsOutline,
  TimeOutline,
} from "@vicons/ionicons5";
import { useAuthStore } from "@/stores/auth";
import { useBrandStore } from "@/stores/brand";
import { useSpacesStore } from "@/stores/spaces";
import SiteLogo from "@/components/SiteLogo.vue";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const brand = useBrandStore();
const spacesStore = useSpacesStore();
const spaces = computed(() => spacesStore.items);
const collapsed = ref(false);

const spaceId = computed(() => (typeof route.params.id === "string" ? route.params.id : ""));
const current = computed(() => spaces.value.find((s) => s.id === spaceId.value));
const initial = computed(() => auth.user?.name?.[0]?.toUpperCase() || "U");

function icon(comp: unknown) {
  return () => h(NIcon, null, { default: () => h(comp as never) });
}

const spaceOptions = computed(() =>
  spaces.value.map((s) => ({ label: s.name, value: s.id })),
);

const menuOptions = computed<MenuOption[]>(() => {
  if (!spaceId.value) {
    // 不在某个空间里时，这里放的是全站级入口，不是空间内的页面。
    const children: MenuOption[] = [
      { label: "全部空间", key: "/", icon: icon(HomeOutline) },
      { label: "全库检索", key: "/search", icon: icon(SearchOutline) },
    ];
    // 用户管理只给站点管理员看，普通用户不知道这个入口存在。
    if (brand.isSiteAdmin) {
      children.push({ label: "用户管理", key: "/users", icon: icon(PeopleOutline) });
    }
    return [{ type: "group", label: "全局", key: "g-global", children }];
  }
  const id = spaceId.value;
  return [
    {
      type: "group",
      label: "工作区",
      key: "g-workspace",
      children: [
        { label: "总览", key: `/spaces/${id}`, icon: icon(HomeOutline) },
        { label: "文档", key: `/spaces/${id}/docs`, icon: icon(BookOutline) },
        { label: "收录", key: `/spaces/${id}/ingest`, icon: icon(CloudUploadOutline) },
      ],
    },
    {
      type: "group",
      label: "接口",
      key: "g-api",
      children: [{ label: "API 文档", key: `/spaces/${id}/apis`, icon: icon(CodeSlashOutline) }],
    },
    {
      type: "group",
      label: "智能",
      key: "g-ai",
      children: [
        { label: "检索", key: `/spaces/${id}/search`, icon: icon(SearchOutline) },
        { label: "问答", key: `/spaces/${id}/chat`, icon: icon(ChatbubblesOutline) },
      ],
    },
    {
      type: "group",
      label: "管理",
      key: "g-manage",
      children: [
        { label: "日志", key: `/spaces/${id}/logs`, icon: icon(TimeOutline) },
        { label: "设置", key: `/spaces/${id}/settings`, icon: icon(SettingsOutline) },
      ],
    },
  ];
});

const activeKey = computed(() => {
  const path = route.path;
  const match = [...menuOptions.value]
    .flatMap((item) => (item.children ? (item.children as MenuOption[]) : [item]))
    .sort((a, b) => String(b.key).length - String(a.key).length)
    .find((item) => {
      const key = String(item.key);
      return path === key || (key !== "/" && path.startsWith(key));
    });
  return match ? String(match.key) : path;
});

const userOptions = [
  { label: "账号设置", key: "profile", icon: icon(PersonOutline) },
  { label: "退出登录", key: "logout", icon: icon(LogOutOutline) },
];

async function loadSpaces() {
  await spacesStore.refresh();
}

function onMenu(key: string) {
  router.push(key);
}

function onUser(key: string) {
  if (key === "logout") {
    auth.logout();
    router.replace("/login");
    return;
  }
  if (key === "profile") router.push("/profile");
}

function switchSpace(id: string) {
  router.push(`/spaces/${id}`);
}

onMounted(loadSpaces);
watch(spaceId, loadSpaces);
</script>

<template>
  <n-layout has-sider class="shell" style="height: 100vh">
    <n-layout-sider
      collapse-mode="width"
      :collapsed-width="72"
      :width="248"
      :collapsed="collapsed"
      show-trigger
      bordered
      :native-scrollbar="false"
      @collapse="collapsed = true"
      @expand="collapsed = false"
    >
      <div class="side">
        <div class="brand" @click="router.push('/')">
          <SiteLogo :src="brand.logoUrl" :size="28" />
          <div v-if="!collapsed" class="brand-copy">
            <div class="name">{{ brand.siteName }}</div>
            <div class="sub">{{ brand.tagline }}</div>
          </div>
        </div>

        <div v-if="!collapsed && spaces.length" class="picker">
          <n-select
            size="small"
            :value="spaceId || null"
            :options="spaceOptions"
            placeholder="选择空间"
            :consistent-menu-width="false"
            @update:value="switchSpace"
          />
          <div v-if="current" class="picker-meta">
            {{ current.kind === "personal" ? "个人空间" : "团队空间" }} ·
            {{ current.visibility === "public" ? "公开" : "私密" }}
          </div>
        </div>

        <n-menu
          :value="activeKey"
          :collapsed="collapsed"
          :options="menuOptions"
          :indent="16"
          class="nav"
          :class="{ 'nav-collapsed': collapsed }"
          @update:value="onMenu"
        />

        <div class="side-foot">
          <n-dropdown :options="userOptions" placement="top-start" @select="onUser">
            <button class="me">
              <span class="ava">{{ initial }}</span>
              <span v-if="!collapsed" class="me-meta">
                <b>{{ auth.user?.name }}</b>
                <i>{{ auth.user?.email }}</i>
              </span>
              <n-icon v-if="!collapsed" size="14" class="chev"><ChevronDownOutline /></n-icon>
            </button>
          </n-dropdown>
        </div>
      </div>
    </n-layout-sider>
    <n-layout>
      <n-layout-content
        content-style="padding: 26px 32px; height: 100vh; overflow: auto; background: #f6f7f9"
      >
        <!-- 缓存页面实例，切走再回来时保留滚动位置、搜索词、选中项等状态。
             刷新数据在页面自己的 onActivated 里做，避免看到过期内容。 -->
        <router-view v-slot="{ Component }">
          <keep-alive :max="12">
            <component :is="Component" />
          </keep-alive>
        </router-view>
      </n-layout-content>
    </n-layout>
  </n-layout>
</template>

<style scoped>
.side {
  height: 100vh;
  display: flex;
  flex-direction: column;
}
.brand {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 18px 18px 14px;
  cursor: pointer;
  flex: none;
}
.name {
  font-size: 14.5px;
  font-weight: 700;
  letter-spacing: -0.015em;
  color: #0d1117;
  line-height: 1.2;
}
.sub {
  font-size: 10.5px;
  color: #98a2b3;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-top: 2px;
}
.picker {
  padding: 4px 14px 10px;
  flex: none;
}
.picker-meta {
  margin-top: 7px;
  font-size: 11.5px;
  color: #98a2b3;
  padding-left: 2px;
}
.nav {
  flex: 1;
  overflow: auto;
  padding: 2px 8px 8px;
}
.side-foot {
  padding: 10px 12px 12px;
  border-top: 1px solid #eceef2;
  flex: none;
}
.me {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  border: 0;
  background: transparent;
  padding: 8px;
  border-radius: 10px;
  cursor: pointer;
  text-align: left;
}
.me:hover {
  background: #f5f6f8;
}
.ava {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #eff4ff;
  color: #1d4ed8;
  display: grid;
  place-items: center;
  font-size: 12px;
  font-weight: 700;
  flex: none;
}
.me-meta {
  flex: 1;
  min-width: 0;
}
.me-meta b {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: #0d1117;
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.me-meta i {
  display: block;
  font-style: normal;
  font-size: 11.5px;
  color: #98a2b3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.chev {
  color: #98a2b3;
  flex: none;
}
:deep(.n-menu-item-group-title) {
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  color: #aab2bf;
  padding: 14px 16px 6px;
  height: auto;
  line-height: 1.4;
}
/* 收起后没有横向空间，分组标题会挤成竖排单字，改成一条细分隔线。 */
.nav-collapsed :deep(.n-menu-item-group-title) {
  font-size: 0;
  height: 1px;
  padding: 0;
  margin: 10px 20px;
  border-top: 1px solid #eceef2;
  overflow: hidden;
}
/* Naive UI 的菜单项是 grid 布局并带内联 padding，收起后图标会偏左，这里改成居中。 */
.nav-collapsed :deep(.n-menu-item-content) {
  display: flex;
  justify-content: center;
  padding-left: 0 !important;
  padding-right: 0 !important;
}
.nav-collapsed :deep(.n-menu-item-content__icon) {
  margin-right: 0 !important;
}
.nav-collapsed :deep(.n-menu-item-content-header) {
  display: none;
}
:deep(.n-menu-item-content) {
  font-size: 13.5px;
}
:deep(.n-layout-sider-scroll-container) {
  display: flex;
  flex-direction: column;
}
</style>
