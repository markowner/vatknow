<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { NEmpty, NInput } from "naive-ui";
import { parseOpenApi, type OpenOp } from "@/openapi";
import { renderMarkdown } from "@/utils";
import MethodBadge from "./api-doc/MethodBadge.vue";
import PreviewPane from "./api-doc/PreviewPane.vue";

const props = defineProps<{ spec: string }>();

const parsed = computed(() => parseOpenApi(props.spec));
const keyword = ref("");
const current = ref<OpenOp | null>(null);
const collapsed = ref<Record<string, boolean>>({});
/** 公共说明作为独立一页，默认不抢占接口内容。 */
const showIntro = ref(false);
const introHtml = computed(() => renderMarkdown(parsed.value?.description || ""));

/** 接口对象每次 parse 都会重建，用 method+path 比较，避免高亮永远失效。 */
function isActive(op: OpenOp) {
  return Boolean(current.value && current.value.method === op.method && current.value.path === op.path);
}

watch(
  parsed,
  (spec) => {
    if (!spec) return;
    if (!spec.ops.some((op) => isActive(op))) current.value = spec.ops[0] || null;
  },
  { immediate: true },
);

const groups = computed(() => {
  const spec = parsed.value;
  if (!spec) return [];
  const q = keyword.value.trim().toLowerCase();
  return spec.categories
    .map((cat) => ({
      cat,
      ops: spec.ops.filter((op) => (op.tags[0] || "公共分类") === cat && (!q || `${op.method} ${op.path} ${op.summary}`.toLowerCase().includes(q))),
    }))
    .filter((group) => group.ops.length);
});
</script>

<template>
  <div v-if="!parsed || !parsed.ops.length" class="blank">
    <n-empty description="这个项目还没有已完成的接口，完成并保存后会出现在这里。" />
  </div>
  <div v-else class="doc">
    <aside class="side">
      <div class="brand">
        <div class="name">{{ parsed.title }}</div>
        <div class="meta">
          <span v-if="parsed.version">v{{ parsed.version }}</span>
          <span>{{ parsed.ops.length }} 个接口</span>
        </div>
      </div>
      <n-input v-model:value="keyword" size="small" placeholder="搜索接口" clearable />
      <!-- 公共说明是整份文档通用的，独立一项，不挂在每个接口下面 -->
      <button v-if="parsed.description" class="nav-intro" :class="{ active: showIntro }" @click="showIntro = true">
        <span class="ico">≡</span> 公共说明
      </button>
      <div class="groups">
        <div v-for="group in groups" :key="group.cat" class="group">
          <button class="cat" @click="collapsed[group.cat] = !collapsed[group.cat]">
            <span class="chev">{{ collapsed[group.cat] ? "▸" : "▾" }}</span>
            {{ group.cat }}
            <em>{{ group.ops.length }}</em>
          </button>
          <template v-if="!collapsed[group.cat]">
            <button
              v-for="op in group.ops"
              :key="op.method + op.path"
              class="op"
              :class="{ active: !showIntro && isActive(op) }"
              @click="showIntro = false; current = op"
            >
              <MethodBadge :method="op.method" />
              <span class="t">
                <b>{{ op.summary }}</b>
                <i>{{ op.path }}</i>
              </span>
            </button>
          </template>
        </div>
        <n-empty v-if="!groups.length" description="没有匹配接口" size="small" />
      </div>
    </aside>

    <section v-if="showIntro" class="main intro-main">
      <header class="head">
        <div class="who">
          <h1>公共说明</h1>
          <code>{{ parsed.title }}</code>
        </div>
        <span class="from">外部只读</span>
      </header>
      <div class="md-body intro-md" v-html="introHtml" />
    </section>
    <section v-else-if="current" class="main">
      <header class="head">
        <MethodBadge :method="current.method" large />
        <div class="who">
          <h1>{{ current.summary }}</h1>
          <code>{{ parsed.servers[0] || "" }}{{ current.path }}</code>
        </div>
        <span class="from">外部只读</span>
      </header>
      <!-- 公共说明已独立成一页，这里只渲染接口本身 -->
      <PreviewPane :spec="parsed" :op="current" external />
    </section>
  </div>
</template>

<style scoped>
.doc {
  display: grid;
  grid-template-columns: 264px 1fr;
  gap: 20px;
  align-items: start;
}
.blank {
  padding: 80px 0;
}
.side {
  position: sticky;
  top: 20px;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 16px 12px;
  max-height: calc(100vh - 40px);
  overflow: auto;
  box-shadow: var(--shadow-sm);
}
.brand {
  padding: 0 6px 12px;
}
.name {
  font-size: 15px;
  font-weight: 650;
  letter-spacing: -0.01em;
}
.meta {
  display: flex;
  gap: 8px;
  margin-top: 5px;
  font-size: 12px;
  color: var(--faint);
}
.groups {
  margin-top: 12px;
}
.cat {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 6px;
  border: 0;
  background: transparent;
  padding: 7px 6px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-2);
}
.cat em {
  color: var(--faint);
  font-style: normal;
  font-weight: 500;
}
.chev {
  color: var(--faint);
  width: 10px;
  font-size: 10px;
}
.op {
  width: 100%;
  display: flex;
  gap: 8px;
  align-items: center;
  border: 0;
  background: transparent;
  padding: 7px 6px 7px 10px;
  border-radius: 8px;
  cursor: pointer;
  text-align: left;
}
.op:hover {
  background: #f7f8fa;
}
.op.active {
  background: var(--accent-soft);
}
.t {
  min-width: 0;
}
.t b {
  display: block;
  font-size: 13px;
  font-weight: 550;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.t i {
  display: block;
  font-style: normal;
  font-size: 11.5px;
  color: var(--faint);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.main {
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 20px 24px 8px;
  min-width: 0;
  box-shadow: var(--shadow-sm);
}
.head {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.who {
  min-width: 0;
  flex: 1;
}
.who h1 {
  margin: 0;
  font-size: 18px;
  font-weight: 650;
  letter-spacing: -0.015em;
}
.who code {
  display: block;
  margin-top: 3px;
  font-size: 12.5px;
  color: var(--muted);
  overflow: hidden;
  text-overflow: ellipsis;
}
.from {
  font-size: 12px;
  color: var(--faint);
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 3px 10px;
  flex: none;
}
@media (max-width: 900px) {
  .doc {
    grid-template-columns: 1fr;
  }
  .side {
    position: static;
    max-height: none;
  }
}
</style>
<style scoped>
.nav-intro {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 7px;
  border: 0;
  background: transparent;
  padding: 8px 6px 8px 10px;
  border-radius: 8px;
  cursor: pointer;
  text-align: left;
  margin-top: 10px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-2);
}
.nav-intro:hover {
  background: #f7f8fa;
}
.nav-intro.active {
  background: var(--accent-soft);
  color: var(--accent);
}
.nav-intro .ico {
  color: var(--faint);
  font-size: 13px;
}
.nav-intro.active .ico {
  color: var(--accent);
}
.intro-main {
  padding-bottom: 36px;
}
.intro-md {
  max-width: 780px;
  margin-top: 18px;
}
</style>
