import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { AuthApi, clearToken, getToken, setToken, type User } from "@/api";
import { useBrandStore } from "@/stores/brand";

export const useAuthStore = defineStore("auth", () => {
  const user = ref<User | null>(null);
  const token = ref<string | null>(getToken());
  const ready = ref(false);
  const isAuthed = computed(() => Boolean(token.value));

  async function bootstrap() {
    if (!token.value) {
      ready.value = true;
      return;
    }
    try {
      user.value = await AuthApi.me();
    } catch {
      token.value = null;
      clearToken();
    } finally {
      ready.value = true;
    }
  }

  async function login(email: string, password: string) {
    const res = await AuthApi.login(email, password);
    setToken(res.access_token);
    token.value = res.access_token;
    user.value = res.user;
    // 登录后「我是不是站点管理员」会变，品牌信息要重新读一次。
    await useBrandStore().load(true);
  }

  async function register(email: string, password: string, name: string) {
    const res = await AuthApi.register(email, password, name);
    setToken(res.access_token);
    token.value = res.access_token;
    user.value = res.user;
    await useBrandStore().load(true);
  }

  function logout() {
    clearToken();
    token.value = null;
    user.value = null;
    // 退回公开品牌信息，别把超管标记留给下一个人。
    useBrandStore().load(false);
  }

  return { user, token, ready, isAuthed, bootstrap, login, register, logout };
});
