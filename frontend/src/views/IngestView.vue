<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { NButton, NForm, NFormItem, NInput, NTabPane, NTabs, NUpload, NUploadDragger, useMessage } from "naive-ui";
import type { UploadFileInfo } from "naive-ui";
import { DocsApi } from "@/api";
import { useSpaceId } from "@/composables/useRouteIds";

const router = useRouter();
const message = useMessage();
const spaceId = useSpaceId();
const loading = ref(false);
const markdown = reactive({ title: "", content_md: "" });
const pdf = reactive({ title: "", file: null as File | null });
const paste = reactive({ title: "", html: "" });
const page = reactive({ title: "", url: "" });
const openapi = reactive({ title: "", slug: "", spec: "" });

async function go(docId: string) {
  message.success("已收录并建立索引");
  router.push(`/spaces/${spaceId.value}/docs/${docId}`);
}

async function saveMarkdown() {
  loading.value = true;
  try {
    const doc = await DocsApi.create(spaceId.value, markdown.title, markdown.content_md);
    await go(doc.id);
  } catch (err) {
    message.error(err instanceof Error ? err.message : "保存失败");
  } finally {
    loading.value = false;
  }
}

function onPdf({ file }: { file: UploadFileInfo }) {
  pdf.file = file.file || null;
}

async function savePdf() {
  if (!pdf.file) {
    message.warning("请选择 PDF");
    return;
  }
  loading.value = true;
  try {
    const doc = await DocsApi.upload(spaceId.value, pdf.file, pdf.title || undefined);
    await go(doc.id);
  } catch (err) {
    message.error(err instanceof Error ? err.message : "上传失败");
  } finally {
    loading.value = false;
  }
}

async function savePaste() {
  loading.value = true;
  try {
    const doc = await DocsApi.paste(spaceId.value, paste.title, paste.html, undefined);
    await go(doc.id);
  } catch (err) {
    message.error(err instanceof Error ? err.message : "保存失败");
  } finally {
    loading.value = false;
  }
}

async function saveUrl() {
  loading.value = true;
  try {
    const doc = await DocsApi.fromUrl(spaceId.value, page.url, page.title || undefined);
    await go(doc.id);
  } catch (err) {
    message.error(err instanceof Error ? err.message : "导入失败");
  } finally {
    loading.value = false;
  }
}

async function saveOpenapi() {
  loading.value = true;
  try {
    const doc = await DocsApi.openapi(spaceId.value, openapi.spec, openapi.title || undefined, openapi.slug || undefined);
    message.success("已收录 API 文档");
    router.push(`/spaces/${spaceId.value}/apis/${doc.id}`);
  } catch (err) {
    message.error(err instanceof Error ? err.message : "导入失败");
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="ingest">
    <div class="page-head">
      <div>
        <div class="eyebrow">Ingest</div>
        <h1 class="page-title">收录知识</h1>
        <p class="page-desc">Markdown、PDF、网页与 OpenAPI 文档，收录后自动建立索引。</p>
      </div>
    </div>
    <div class="panel body">
    <n-tabs type="line" animated>
      <n-tab-pane name="md" tab="Markdown">
        <n-form>
          <n-form-item label="标题"><n-input v-model:value="markdown.title" /></n-form-item>
          <n-form-item label="正文">
            <n-input v-model:value="markdown.content_md" type="textarea" :autosize="{ minRows: 14 }" placeholder="# 标题&#10;&#10;在此编写 Markdown" />
          </n-form-item>
          <n-button type="primary" :loading="loading" @click="saveMarkdown">保存并索引</n-button>
        </n-form>
      </n-tab-pane>
      <n-tab-pane name="pdf" tab="PDF">
        <n-form>
          <n-form-item label="标题（可选）"><n-input v-model:value="pdf.title" placeholder="默认使用文件名" /></n-form-item>
          <n-form-item label="文件">
            <n-upload :max="1" accept="application/pdf" :default-upload="false" @change="onPdf">
              <n-upload-dragger>
                <p>点击或拖拽 PDF 到这里，最大 20MB</p>
              </n-upload-dragger>
            </n-upload>
          </n-form-item>
          <n-button type="primary" :loading="loading" @click="savePdf">上传并解析</n-button>
        </n-form>
      </n-tab-pane>
      <n-tab-pane name="paste" tab="粘贴网页">
        <n-form>
          <n-form-item label="标题"><n-input v-model:value="paste.title" /></n-form-item>
          <n-form-item label="HTML 或纯文本">
            <n-input v-model:value="paste.html" type="textarea" :autosize="{ minRows: 12 }" />
          </n-form-item>
          <n-button type="primary" :loading="loading" @click="savePaste">清洗并保存</n-button>
        </n-form>
      </n-tab-pane>
      <n-tab-pane name="url" tab="导入网址">
        <n-form>
          <n-form-item label="网址"><n-input v-model:value="page.url" placeholder="https://example.com/article" /></n-form-item>
          <n-form-item label="标题（可选）"><n-input v-model:value="page.title" placeholder="默认读取网页标题" /></n-form-item>
          <n-button type="primary" :loading="loading" @click="saveUrl">抓取并收录</n-button>
        </n-form>
      </n-tab-pane>
      <n-tab-pane name="openapi" tab="API 文档">
        <p class="lead">推荐在页面上直接添加接口、字段说明和备注，不必先写 JSON。</p>
        <n-button type="primary" style="margin-bottom: 20px" @click="router.push(`/spaces/${spaceId}/apis/new`)">可视化新建</n-button>
        <n-form>
          <n-form-item label="已有 OpenAPI 时，可在此导入">
            <n-input v-model:value="openapi.title" placeholder="标题（可选）" />
          </n-form-item>
          <n-form-item>
            <n-input v-model:value="openapi.spec" type="textarea" :autosize="{ minRows: 10 }" placeholder="粘贴 OpenAPI JSON / YAML" />
          </n-form-item>
          <n-button :loading="loading" @click="saveOpenapi">导入并打开</n-button>
        </n-form>
      </n-tab-pane>
    </n-tabs>
    </div>
  </div>
</template>

<style scoped>
.ingest {
  max-width: 900px;
}
.body {
  padding: 8px 22px 22px;
}
.lead {
  color: var(--text-2);
  margin: 0 0 12px;
}
</style>
