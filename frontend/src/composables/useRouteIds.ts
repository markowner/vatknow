import { computed } from "vue";
import { useRoute } from "vue-router";

/**
 * 路由里的空间 / 文档 id。
 *
 * 本项目的页面都被 keep-alive 缓存，离开 `/spaces/:id/*` 后实例仍然活着，
 * 此时 `route.params.id` 已经是 undefined。直接 `String()` 会得到字符串
 * "undefined"，它看起来像合法值，于是被 watch 到的加载函数原样发给后端，
 * 后端 UUID 校验直接 422 —— 报错信息就是「invalid character: found `u` at 0」。
 *
 * 所以这里统一把缺失的参数收敛成空串，调用方在发请求前用
 * `if (!spaceId.value) return` 跳过。
 */
function param(get: () => unknown) {
  return computed(() => {
    const value = get();
    return typeof value === "string" ? value : "";
  });
}

export function useSpaceId() {
  const route = useRoute();
  return param(() => route.params.id);
}

export function useDocId() {
  const route = useRoute();
  return param(() => route.params.docId);
}
