<script setup lang="ts">
/**
 * 站点 Logo。
 *
 * 没有上传自定义 Logo 时用内置的默认图形：V 字形（VatKnow）叠在两张文档上，
 * 表达「知识库」。图形全部走 currentColor / 固定色，不依赖外部资源。
 */
import { computed } from "vue";

const props = withDefaults(
  defineProps<{
    /** 上传的 Logo 地址，为空则显示默认图形。 */
    src?: string | null;
    /** 显示边长，单位 px。 */
    size?: number;
  }>(),
  { src: null, size: 28 },
);

/** 圆角按比例走，20px 和 28px 下观感一致。 */
const radius = computed(() => `${Math.round(props.size * 0.27)}px`);
</script>

<template>
  <img
    v-if="src"
    :src="src"
    :width="size"
    :height="size"
    alt="站点 Logo"
    class="site-logo"
    :style="{ borderRadius: radius }"
  />
  <svg
    v-else
    :width="size"
    :height="size"
    viewBox="0 0 32 32"
    class="site-logo"
    :style="{ borderRadius: radius }"
    role="img"
    aria-label="站点 Logo"
  >
    <defs>
      <linearGradient :id="`logo-grad`" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#3b82f6" />
        <stop offset="1" stop-color="#1d4ed8" />
      </linearGradient>
    </defs>
    <rect width="32" height="32" rx="8.5" fill="url(#logo-grad)" />
    <!-- 后面那张文档：淡一点，做出叠层纵深 -->
    <rect x="8.4" y="7.4" width="10.6" height="14" rx="2.6" fill="#ffffff" opacity="0.45" />
    <!-- 前面那张文档 -->
    <rect x="13" y="10.6" width="10.6" height="14" rx="2.6" fill="#ffffff" />
    <path
      d="M15.6 15.4 L18.3 20 L21 15.4"
      fill="none"
      stroke="#2563eb"
      stroke-width="1.8"
      stroke-linecap="round"
      stroke-linejoin="round"
    />
  </svg>
</template>

<style scoped>
.site-logo {
  display: block;
  flex: none;
  object-fit: cover;
}
</style>
