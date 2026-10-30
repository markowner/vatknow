import { createApp } from "vue";
import { createPinia } from "pinia";
import App from "./App.vue";
import router from "./router";
import { useAuthStore } from "./stores/auth";
import { useBrandStore } from "./stores/brand";
import "./styles.css";

const app = createApp(App);
app.use(createPinia());
app.use(router);

const auth = useAuthStore();
const brand = useBrandStore();
// 先确定是否已登录，再决定读公开品牌接口还是带权限的那个。
auth.bootstrap().then(async () => {
  await brand.load(auth.isAuthed);
  app.mount("#app");
});
