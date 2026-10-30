<script setup lang="ts">
import { reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { NButton, NForm, NFormItem, NInput, NTabPane, NTabs, useMessage } from "naive-ui";
import { useAuthStore } from "@/stores/auth";
import { useBrandStore } from "@/stores/brand";
import SiteLogo from "@/components/SiteLogo.vue";

const router = useRouter();
const auth = useAuthStore();
const brand = useBrandStore();
const message = useMessage();
const tab = ref("login");
const loading = ref(false);
// 不预填账号密码：预填会让每次登录都被默认值带回去，看起来像"账号换不掉"。
const loginForm = reactive({ email: "", password: "" });
const registerForm = reactive({ name: "", email: "", password: "" });

async function submitLogin() {
  loading.value = true;
  try {
    await auth.login(loginForm.email, loginForm.password);
    message.success("登录成功");
    router.replace("/");
  } catch (err) {
    message.error(err instanceof Error ? err.message : "登录失败");
  } finally {
    loading.value = false;
  }
}

async function submitRegister() {
  loading.value = true;
  try {
    await auth.register(registerForm.email, registerForm.password, registerForm.name || registerForm.email.split("@")[0]);
    message.success("注册成功");
    router.replace("/");
  } catch (err) {
    message.error(err instanceof Error ? err.message : "注册失败");
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="wrap">
    <div class="hero">
      <div class="mark">
        <SiteLogo :src="brand.logoUrl" :size="26" />
        <span>{{ brand.siteName }}</span>
      </div>
      <h1>把分散的资料，收成可检索、可提问的知识库。</h1>
      <p>Markdown、PDF、网页与 API 文档同处一室。检索有出处，问答有依据。</p>
    </div>
    <aside class="panel">
      <n-tabs v-model:value="tab" type="line" animated default-value="login">
        <n-tab-pane name="login" tab="登录">
          <n-form :model="loginForm" @submit.prevent="submitLogin">
            <n-form-item label="邮箱">
              <n-input v-model:value="loginForm.email" size="large" />
            </n-form-item>
            <n-form-item label="密码">
              <n-input v-model:value="loginForm.password" type="password" size="large" show-password-on="click" />
            </n-form-item>
            <n-button type="primary" block size="large" attr-type="submit" :loading="loading">进入知识库</n-button>
          </n-form>
        </n-tab-pane>
        <n-tab-pane name="register" tab="注册">
          <n-form :model="registerForm" @submit.prevent="submitRegister">
            <n-form-item label="名称">
              <n-input v-model:value="registerForm.name" size="large" placeholder="怎么称呼你" />
            </n-form-item>
            <n-form-item label="邮箱">
              <n-input v-model:value="registerForm.email" size="large" placeholder="you@example.com" />
            </n-form-item>
            <n-form-item label="密码">
              <n-input v-model:value="registerForm.password" type="password" size="large" show-password-on="click" placeholder="至少 8 位" />
            </n-form-item>
            <n-button type="primary" block size="large" attr-type="submit" :loading="loading">创建账号并进入</n-button>
          </n-form>
        </n-tab-pane>
      </n-tabs>
    </aside>
  </div>
</template>

<style scoped>
.wrap {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 1fr 460px;
  background: #0b1220;
}
.hero {
  color: #fff;
  padding: 80px 88px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  background:
    radial-gradient(900px 420px at 12% 18%, rgb(37 99 235 / 42%), transparent 55%),
    radial-gradient(700px 360px at 80% 90%, rgb(59 130 246 / 20%), transparent 50%),
    #070b14;
}
.mark {
  display: flex;
  align-items: center;
  gap: 9px;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: #93c5fd;
}
.hero h1 {
  font-size: 42px;
  font-weight: 700;
  letter-spacing: -0.03em;
  line-height: 1.25;
  max-width: 560px;
  margin: 24px 0 16px;
}
.hero p {
  max-width: 460px;
  color: #94a3b8;
  line-height: 1.8;
  font-size: 16px;
}
.panel {
  background: #fff;
  padding: 72px 48px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}
@media (max-width: 860px) {
  .wrap {
    grid-template-columns: 1fr;
  }
  .hero {
    display: none;
  }
  .panel {
    min-height: 100vh;
  }
}
</style>
