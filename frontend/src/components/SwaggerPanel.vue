<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from "vue";

const props = defineProps<{ spec: string }>();
const el = ref<HTMLDivElement | null>(null);
let ui: { destroy?: () => void } | null = null;

function parseSpec(raw: string): object | null {
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function loadScript(src: string) {
  return new Promise<void>((resolve, reject) => {
    const existed = document.querySelector(`script[src="${src}"]`);
    if (existed) {
      resolve();
      return;
    }
    const script = document.createElement("script");
    script.src = src;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("无法加载 Swagger UI"));
    document.body.appendChild(script);
  });
}

function loadCss(href: string) {
  if (document.querySelector(`link[href="${href}"]`)) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = href;
  document.head.appendChild(link);
}

async function render() {
  const spec = parseSpec(props.spec);
  if (!el.value || !spec) return;
  loadCss("https://unpkg.com/swagger-ui-dist@5.17.14/swagger-ui.css");
  await loadScript("https://unpkg.com/swagger-ui-dist@5.17.14/swagger-ui-bundle.js");
  const SwaggerUIBundle = (window as unknown as { SwaggerUIBundle: (opts: object) => { destroy?: () => void } }).SwaggerUIBundle;
  el.value.innerHTML = "";
  ui = SwaggerUIBundle({
    spec,
    domNode: el.value,
    deepLinking: false,
    tryItOutEnabled: true,
    docExpansion: "list",
    defaultModelsExpandDepth: 1,
  });
}

onMounted(render);
watch(() => props.spec, render);
onUnmounted(() => ui?.destroy?.());
</script>

<template>
  <div>
    <div v-if="!parseSpec(spec)" class="plain">当前内容不是有效的 OpenAPI JSON，无法渲染调试台。</div>
    <div ref="el" class="swagger-host" />
  </div>
</template>

<style scoped>
.plain {
  padding: 16px;
  color: #6b7280;
}
.swagger-host {
  background: #fff;
}
</style>
