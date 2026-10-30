<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { NIcon } from "naive-ui";
import { ChevronForwardOutline } from "@vicons/ionicons5";
import type { Document } from "@/api";

export type TreeNode = {
  id: string;
  title: string;
  isFolder: boolean;
  sourceType: string;
  children: TreeNode[];
};

const props = defineProps<{
  docs: Document[];
  activeId?: string;
  keyword?: string;
  editable?: boolean;
}>();

const emit = defineEmits<{
  open: [doc: Document];
  move: [id: string, parentId: string | null];
}>();

const expanded = ref<Record<string, boolean>>({});
const dragId = ref<string | null>(null);
const dropId = ref<string | null>(null);

/** 把扁平列表还原成树：parent_id 指向不存在的节点时按顶层处理，避免节点凭空消失。 */
const tree = computed<TreeNode[]>(() => {
  const byId = new Map<string, TreeNode>();
  for (const doc of props.docs) {
    byId.set(doc.id, {
      id: doc.id,
      title: doc.title,
      isFolder: Boolean(doc.is_folder),
      sourceType: doc.source_type,
      children: [],
    });
  }
  const roots: TreeNode[] = [];
  for (const doc of props.docs) {
    const node = byId.get(doc.id)!;
    const parent = doc.parent_id ? byId.get(doc.parent_id) : null;
    if (parent && parent.id !== node.id) parent.children.push(node);
    else roots.push(node);
  }
  return roots;
});

const matched = computed(() => {
  const k = (props.keyword || "").trim().toLowerCase();
  if (!k) return null;
  const keep = new Set<string>();
  // 返回子树里是否有命中；有命中就把当前节点也留下，保证祖先路径可见。
  const walk = (nodes: TreeNode[]): boolean => {
    let any = false;
    for (const node of nodes) {
      const childHit = walk(node.children);
      const selfHit = node.title.toLowerCase().includes(k);
      if (selfHit || childHit) {
        keep.add(node.id);
        any = true;
      }
    }
    return any;
  };
  walk(tree.value);
  return keep;
});

function visible(node: TreeNode): boolean {
  if (!matched.value) return true;
  return matched.value.has(node.id);
}

function isOpen(id: string): boolean {
  if (matched.value?.has(id)) return true;
  return expanded.value[id] !== false;
}

function toggle(id: string) {
  expanded.value[id] = !isOpen(id);
}
function onDragStart(e: DragEvent, node: TreeNode) {
  if (!props.editable) return;
  dragId.value = node.id;
  e.dataTransfer?.setData("text/plain", node.id);
}

function onDrop(e: DragEvent, target: TreeNode | null) {
  if (!props.editable) return;
  e.preventDefault();
  e.stopPropagation();
  const id = dragId.value;
  dragId.value = null;
  dropId.value = null;
  if (!id) return;
  if (target && (!target.isFolder || target.id === id)) return;
  emit("move", id, target ? target.id : null);
}

function docOf(node: TreeNode): Document | undefined {
  return props.docs.find((d) => d.id === node.id);
}

function folderCount(node: TreeNode): number {
  return node.children.filter((c) => !c.isFolder).length;
}

watch(
  () => props.activeId,
  (id) => {
    if (!id) return;
    const parent = props.docs.find((d) => d.id === id)?.parent_id;
    if (parent) expanded.value[parent] = true;
  },
  { immediate: true },
);
</script>

<template>
  <div class="tree">
    <template v-for="node in tree" :key="node.id">
      <div
        v-if="visible(node)"
        class="row"
        :class="{
          active: node.id === activeId,
          folder: node.isFolder,
          drop: dropId === node.id,
        }"
        :draggable="editable"
        @dragstart="onDragStart($event, node)"
        @dragover.prevent="node.isFolder && (dropId = node.id)"
        @dragleave="dropId === node.id && (dropId = null)"
        @drop="onDrop($event, node)"
        @click="node.isFolder ? toggle(node.id) : docOf(node) && emit('open', docOf(node)!)"
      >
        <span v-if="node.isFolder" class="caret" :class="{ open: isOpen(node.id) }">
          <n-icon size="12"><ChevronForwardOutline /></n-icon>
        </span>
        <span v-else class="dot" />
        <span class="label" :title="node.title">{{ node.title }}</span>
        <span v-if="node.isFolder && folderCount(node)" class="count">{{ folderCount(node) }}</span>
      </div>

      <div v-if="node.isFolder && isOpen(node.id)" class="children">
        <template v-for="child in node.children" :key="child.id">
          <div
            v-if="visible(child)"
            class="row child"
            :class="{ active: child.id === activeId, folder: child.isFolder, drop: dropId === child.id }"
            :draggable="editable"
            @dragstart="onDragStart($event, child)"
            @dragover.prevent="child.isFolder && (dropId = child.id)"
            @dragleave="dropId === child.id && (dropId = null)"
            @drop="onDrop($event, child)"
            @click.stop="child.isFolder ? toggle(child.id) : docOf(child) && emit('open', docOf(child)!)"
          >
            <span v-if="child.isFolder" class="caret" :class="{ open: isOpen(child.id) }">
              <n-icon size="12"><ChevronForwardOutline /></n-icon>
            </span>
            <span v-else class="dot" />
            <span class="label" :title="child.title">{{ child.title }}</span>
          </div>
          <div v-if="child.isFolder && isOpen(child.id)" class="children deep">
            <div
              v-for="leaf in child.children"
              :key="leaf.id"
              class="row child"
              :class="{ active: leaf.id === activeId }"
              @click.stop="docOf(leaf) && emit('open', docOf(leaf)!)"
            >
              <span class="dot" />
              <span class="label" :title="leaf.title">{{ leaf.title }}</span>
            </div>
          </div>
        </template>
      </div>
    </template>
    <div
      class="row root-drop"
      @dragover.prevent="dropId = '__root'"
      @dragleave="dropId === '__root' && (dropId = null)"
      @drop="onDrop($event, null)"
    >
      拖到这里移到顶层
    </div>
  </div>
</template>

<style scoped>
.tree {
  padding: 4px 0;
}
.row {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 30px;
  padding: 0 10px;
  margin: 1px 6px;
  border-radius: 7px;
  cursor: pointer;
  color: var(--text-2);
  font-size: 13.5px;
  user-select: none;
}
.row:hover {
  background: var(--line-soft);
}
.row.active {
  background: var(--accent-soft);
  color: var(--accent);
  font-weight: 600;
}
.row.drop {
  outline: 1px dashed var(--accent);
  outline-offset: -1px;
}
.caret {
  display: grid;
  place-items: center;
  width: 14px;
  color: var(--faint);
  transition: transform 0.15s ease;
}
.caret.open {
  transform: rotate(90deg);
}
.dot {
  width: 14px;
  height: 14px;
  position: relative;
}
.dot::after {
  content: "";
  position: absolute;
  left: 5px;
  top: 5px;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: #cbd5e1;
}
.row.active .dot::after {
  background: var(--accent);
}
.label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.count {
  font-size: 11px;
  color: var(--faint);
  background: var(--line-soft);
  border-radius: 999px;
  padding: 0 6px;
  line-height: 16px;
}
.children {
  padding-left: 14px;
}
.children.deep {
  padding-left: 14px;
}
.root-drop {
  justify-content: center;
  color: var(--faint);
  font-size: 12px;
  border: 1px dashed var(--line);
  margin-top: 10px;
  display: none;
}
.tree:hover .root-drop {
  display: flex;
}
</style>
