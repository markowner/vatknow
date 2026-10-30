<script setup lang="ts">
import { methodStyle } from "@/openapi";

defineProps<{ method: string; large?: boolean }>();
</script>

<template>
  <span class="badge" :class="{ large }" :style="{ background: methodStyle(method).bg }">{{ method }}</span>
</template>

<style scoped>
.badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: none;
  min-width: 46px;
  padding: 3px 8px;
  border-radius: 5px;
  color: #fff;
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, monospace;
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.04em;
  line-height: 1.4;
}
.large {
  min-width: 54px;
  padding: 5px 11px;
  font-size: 11.5px;
  border-radius: 6px;
}
</style>
