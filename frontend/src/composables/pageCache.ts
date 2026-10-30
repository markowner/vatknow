import {
  getCurrentInstance,
  nextTick,
  onActivated,
  onDeactivated,
  onMounted,
  onUnmounted,
} from "vue";

/**
 * 页面被 keep-alive 缓存后的生命周期封装。
 *
 * 组件一旦进缓存，onMounted / onUnmounted 只在第一次进入和真正销毁时各触发一次，
 * 所以「每次回到页面都要做的事」（刷新数据）必须挂在 onActivated，
 * 而「离开时该收起来的」必须挂在 onDeactivated —— 否则页面已经切走了，
 * 它的全局键盘监听还在，快捷键会串到别的页面去。
 *
 * leave 可能因为「先缓存再销毁」而触发两次，调用方应保证它是幂等的
 * （移除监听、清定时器这类操作天然幂等）。
 */
export function usePageLifecycle(options: {
  /** 每次进入页面（含首次）调用。 */
  enter?: () => void;
  /** 每次离开页面调用，也可能是组件销毁。 */
  leave?: () => void;
}) {
  const { enter, leave } = options;
  let first = true;

  onMounted(() => enter?.());

  onActivated(() => {
    // 首次挂载时 onActivated 紧跟 onMounted 触发，跳过以免重复加载一次。
    if (first) {
      first = false;
      return;
    }
    enter?.();
  });

  onDeactivated(() => leave?.());
  onUnmounted(() => leave?.());
}

/**
 * 记住页面内滚动容器的位置，回到页面时还原。
 *
 * keep-alive 只保住 DOM，滚动位置会被「重新拉数据 → 内容变短 → 再变长」冲掉；
 * 外层的 .n-layout-content 还是所有页面共用的，切页时会沿用上一页的位置。
 * 两处都得自己存、自己还原。
 *
 * 元素用「从根节点往下的下标路径」定位：同一组件实例的 DOM 结构稳定，路径不会错位。
 */
type ScrollEntry = { path: number[] | "layout"; top: number };

const saved = new Map<number, ScrollEntry[]>();

function pathOf(root: HTMLElement, el: HTMLElement): number[] | null {
  const path: number[] = [];
  let node: HTMLElement | null = el;
  while (node && node !== root) {
    const parent: HTMLElement | null = node.parentElement;
    if (!parent) return null;
    path.unshift([...parent.children].indexOf(node));
    node = parent;
  }
  return node === root ? path : null;
}

function resolve(root: HTMLElement, path: number[]): HTMLElement | null {
  let node: HTMLElement = root;
  for (const i of path) {
    const next = node.children[i] as HTMLElement | undefined;
    if (!next) return null;
    node = next;
  }
  return node;
}

function layoutScroller(): HTMLElement | null {
  return document.querySelector<HTMLElement>(".n-layout-content");
}

function collect(root: HTMLElement | null): ScrollEntry[] {
  const list: ScrollEntry[] = [];
  const main = layoutScroller();
  if (main) list.push({ path: "layout", top: main.scrollTop });
  if (!root) return list;
  for (const el of [root, ...root.querySelectorAll<HTMLElement>("*")]) {
    if (el.scrollTop <= 0) continue;
    const style = window.getComputedStyle(el);
    if (style.overflowY !== "auto" && style.overflowY !== "scroll") continue;
    const path = pathOf(root, el);
    if (path) list.push({ path, top: el.scrollTop });
  }
  return list;
}

/**
 * 数据是异步拉回来的，内容高度会变，所以在一小段时间内反复尝试，
 * 等容器撑到足够高再一次性落位。
 */
function restore(root: HTMLElement | null, entries: ScrollEntry[]) {
  let attempt = 0;
  const apply = () => {
    let pending = false;
    for (const entry of entries) {
      const el = entry.path === "layout" ? layoutScroller() : root && resolve(root, entry.path);
      if (!el) continue;
      if (el.scrollHeight - el.clientHeight < entry.top) {
        pending = true;
        continue;
      }
      if (Math.abs(el.scrollTop - entry.top) > 1) el.scrollTop = entry.top;
    }
    attempt += 1;
    if (pending && attempt < 10) window.setTimeout(apply, 100);
  };
  nextTick(apply);
}

export function useScrollMemory() {
  const instance = getCurrentInstance();
  const root = () => (instance?.proxy?.$el as HTMLElement | null) ?? null;
  const key = instance?.uid ?? 0;
  let live = true;

  /**
   * keep-alive 在触发 deactivated 之前就已经把 DOM 从 document 摘出去了，
   * 那时读 scrollTop 一律是 0，所以必须「边滚边记」，不能等离开时再采样。
   *
   * 滚动事件本身触发得很密，但每个页面只有一两个滚动容器、只是读几个数字，
   * 直接同步记即可，用 rAF 反而可能在切页瞬间丢掉最后一次记录。
   */
  const onScroll = () => {
    if (!live) return;
    saved.set(key, collect(root()));
  };

  onMounted(() => {
    // 捕获阶段监听，页面内任意滚动容器都能收到。
    window.addEventListener("scroll", onScroll, true);
  });

  onActivated(() => {
    live = true;
    const entries = saved.get(key);
    if (!entries) {
      // 外层滚动容器是所有页面共用的，没存过位置的页面要从顶部开始，
      // 否则会沿用上一页的滚动位置。
      const main = layoutScroller();
      if (main) main.scrollTop = 0;
      return;
    }
    saved.delete(key);
    restore(root(), entries);
  });

  onDeactivated(() => {
    live = false;
  });

  onUnmounted(() => {
    live = false;
    window.removeEventListener("scroll", onScroll, true);
    saved.delete(key);
  });
}
