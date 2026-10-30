<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  NButton,
  NDropdown,
  NEmpty,
  NForm,
  NFormItem,
  NInput,
  NModal,
  NSelect,
  NSpace,
  NTabPane,
  NTabs,
  NTag,
  useDialog,
  useMessage,
} from "naive-ui";
import { DocsApi } from "@/api";
import PreviewPane from "@/components/api-doc/PreviewPane.vue";
import EditPane from "@/components/api-doc/EditPane.vue";
import RunPane from "@/components/api-doc/RunPane.vue";
import MethodBadge from "@/components/api-doc/MethodBadge.vue";
import CommonParamsPane from "@/components/api-doc/CommonParamsPane.vue";
import EnvironmentsPane from "@/components/api-doc/EnvironmentsPane.vue";
import ExternalAccessModal from "@/components/ExternalAccessModal.vue";
import { usePageLifecycle, useScrollMemory } from "@/composables/pageCache";
import { emptyOp, emptySpec, envNameFromUrl, mergeCommonParams, parseOpenApi, serializeOpenApi, type OpenEnv, type OpenParam, type OpenSpec } from "@/openapi";
import { renderMarkdown } from "@/utils";
import { useSpaceId } from "@/composables/useRouteIds";

const route = useRoute();
const router = useRouter();
const message = useMessage();
const dialog = useDialog();
const spaceId = useSpaceId();
const docId = ref(typeof route.params.docId === "string" ? route.params.docId : "");
const spec = reactive<OpenSpec>(emptySpec());
const index = ref(0);
const current = computed(() => spec.ops[index.value] || null);
const tab = ref("preview");
const saving = ref(false);
const dirty = ref(false);
const keyword = ref("");
const collapsed = ref<Record<string, boolean>>({});
const showAdd = ref(false);
const showCat = ref(false);
const showShare = ref(false);
const renaming = ref("");
const renameTo = ref("");
const newCat = ref("");
const envPanel = ref(false);
const paramPanel = ref(false);
/** 项目级公共说明：对外展示，支持 Markdown，例如怎么对接、鉴权、如何获取密钥。 */
const introPanel = ref(false);
const introDraft = ref("");
const introHtml = computed(() => renderMarkdown(introDraft.value));
/** 主区域是否正在显示「公共说明」这一页；和具体接口互斥。 */
const showIntroPage = ref(false);
const introPageHtml = computed(() => renderMarkdown(spec.description || ""));
const envIndex = ref(0);
const searchPanel = ref(false);
const searchActive = ref(0);
const searchTerm = ref("");
const draft = reactive({ method: "GET", path: "/user/{id}", summary: "获取用户", tag: "公共分类" });
const methods = ["GET", "POST", "PUT", "PATCH", "DELETE"].map((value) => ({ label: value, value }));

function markDirty() {
  dirty.value = true;
}

/**
 * 每个文档上次停留的接口和页签。切空间或换文档都会重新拉取，
 * 没有这份记忆的话选中项会被 apply 归零，用户会以为自己的位置丢了。
 */
const lastPosition = new Map<string, { index: number; tab: string }>();

function rememberPosition() {
  if (docId.value) lastPosition.set(docId.value, { index: index.value, tab: tab.value });
}

function apply(next: OpenSpec) {
  spec.title = next.title;
  spec.version = next.version;
  spec.description = next.description;
  spec.notes = next.notes;
  spec.servers = next.servers.length ? [...next.servers] : ["https://api.example.com"];
  spec.categories = next.categories.length ? [...next.categories] : ["公共分类"];
  spec.ops = next.ops;
  spec.environments = next.environments.length
    ? next.environments.map((item) => ({ ...item }))
    : next.servers.map((url) => ({ name: url, url }));
  spec.commonParams = next.commonParams.map((item) => ({ ...item }));
  const remembered = docId.value ? lastPosition.get(docId.value) : undefined;
  index.value = remembered ? Math.min(remembered.index, Math.max(0, spec.ops.length - 1)) : 0;
  tab.value = remembered?.tab || "preview";
  envIndex.value = 0;
  dirty.value = false;
}

/** 当前环境决定预览 / 调试用的 Base URL。用下标而不是名字，避免同名环境选错。 */
const currentEnv = computed(() => spec.environments[envIndex.value] || spec.environments[0] || null);
/** 顶部只展示当前环境的地址，改域名统一去“环境”弹框，避免两处互相打架。 */
const activeServer = computed(() => currentEnv.value?.url || spec.servers[0] || "");

/** 预览和调试都要带上全局公共参数，否则看不到真实请求形态。 */
const effectiveOp = computed(() => {
  if (!current.value) return null;
  const common = spec.commonParams.filter((item) => item.in !== "path");
  return { ...current.value, parameters: mergeCommonParams(current.value.parameters, common) };
});

async function load() {
  if (!docId.value) {
    apply(emptySpec());
    spec.title = "未命名项目";
    return;
  }
  const doc = await DocsApi.get(docId.value);
  const parsed = parseOpenApi(doc.content_md || "") || emptySpec();
  parsed.title = parsed.title || doc.title;
  apply(parsed);
}

const groups = computed(() => {
  // 左侧固定展示完整树，搜索走弹框，避免输入即过滤把树结构打散。
  return spec.categories.map((cat) => ({
    cat,
    ops: spec.ops.map((op, i) => ({ op, i })).filter(({ op }) => (op.tags[0] || "公共分类") === cat),
  }));
});

async function confirmAdd(): Promise<boolean> {
  const op = emptyOp(draft.tag || spec.categories[0] || "公共分类");
  op.method = draft.method;
  op.path = draft.path.startsWith("/") ? draft.path : `/${draft.path}`;
  op.summary = draft.summary.trim() || op.path;
  if (["POST", "PUT", "PATCH"].includes(op.method)) {
    op.body = { contentType: "application/json", example: "{\n  \n}", required: true, description: "" };
  }
  const names = [...op.path.matchAll(/\{([^}/]+)\}/g)].map((item) => item[1]);
  for (const name of names) {
    op.parameters.push({ name, in: "path", required: true, description: "", schema: { type: "string" } });
  }
  spec.ops.push(op);
  index.value = spec.ops.length - 1;
  tab.value = "edit";
  // 确认即落库，省掉再去点顶部「保存」这一步。
  if (!(await save())) {
    // 保存失败就回滚，别把没存上的接口留在界面上。
    spec.ops.pop();
    index.value = Math.min(index.value, spec.ops.length - 1);
    return false;
  }
  showAdd.value = false;
  return true;
}

async function addCategory(): Promise<boolean> {
  const name = newCat.value.trim();
  if (!name) return false;
  const isNew = !spec.categories.includes(name);
  if (isNew) spec.categories.push(name);
  draft.tag = name;
  // 和添加接口保持一致：确认即落库，不用再点顶部保存。
  if (!(await save())) {
    if (isNew) spec.categories = spec.categories.filter((item) => item !== name);
    return false;
  }
  newCat.value = "";
  showCat.value = false;
  return true;
}

function renameCategory() {
  const next = renameTo.value.trim();
  if (!renaming.value || !next) return;
  if (next !== renaming.value && spec.categories.includes(next)) {
    message.warning("已有同名分类");
    return;
  }
  spec.categories = spec.categories.map((item) => (item === renaming.value ? next : item));
  for (const op of spec.ops) {
    if (op.tags[0] === renaming.value) op.tags = [next];
  }
  renaming.value = "";
  markDirty();
}

function removeCategory(cat: string) {
  if (spec.ops.some((op) => (op.tags[0] || "公共分类") === cat)) {
    message.warning("请先把该分类下的接口移走或删除");
    return;
  }
  if (spec.categories.length <= 1) {
    message.warning("至少保留一个分类");
    return;
  }
  spec.categories = spec.categories.filter((item) => item !== cat);
  markDirty();
}

function duplicate() {
  if (!current.value) return;
  const copy = JSON.parse(JSON.stringify(current.value));
  copy.summary = `${copy.summary} 副本`;
  spec.ops.splice(index.value + 1, 0, copy);
  index.value += 1;
  markDirty();
}

function removeOp() {
  if (!current.value) return;
  dialog.warning({
    title: "删除接口",
    content: `确定删除「${current.value.summary}」？`,
    positiveText: "删除",
    negativeText: "取消",
    onPositiveClick: () => {
      spec.ops.splice(index.value, 1);
      index.value = Math.min(index.value, Math.max(0, spec.ops.length - 1));
      markDirty();
    },
  });
}

async function save(): Promise<boolean> {
  if (!spec.title.trim()) {
    message.warning("请填写项目名称");
    return false;
  }
  saving.value = true;
  try {
    const json = serializeOpenApi(spec);
    if (!docId.value) {
      const doc = await DocsApi.openapi(spaceId.value, json, spec.title);
      docId.value = doc.id;
      await router.replace(`/spaces/${spaceId.value}/apis/${doc.id}`);
    } else {
      await DocsApi.update(docId.value, { title: spec.title, content_md: json });
    }
    dirty.value = false;
    message.success("保存成功");
    return true;
  } catch (err) {
    message.error(err instanceof Error ? err.message : "保存失败");
    return false;
  } finally {
    saving.value = false;
  }
}

async function copyPath() {
  if (!current.value) return;
  await navigator.clipboard.writeText(current.value.path);
  message.success("已复制路径");
}

function onMore(key: string) {
  if (key === "copy") copyPath();
  if (key === "dup") duplicate();
  if (key === "del") removeOp();
}

function onCatMore(cat: string, key: string) {
  if (key === "rename") {
    renaming.value = cat;
    renameTo.value = cat;
  }
  if (key === "remove") removeCategory(cat);
}

/** 弹框里编辑的是副本，点保存才写回 spec；取消不留下半成品改动。 */
const envDraft = ref<OpenEnv[]>([]);
const paramDraft = ref<OpenParam[]>([]);

function openIntro() {
  introDraft.value = spec.description || "";
  introPanel.value = true;
}

async function saveIntro() {
  const prev = spec.description;
  spec.description = introDraft.value;
  // 和其他弹框一致：确认即写库，避免留下「未保存」。
  if (await save()) {
    introPanel.value = false;
  } else {
    spec.description = prev;
  }
}

function openEnvs() {
  envDraft.value = spec.environments.map((item) => ({ ...item }));
  envPanel.value = true;
}

async function saveEnvs() {
  const kept = envDraft.value.filter((item) => item.url.trim() || item.name.trim());
  if (!kept.length) {
    message.warning("至少保留一个环境");
    return;
  }
  const prevEnvs = spec.environments;
  const prevServers = spec.servers;
  spec.environments = kept.map((item, i) => ({
    name: item.name.trim() || envNameFromUrl(item.url),
    url: item.url.trim() || `https://env${i + 1}.example.com`,
  }));
  spec.servers = spec.environments.map((item) => item.url);
  envIndex.value = Math.min(envIndex.value, spec.environments.length - 1);
  // 弹框里点了保存就落库，不然关掉弹框还挂着「未保存」让人以为没存上。
  if (await save()) {
    envPanel.value = false;
  } else {
    spec.environments = prevEnvs;
    spec.servers = prevServers;
  }
}

function openParams() {
  paramDraft.value = spec.commonParams.map((item) => ({ ...item, schema: { ...item.schema } }));
  paramPanel.value = true;
}

async function saveParams() {
  const prev = spec.commonParams;
  spec.commonParams = paramDraft.value
    .filter((item) => item.name.trim())
    .map((item) => ({ ...item, name: item.name.trim(), schema: { ...item.schema } }));
  // 同环境弹框：点保存即写库，避免残留在「未保存」状态。
  if (await save()) {
    paramPanel.value = false;
  } else {
    spec.commonParams = prev;
  }
}

/** 弹框内容以 props 传入副本，子组件直接改副本即可。 */
/** 弹框搜索：在当前 API 文档内找接口，命中范围覆盖名称、路径、分组、说明和参数。 */
const searchResults = computed(() => {
  const q = searchTerm.value.trim().toLowerCase();
  if (!q) return [];
  return spec.ops
    .map((op, i) => ({ op, i }))
    .filter(({ op }) => {
      const haystack = [
        op.method,
        op.path,
        op.summary,
        op.description,
        op.notes,
        (op.tags || []).join(" "),
        op.parameters.map((item) => `${item.name} ${item.description}`).join(" "),
        op.responses.map((item) => `${item.status} ${item.description}`).join(" "),
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(q);
    });
});

/** 焦点落到搜索弹框的输入框上，省得再点一次。 */
function focusSearchInput() {
  window.setTimeout(() => {
    const input = document.querySelector<HTMLInputElement>(".search-modal input");
    input?.focus();
  }, 60);
}

function openSearch() {
  searchTerm.value = "";
  searchActive.value = 0;
  searchPanel.value = true;
  focusSearchInput();
}

/** 从搜索结果跳到接口：切到预览页，同时把左侧分组展开，保证能看清所在位置。 */
function openResult(target: number) {
  index.value = target;
  tab.value = "preview";
  const cat = spec.ops[target]?.tags[0] || "公共分类";
  collapsed.value[cat] = false;
  searchPanel.value = false;
}

/** 弹框内的方向键、回车、Esc。列表变了就把高亮拉回第一项，避免停在越界位置。 */
function onSearchKey(e: KeyboardEvent) {
  const list = searchResults.value;
  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    if (!list.length) return;
    e.preventDefault();
    const step = e.key === "ArrowDown" ? 1 : -1;
    searchActive.value = (searchActive.value + step + list.length) % list.length;
    return;
  }
  if (e.key === "Enter") {
    const hit = list[searchActive.value];
    if (hit) {
      e.preventDefault();
      openResult(hit.i);
    }
    return;
  }
  if (e.key === "Escape") {
    e.preventDefault();
    searchPanel.value = false;
  }
}

function onKey(e: KeyboardEvent) {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") {
    e.preventDefault();
    save();
  }
  // ⌘K / Ctrl+K 直接开搜索，和常见工具的肌肉记忆一致。
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
    e.preventDefault();
    openSearch();
  }
}

watch(docId, load, { immediate: true });
// 组件被缓存后实例复用，路由换了文档时得手动同步，否则会停在上一个文档上。
// 只处理「切到了另一个文档」，离开本页（参数变空）时不能动 docId，
// 否则会触发一次 load，把选中的接口和编辑页签一起重置掉。
watch(
  () => route.params.docId,
  (id) => {
    if (typeof id !== "string" || !id) return;
    if (id !== docId.value) {
      rememberPosition();
      docId.value = id;
    }
  },
);
// 关键词一变，命中结果和顺序都变了，高亮回到第一项。
watch(searchTerm, () => (searchActive.value = 0));

// 缓存后组件不会销毁，全局快捷键必须跟着页面进出，否则在别的页面也会触发。
// 数据也不重拉：这里有未保存的编辑，重载会把用户正在改的东西冲掉。
usePageLifecycle({
  enter: () => window.addEventListener("keydown", onKey),
  leave: () => {
    window.removeEventListener("keydown", onKey);
    // 离开时把位置记下来，切空间重新加载后还能回到原处。
    rememberPosition();
  },
});
useScrollMemory();
</script>

<template>
  <div class="yapi">
    <header>
      <div class="left">
        <button class="back" @click="router.push(`/spaces/${spaceId}/apis`)">← 项目</button>
        <n-input v-model:value="spec.title" class="title" placeholder="项目名称" @update:value="markDirty" />
        <span class="sep" />
        <!-- 环境用下拉选择，避免把人家的地址直接改错；只有一个环境也保留下拉，入口位置才稳定 -->
        <n-select
          v-model:value="envIndex"
          class="env-pick"
          size="small"
          :options="spec.environments.map((item, i) => ({ label: item.name || item.url || `环境 ${i + 1}`, value: i }))"
        />
        <code class="env">{{ activeServer || "未配置环境" }}</code>
        <n-tag v-if="dirty" size="small" type="warning" :bordered="false">未保存</n-tag>
      </div>
      <n-space>
        <n-button :disabled="!docId || dirty" :title="dirty ? '先保存再对外分享' : ''" @click="showShare = true">外链</n-button>
        <n-button @click="openEnvs">环境</n-button>
        <n-button @click="openParams">公共参数</n-button>
        <n-button @click="openIntro">公共说明</n-button>
        <n-button type="primary" :loading="saving" @click="save">保存</n-button>
      </n-space>
    </header>
    <div class="wrap">
      <aside>
        <div class="aside-head">
          <button class="search-trigger" @click="openSearch">
            <span class="ico">⌕</span>
            <span class="ph">搜索接口</span>
            <span class="kbd">⌘K</span>
          </button>
        </div>
        <div class="tree">
          <!-- 公共说明属于整份文档，放树顶单独一项，不再跟着每个接口重复 -->
          <button class="intro-nav" :class="{ active: showIntroPage }" @click="showIntroPage = true">
            <span class="ico">≡</span>
            <span class="t">
              <b>公共说明</b>
              <i>{{ spec.description.trim() ? "已填写" : "未填写 · 怎么对接" }}</i>
            </span>
          </button>
          <div v-for="group in groups" :key="group.cat" class="group">
            <div class="cat">
              <button class="cat-name" @click="collapsed[group.cat] = !collapsed[group.cat]">
                <span class="chev">{{ collapsed[group.cat] ? "▸" : "▾" }}</span>
                <span class="cat-label">{{ group.cat }}</span>
                <em>{{ group.ops.length }}</em>
              </button>
              <n-dropdown
                :options="[
                  { label: '重命名', key: 'rename' },
                  { label: '删除分类', key: 'remove' },
                ]"
                @select="(key) => onCatMore(group.cat, String(key))"
              >
                <button class="more" @click.stop>⋯</button>
              </n-dropdown>
            </div>
            <template v-if="!collapsed[group.cat]">
              <button
                v-for="item in group.ops"
                :key="item.i"
                class="iface"
                :class="{ active: !showIntroPage && item.i === index }"
                @click="showIntroPage = false; index = item.i; tab = 'preview'"
              >
                <MethodBadge :method="item.op.method" />
                <span class="t">
                  <b>{{ item.op.summary }}</b>
                  <i>{{ item.op.path }}</i>
                </span>
                <span class="dot" :class="item.op.status" :title="item.op.status === 'done' ? '已完成' : '未完成'" />
              </button>
              <div v-if="!group.ops.length" class="none">暂无接口</div>
            </template>
          </div>
          <div v-if="!spec.ops.length" class="tree-empty">
            还没有接口，点下方「新建接口」开始
          </div>
        </div>
        <div class="aside-foot">
          <button class="foot-main" @click="showAdd = true">
            <span class="p">＋</span> 新建接口
          </button>
          <button class="foot-sub" @click="showCat = true">
            <span class="p">＋</span> 新建分类
          </button>
        </div>
      </aside>
      <!-- 公共说明是文档级内容，单独一页展示一次，不跟随接口切换 -->
      <section v-if="showIntroPage" class="main intro-page">
        <div class="intro-bar">
          <div class="who">
            <h1>公共说明</h1>
            <p>这份说明对所有接口通用，外链访客也会看到</p>
          </div>
          <n-button size="small" type="primary" @click="openIntro">编辑</n-button>
        </div>
        <div v-if="spec.description.trim()" class="intro-doc md-body" v-html="introPageHtml" />
        <n-empty v-else description="还没有公共说明。写清楚怎么对接、怎么鉴权，外部调用方就不用反复问了。">
          <n-button type="primary" @click="openIntro">写公共说明</n-button>
        </n-empty>
      </section>
      <section v-else-if="current" class="main">
        <div class="iface-bar">
          <div class="who">
            <MethodBadge :method="current.method" large />
            <div>
              <div class="name">{{ current.summary }}</div>
              <code>{{ activeServer }}{{ current.path }}</code>
            </div>
          </div>
          <n-dropdown
            :options="[
              { label: '复制路径', key: 'copy' },
              { label: '复制接口', key: 'dup' },
              { label: '删除接口', key: 'del' },
            ]"
            @select="onMore"
          >
            <n-button size="small">更多</n-button>
          </n-dropdown>
        </div>
        <n-tabs v-model:value="tab" type="line" animated class="tabs">
          <n-tab-pane name="preview" tab="预览">
            <PreviewPane :spec="spec" :op="effectiveOp || current" />
          </n-tab-pane>
          <n-tab-pane name="edit" tab="编辑">
            <EditPane :spec="spec" :op="current" @change="markDirty" />
          </n-tab-pane>
          <n-tab-pane name="run" tab="运行">
            <RunPane :op="current" :server="activeServer" :space-id="spaceId" :document-id="docId" :common-params="spec.commonParams" />
          </n-tab-pane>
        </n-tabs>
      </section>
      <section v-else class="blank">
        <n-empty description="添加一个接口后，可以预览文档、编辑字段、在线调试。">
          <n-button type="primary" @click="showAdd = true">添加接口</n-button>
        </n-empty>
      </section>
    </div>

    <n-modal v-model:show="showAdd" preset="dialog" title="添加接口" positive-text="确定" @positive-click="confirmAdd">
      <n-form label-placement="left" label-width="80">
        <n-form-item label="名称"><n-input v-model:value="draft.summary" /></n-form-item>
        <n-form-item label="方法"><n-select v-model:value="draft.method" :options="methods" /></n-form-item>
        <n-form-item label="路径"><n-input v-model:value="draft.path" placeholder="/user/{id}" /></n-form-item>
        <n-form-item label="分类">
          <n-select v-model:value="draft.tag" :options="spec.categories.map((value) => ({ label: value, value }))" />
        </n-form-item>
      </n-form>
    </n-modal>
    <n-modal v-model:show="showCat" preset="dialog" title="添加分类" positive-text="确定" @positive-click="addCategory">
      <n-input v-model:value="newCat" placeholder="例如 用户 / 订单 / 内部" />
    </n-modal>
    <n-modal
      :show="envPanel"
      preset="card"
      title="环境"
      style="width: 620px"
      :bordered="false"
      @update:show="(v: boolean) => (envPanel = v)"
    >
      <EnvironmentsPane :environments="envDraft" />
      <template #footer>
        <n-space justify="end">
          <n-button @click="envPanel = false">取消</n-button>
          <n-button type="primary" @click="saveEnvs">保存环境</n-button>
        </n-space>
      </template>
    </n-modal>
    <n-modal
      :show="introPanel"
      preset="card"
      title="公共说明"
      style="width: 760px"
      :bordered="false"
      @update:show="(v: boolean) => (introPanel = v)"
    >
      <p class="intro-tip">
        所有接口页都会展示这段说明，对外链接同样可见，适合写对接流程、鉴权方式、如何申请密钥。支持 Markdown。
      </p>
      <div class="intro-grid">
        <div class="intro-cell">
          <div class="intro-label">Markdown</div>
          <n-input
            v-model:value="introDraft"
            type="textarea"
            :autosize="{ minRows: 10, maxRows: 14 }"
            placeholder="# 对接说明&#10;&#10;1. 申请 accessKey / secretKey&#10;2. 按签名规则计算 sign&#10;3. 请求头带上 Authorization"
          />
        </div>
        <div class="intro-cell">
          <div class="intro-label">预览</div>
          <div class="intro-preview">
            <div v-if="introDraft.trim()" class="md-body intro-md" v-html="introHtml" />
            <p v-else class="intro-empty">左侧输入后这里显示效果</p>
          </div>
        </div>
      </div>
      <template #footer>
        <n-space justify="end">
          <n-button @click="introPanel = false">取消</n-button>
          <n-button type="primary" :loading="saving" @click="saveIntro">保存说明</n-button>
        </n-space>
      </template>
    </n-modal>
    <n-modal
      :show="paramPanel"
      preset="card"
      title="全局公共参数"
      style="width: 840px"
      :bordered="false"
      @update:show="(v: boolean) => (paramPanel = v)"
    >
      <CommonParamsPane :params="paramDraft" />
      <template #footer>
        <n-space justify="end">
          <n-button @click="paramPanel = false">取消</n-button>
          <n-button type="primary" @click="saveParams">保存参数</n-button>
        </n-space>
      </template>
    </n-modal>
    <n-modal
      :show="searchPanel"
      preset="card"
      class="search-modal"
      :bordered="false"
      :closable="false"
      style="width: 620px"
      @update:show="(v: boolean) => (searchPanel = v)"
    >
      <template #header>
        <div class="sm-head">
          <span class="ico">⌕</span>
          <input
            v-model="searchTerm"
            class="sm-input"
            placeholder="搜索接口名称、路径、分组、说明或参数"
            spellcheck="false"
            @keydown="onSearchKey"
          />
          <span class="kbd">ESC</span>
        </div>
      </template>
      <div class="search-list">
        <div v-if="!searchTerm.trim()" class="search-tip">
          输入关键词即时过滤，点结果直接定位到接口
        </div>
        <div v-else-if="!searchResults.length" class="search-tip">没有匹配的接口</div>
        <button
          v-for="(hit, n) in searchResults"
          :key="hit.i"
          class="search-hit"
          :class="{ on: n === searchActive }"
          @click="openResult(hit.i)"
          @mouseenter="searchActive = n"
        >
          <MethodBadge :method="hit.op.method" />
          <span class="t">
            <b>{{ hit.op.summary }}</b>
            <i>{{ hit.op.path }}</i>
          </span>
          <n-tag v-if="hit.op.tags[0]" size="tiny" :bordered="false">{{ hit.op.tags[0] }}</n-tag>
        </button>
      </div>
      <template #footer>
        <div class="sm-foot">
          <span><em class="kbd-sm">↑↓</em> 选择</span>
          <span><em class="kbd-sm">↵</em> 打开</span>
          <span class="sm-count" v-if="searchTerm.trim()">{{ searchResults.length }} 个结果</span>
        </div>
      </template>
    </n-modal>
    <ExternalAccessModal
      v-if="docId"
      :show="showShare"
      :space-id="spaceId"
      :document-id="docId"
      :title="spec.title"
      @update:show="(value: boolean) => (showShare = value)"
    />
    <n-modal :show="Boolean(renaming)" preset="dialog" title="重命名分类" positive-text="确定" @positive-click="renameCategory" @update:show="(v) => { if (!v) renaming = '' }">
      <n-input v-model:value="renameTo" />
    </n-modal>
  </div>
</template>

<style scoped>
.yapi {
  margin: -26px -32px;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f6f7f9;
  color: #0d1117;
}
header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 10px 18px;
  background: #fff;
  border-bottom: 1px solid #e8eaee;
}
.left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  flex: 1;
}
.back {
  border: 0;
  background: transparent;
  color: #6b7280;
  cursor: pointer;
  padding: 4px 6px;
  border-radius: 6px;
}
.back:hover {
  background: #f3f4f6;
  color: #111827;
}
.title,
/* 环境地址只读展示，改域名走「环境」弹框 */
.env {
  max-width: 260px;
  padding: 5px 10px;
  border: 1px solid #e8eaee;
  border-radius: 6px;
  background: #f7f9fc;
  color: var(--text-2);
  font-size: 12.5px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.env-pick {
  width: 110px;
  flex: none;
}
.sep {
  width: 1px;
  height: 18px;
  background: #e8eaee;
}
.wrap {
  flex: 1;
  display: grid;
  grid-template-columns: 268px 1fr;
  min-height: 0;
}
/* 三区固定：顶栏搜索、中间树可滚动、底部新建常驻，长列表也不会把按钮顶走 */
aside {
  background: #fbfcfd;
  border-right: 1px solid #e8eaee;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.aside-head {
  padding: 12px 12px 8px;
  flex: none;
}
.search-trigger {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  height: 32px;
  padding: 0 10px;
  border: 1px solid #e8eaee;
  border-radius: 8px;
  background: #fff;
  color: var(--muted);
  font-size: 12.5px;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.search-trigger:hover {
  border-color: #cbd5e1;
  box-shadow: var(--shadow-sm);
}
.search-trigger .ico {
  color: var(--faint);
  font-size: 14px;
  line-height: 1;
}
.search-trigger .ph {
  flex: 1;
  text-align: left;
}
.search-trigger .kbd {
  font-size: 11px;
  color: var(--faint);
  border: 1px solid #e8eaee;
  border-radius: 4px;
  padding: 0 4px;
  line-height: 16px;
  background: #fafbfc;
}
.tree {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 4px 12px 12px;
}
.group {
  margin-top: 10px;
}
.cat {
  display: flex;
  align-items: center;
  height: 30px;
}
.cat-name {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 6px;
  border: 0;
  background: transparent;
  padding: 0 4px;
  cursor: pointer;
  font-weight: 600;
  font-size: 12px;
  letter-spacing: 0.02em;
  color: #667085;
  text-transform: none;
}
.cat-label {
  flex: 1;
  text-align: left;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.cat-name em {
  color: var(--faint);
  font-style: normal;
  font-weight: 500;
  font-size: 11.5px;
  background: #f0f2f5;
  border-radius: 999px;
  padding: 0 6px;
  line-height: 17px;
}
.chev {
  color: #9ca3af;
  width: 10px;
  font-size: 10px;
  flex: none;
}
.more {
  border: 0;
  background: transparent;
  color: #9ca3af;
  cursor: pointer;
  width: 24px;
  height: 24px;
  border-radius: 6px;
  opacity: 0;
  transition: opacity 0.12s, background 0.12s;
}
.cat:hover .more {
  opacity: 1;
}
.more:hover {
  background: #eef1f6;
  color: #111;
}
.iface {
  width: 100%;
  display: flex;
  gap: 8px;
  align-items: center;
  border: 0;
  background: transparent;
  padding: 7px 8px 7px 10px;
  cursor: pointer;
  text-align: left;
  border-radius: 8px;
  margin-top: 1px;
  position: relative;
  transition: background 0.12s;
}
.iface:hover {
  background: #f2f5f9;
}
/* 选中态用左侧竖条 + 淡底，比整块加深更克制 */
.iface.active {
  background: var(--accent-soft);
}
.iface.active::before {
  content: "";
  position: absolute;
  left: 0;
  top: 6px;
  bottom: 6px;
  width: 2px;
  border-radius: 2px;
  background: var(--accent);
}
.t {
  flex: 1;
  min-width: 0;
}
.t b {
  display: block;
  font-size: 13px;
  font-weight: 550;
  color: #111827;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.t i {
  display: block;
  font-style: normal;
  color: #9ca3af;
  font-size: 11.5px;
  margin-top: 1px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #f59e0b;
  flex: none;
}
.dot.done {
  background: #10b981;
}
.none {
  color: #d1d5db;
  font-size: 12px;
  padding: 6px 12px 4px;
}
.tree-empty {
  margin: 18px 8px;
  padding: 22px 12px;
  border: 1px dashed #e2e8f0;
  border-radius: 10px;
  color: var(--faint);
  font-size: 12.5px;
  line-height: 1.7;
  text-align: center;
}
.aside-foot {
  flex: none;
  display: grid;
  gap: 6px;
  padding: 10px 12px 16px;
  border-top: 1px solid var(--line-soft);
  background: #fff;
}
/* 主操作实心、次操作描边，避免两个同权重按钮互相抢注意力 */
.foot-main {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  height: 32px;
  border: 1px solid var(--accent);
  border-radius: 8px;
  background: var(--accent);
  color: #fff;
  font-size: 12.5px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s, box-shadow 0.15s;
}
.foot-main:hover {
  background: var(--accent-hover);
  border-color: var(--accent-hover);
  box-shadow: 0 2px 8px rgb(37 99 235 / 22%);
}
.foot-main .p {
  font-size: 13px;
  line-height: 1;
  opacity: 0.9;
}
.foot-sub {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  height: 30px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--muted);
  font-size: 12.5px;
  cursor: pointer;
  transition: color 0.15s, background 0.15s;
}
.foot-sub:hover {
  color: var(--accent);
  background: var(--accent-soft);
}
.foot-sub .p {
  font-size: 12px;
  line-height: 1;
  opacity: 0.75;
}
/* 搜索按命令面板做：头部即输入框，列表紧凑，底部给快捷键提示。
   注意：n-modal 会 teleport 到 body，scoped 样式够不到，这里放全局块。 */

.main {
  overflow: auto;
  padding: 0 28px 32px;
  background: #fff;
  margin: 12px 12px 12px 0;
  border-radius: 14px;
  border: 1px solid #e8eaee;
}
.iface-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 18px 0 8px;
  gap: 12px;
}
.who {
  display: flex;
  gap: 12px;
  align-items: center;
  min-width: 0;
}
.name {
  font-size: 16px;
  font-weight: 650;
  letter-spacing: -0.015em;
}
.who code {
  display: block;
  color: #6b7280;
  font-size: 12px;
  margin-top: 2px;
}
.blank {
  display: grid;
  place-items: center;
  background: #fff;
  margin: 12px 12px 12px 0;
  border-radius: 14px;
  border: 1px solid #e8eaee;
}
:deep(.n-tabs-nav) {
  margin-top: 4px;
}
:deep(.title .n-input__input-el),

</style>
<style>
/* n-modal 被 teleport 到 body，必须用全局样式才能命中 */
.search-modal {
  width: 620px;
  max-width: calc(100vw - 40px);
}
.search-modal .n-card__content {
  padding: 0;
}
.search-modal .n-card-header {
  padding: 0;
  border-bottom: 1px solid var(--line-soft);
}
.search-modal .n-card__footer {
  padding: 0;
}
.sm-head {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 0 16px;
  height: 52px;
}
.sm-head .ico {
  color: var(--faint);
  font-size: 15px;
  line-height: 1;
}
.sm-input {
  flex: 1;
  border: 0;
  outline: none;
  background: transparent;
  font-size: 14px;
  color: var(--text);
  font-family: inherit;
}
.sm-input::placeholder {
  color: var(--faint);
}
.sm-head .kbd {
  font-size: 10.5px;
  color: var(--faint);
  border: 1px solid #e8eaee;
  border-radius: 4px;
  padding: 1px 5px;
  background: #fafbfc;
  letter-spacing: 0.03em;
}
.search-modal .search-list {
  max-height: 396px;
  overflow: auto;
  padding: 6px;
}
.search-modal .search-tip {
  color: var(--faint);
  font-size: 12.5px;
  text-align: center;
  padding: 34px 0;
}
.search-modal .search-hit {
  width: 100%;
  display: flex;
  gap: 10px;
  align-items: center;
  border: 0;
  background: transparent;
  padding: 9px 10px;
  border-radius: 8px;
  cursor: pointer;
  text-align: left;
  transition: background 0.1s;
}
.search-modal .search-hit:hover,
.search-modal .search-hit.on {
  background: var(--accent-soft);
}
.sm-foot {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 8px 16px;
  border-top: 1px solid var(--line-soft);
  background: #fbfcfd;
  font-size: 11.5px;
  color: var(--faint);
}
.sm-foot .kbd-sm {
  font-style: normal;
  border: 1px solid #e8eaee;
  border-radius: 4px;
  padding: 0 4px;
  margin-right: 2px;
  background: #fff;
  font-size: 10.5px;
}
.sm-count {
  margin-left: auto;
}
</style>
<style>
/* 公共说明弹框同样被 teleport 到 body，样式放全局块。
   两栏并排会太窄，改成上下：上面写，下面即时预览。 */
.intro-tip {
  margin: 0 0 12px;
  color: var(--muted);
  font-size: 12.5px;
  line-height: 1.7;
}
.intro-grid {
  display: grid;
  gap: 14px;
}
.intro-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--muted);
  margin-bottom: 6px;
}
.intro-preview {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fff;
  padding: 14px 16px;
  max-height: 260px;
  overflow: auto;
}
.intro-empty {
  margin: 0;
  color: var(--faint);
  font-size: 12.5px;
  text-align: center;
  padding: 22px 0;
}
.intro-md :deep(h2),
.intro-md h2,
.intro-md h3 {
  font-size: 14.5px;
  margin: 0.8em 0 0.35em;
  padding: 0;
  border: 0;
}
.intro-md h2:first-child,
.intro-md h3:first-child {
  margin-top: 0;
}
.intro-md p {
  margin: 0.45em 0;
  font-size: 13.5px;
  line-height: 1.75;
}
.intro-md ul {
  padding-left: 1.2em;
  margin: 0.4em 0;
}
.intro-md li {
  font-size: 13.5px;
}
.intro-md pre {
  margin: 0.6em 0;
  font-size: 12.5px;
}
</style>
<style scoped>
/* 树顶的公共说明入口，样式和接口项区分开：它不是接口，是文档级信息 */
.intro-nav {
  width: 100%;
  display: flex;
  gap: 8px;
  align-items: center;
  border: 0;
  background: transparent;
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
  text-align: left;
  margin-bottom: 6px;
  transition: background 0.12s;
}
.intro-nav:hover {
  background: #f2f5f9;
}
.intro-nav.active {
  background: var(--accent-soft);
}
.intro-nav .ico {
  width: 18px;
  text-align: center;
  color: var(--faint);
  font-size: 13px;
  flex: none;
}
.intro-nav.active .ico {
  color: var(--accent);
}
.intro-nav .t b {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: #111827;
}
.intro-nav .t i {
  display: block;
  font-style: normal;
  font-size: 11.5px;
  color: var(--faint);
  margin-top: 1px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.intro-page {
  padding-bottom: 40px;
}
.intro-bar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  padding: 18px 0 14px;
  border-bottom: 1px solid var(--line-soft);
  margin-bottom: 20px;
}
.intro-bar h1 {
  margin: 0;
  font-size: 17px;
  font-weight: 650;
  letter-spacing: -0.01em;
}
.intro-bar p {
  margin: 5px 0 0;
  font-size: 12.5px;
  color: var(--faint);
}
.intro-doc {
  max-width: 780px;
}
</style>
