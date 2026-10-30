<script setup lang="ts">
import { reactive, ref, watch } from "vue";
import { NButton, NForm, NFormItem, NInput, NTag, useMessage } from "naive-ui";
import { AuthApi, LLMApi, SiteApi, type LLMSettings } from "@/api";
import { useAuthStore } from "@/stores/auth";
import { useBrandStore } from "@/stores/brand";
import SiteLogo from "@/components/SiteLogo.vue";

const auth = useAuthStore();
const brand = useBrandStore();
const message = useMessage();
const name = ref(auth.user?.name || "");
const email = ref(auth.user?.email || "");
const savingProfile = ref(false);
const pwd = reactive({ old_password: "", new_password: "" });

/** 站点设置只对站点管理员开放。 */
const siteName = ref(brand.brand.site_name);
const siteTagline = ref(brand.brand.site_tagline);
const savingSite = ref(false);
const uploading = ref(false);
const fileInput = ref<HTMLInputElement | null>(null);

// 品牌信息是异步拉回来的，晚到了要补进输入框，否则显示成空。
watch(
  () => brand.brand,
  (next) => {
    siteName.value = next.site_name;
    siteTagline.value = next.site_tagline;
  },
);

async function saveName() {
  savingProfile.value = true;
  try {
    auth.user = await AuthApi.updateMe(name.value.trim(), email.value.trim());
    // 邮箱是登录名，改完要让输入框回到后端规范化后的值（小写、去空格）。
    email.value = auth.user.email;
    name.value = auth.user.name;
    message.success("账号资料已更新");
  } catch (err) {
    message.error(err instanceof Error ? err.message : "保存失败");
  } finally {
    savingProfile.value = false;
  }
}

async function savePassword() {
  try {
    await AuthApi.password(pwd.old_password, pwd.new_password);
    pwd.old_password = "";
    pwd.new_password = "";
    message.success("密码已更新");
  } catch (err) {
    message.error(err instanceof Error ? err.message : "更新失败");
  }
}

async function saveSite() {
  savingSite.value = true;
  try {
    brand.set(
      await SiteApi.update({
        site_name: siteName.value.trim(),
        site_tagline: siteTagline.value.trim(),
      }),
    );
    message.success("站点设置已更新");
  } catch (err) {
    message.error(err instanceof Error ? err.message : "保存失败");
  } finally {
    savingSite.value = false;
  }
}

function pickLogo() {
  fileInput.value?.click();
}

async function onLogoChange(e: Event) {
  const input = e.target as HTMLInputElement;
  const file = input.files?.[0];
  // 选同一个文件两次也要能触发，用完把 value 清掉。
  input.value = "";
  if (!file) return;
  uploading.value = true;
  try {
    brand.set(await SiteApi.uploadLogo(file));
    message.success("Logo 已更新");
  } catch (err) {
    message.error(err instanceof Error ? err.message : "上传失败");
  } finally {
    uploading.value = false;
  }
}

async function resetLogo() {
  uploading.value = true;
  try {
    brand.set(await SiteApi.removeLogo());
    message.success("已恢复默认 Logo");
  } catch (err) {
    message.error(err instanceof Error ? err.message : "操作失败");
  } finally {
    uploading.value = false;
  }
}

/* ---- 模型配置 ---- */
const llm = ref<LLMSettings | null>(null);
const llmForm = reactive({ base_url: "", model: "", api_key: "" });
const savingLlm = ref(false);
const testingLlm = ref(false);

function syncLlm(next: LLMSettings) {
  llm.value = next;
  llmForm.base_url = next.base_url;
  llmForm.model = next.model;
  // Key 不回显，留空表示"不修改"。
  llmForm.api_key = "";
}

async function loadLlm() {
  if (!brand.isSiteAdmin) return;
  try {
    syncLlm(await LLMApi.get());
  } catch (err) {
    message.error(err instanceof Error ? err.message : "读取模型配置失败");
  }
}

async function saveLlm() {
  savingLlm.value = true;
  try {
    syncLlm(
      await LLMApi.update({
        base_url: llmForm.base_url,
        model: llmForm.model,
        // 空串会被后端忽略，避免"清空输入框再保存"把 Key 删掉。
        api_key: llmForm.api_key || undefined,
      }),
    );
    message.success("模型配置已保存");
  } catch (err) {
    message.error(err instanceof Error ? err.message : "保存失败");
  } finally {
    savingLlm.value = false;
  }
}

async function testLlm() {
  testingLlm.value = true;
  try {
    const res = await LLMApi.test();
    message.success(`连接正常，${res.model} 回话：${res.reply}`);
  } catch (err) {
    message.error(err instanceof Error ? err.message : "测试失败");
  } finally {
    testingLlm.value = false;
  }
}

async function clearLlmKey() {
  savingLlm.value = true;
  try {
    syncLlm(await LLMApi.update({ clear_api_key: true }));
    message.success("已清除设置页的 Key，回退到环境变量");
  } catch (err) {
    message.error(err instanceof Error ? err.message : "操作失败");
  } finally {
    savingLlm.value = false;
  }
}

// 品牌信息回来后才确定是不是超管，那时再去读模型配置。
watch(
  () => brand.isSiteAdmin,
  (isAdmin) => {
    if (isAdmin) loadLlm();
  },
  { immediate: true },
);
</script>

<template>
  <div class="profile">
    <div class="page-head">
      <div>
        <div class="eyebrow">Account</div>
        <h1 class="page-title">账号设置</h1>
        <p class="page-desc">修改显示名称和登录密码。</p>
      </div>
    </div>
    <section class="panel block">
      <header><h3>账号资料</h3></header>
      <n-form label-placement="left" label-width="80">
        <n-form-item label="邮箱">
          <n-input v-model:value="email" placeholder="you@example.com" style="max-width: 320px" />
        </n-form-item>
        <n-form-item label="名称">
          <n-input v-model:value="name" style="max-width: 320px" />
        </n-form-item>
        <n-button type="primary" :loading="savingProfile" @click="saveName">保存</n-button>
      </n-form>
      <p class="hint">邮箱同时是登录账号，修改后用新邮箱登录。</p>
    </section>
    <section class="panel block">
      <header><h3>修改密码</h3></header>
      <n-form label-placement="left" label-width="80">
        <n-form-item label="原密码"><n-input v-model:value="pwd.old_password" type="password" show-password-on="click" style="max-width: 320px" /></n-form-item>
        <n-form-item label="新密码"><n-input v-model:value="pwd.new_password" type="password" show-password-on="click" placeholder="至少 8 位" style="max-width: 320px" /></n-form-item>
        <n-button type="primary" @click="savePassword">更新密码</n-button>
      </n-form>
    </section>

    <section v-if="brand.isSiteAdmin" class="panel block">
      <header>
        <h3>站点设置</h3>
        <p class="hint">改的是全站标题和 Logo，出现在左上角、登录页和浏览器标签。仅站点管理员可见。</p>
      </header>
      <n-form label-placement="left" label-width="80">
        <n-form-item label="站点名称">
          <n-input v-model:value="siteName" maxlength="80" style="max-width: 320px" />
        </n-form-item>
        <n-form-item label="副标题">
          <n-input v-model:value="siteTagline" maxlength="120" placeholder="例如 Docs · API" style="max-width: 320px" />
        </n-form-item>
        <n-form-item label="Logo">
          <div class="logo-row">
            <div class="logo-preview">
              <SiteLogo :src="brand.logoUrl" :size="44" />
            </div>
            <div class="logo-acts">
              <n-button size="small" :loading="uploading" @click="pickLogo">上传图片</n-button>
              <n-button v-if="brand.brand.has_logo" size="small" quaternary :disabled="uploading" @click="resetLogo">
                恢复默认
              </n-button>
              <p class="logo-tip">PNG / JPEG / WebP / SVG / GIF，不超过 512KB。方形图片效果最好。</p>
            </div>
            <input
              ref="fileInput"
              type="file"
              accept="image/png,image/jpeg,image/webp,image/svg+xml,image/gif"
              hidden
              @change="onLogoChange"
            />
          </div>
        </n-form-item>
        <n-button type="primary" :loading="savingSite" @click="saveSite">保存站点设置</n-button>
      </n-form>
    </section>

    <section v-if="brand.isSiteAdmin && llm" class="panel block">
      <header>
        <h3>
          模型配置
          <n-tag v-if="llm.has_api_key" size="small" type="success" :bordered="false">已配置</n-tag>
          <n-tag v-else size="small" type="warning" :bordered="false">未配置</n-tag>
        </h3>
        <p class="hint">
          换模型供应商时在这里改，改完立即生效，不用改代码也不用重启。
        </p>
      </header>
      <n-form label-placement="left" label-width="96">
        <n-form-item label="接口地址">
          <n-input v-model:value="llmForm.base_url" placeholder="https://api.openai.com/v1" style="max-width: 380px" />
        </n-form-item>
        <n-form-item label="对话模型">
          <n-input v-model:value="llmForm.model" placeholder="gpt-4o-mini" style="max-width: 380px" />
        </n-form-item>
        <n-form-item label="API Key">
          <div class="key-row">
            <n-input
              v-model:value="llmForm.api_key"
              type="password"
              show-password-on="click"
              :placeholder="llm.has_api_key ? `已配置 ${llm.api_key_hint}，留空表示不修改` : '填入 API Key'"
              style="max-width: 380px"
            />
            <span class="key-src">
              {{ llm.api_key_source === "settings" ? "来自设置页" : llm.api_key_source === "env" ? "来自环境变量" : "未设置" }}
            </span>
          </div>
        </n-form-item>
        <n-form-item label="向量模型">
          <div class="vec-row">
            <span class="vec-name">{{ llm.embedding_model }}（{{ llm.embedding_dim }} 维）</span>
            <span class="hint inline">固定在环境变量，换模型会让已有文档的向量失效，所以这里不开放。</span>
          </div>
        </n-form-item>
        <div class="llm-acts">
          <n-button type="primary" :loading="savingLlm" @click="saveLlm">保存</n-button>
          <n-button :loading="testingLlm" :disabled="!llm.has_api_key" @click="testLlm">测试连接</n-button>
          <n-button
            v-if="llm.api_key_source === 'settings'"
            quaternary
            :disabled="savingLlm"
            @click="clearLlmKey"
          >
            清除设置页 Key
          </n-button>
        </div>
      </n-form>
    </section>
  </div>
</template>

<style scoped>
.profile {
  max-width: 620px;
}
.block {
  padding: 20px 22px;
  margin-bottom: 16px;
}
.block header {
  margin-bottom: 16px;
}
.block h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 650;
}
.hint {
  margin: 6px 0 0;
  font-size: 12.5px;
  color: var(--faint);
  line-height: 1.6;
}
.logo-row {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}
.logo-preview {
  width: 60px;
  height: 60px;
  border: 1px solid var(--line);
  border-radius: 12px;
  display: grid;
  place-items: center;
  background: #fafbfc;
  flex: none;
}
.logo-acts {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.logo-tip {
  width: 100%;
  margin: 2px 0 0;
  font-size: 11.5px;
  color: var(--faint);
  line-height: 1.55;
}
.block h3 {
  display: flex;
  align-items: center;
  gap: 8px;
}
.key-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.key-src {
  font-size: 11.5px;
  color: var(--faint);
  white-space: nowrap;
}
.vec-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.vec-name {
  font-size: 13px;
  color: var(--text-2);
}
.hint.inline {
  margin: 0;
  max-width: 420px;
}
.llm-acts {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
</style>
