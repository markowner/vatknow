import { createRouter, createWebHistory } from "vue-router";
import { getToken } from "@/api";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", component: () => import("@/views/LoginView.vue"), meta: { public: true } },
    { path: "/p/:slug", component: () => import("@/views/PublicSpaceView.vue"), meta: { public: true } },
    { path: "/p/:slug/:key", component: () => import("@/views/PublicPostView.vue"), meta: { public: true } },
    { path: "/s/:token", component: () => import("@/views/ShareView.vue"), meta: { public: true } },
    {
      path: "/",
      component: () => import("@/layouts/MainLayout.vue"),
      children: [
        { path: "", component: () => import("@/views/SpacesView.vue") },
        { path: "search", component: () => import("@/views/GlobalSearchView.vue") },
        { path: "users", component: () => import("@/views/UsersView.vue") },
        { path: "profile", component: () => import("@/views/ProfileView.vue") },
        { path: "spaces/:id", component: () => import("@/views/OverviewView.vue") },
        { path: "spaces/:id/docs", component: () => import("@/views/DocWikiView.vue") },
        { path: "spaces/:id/docs/all", component: () => import("@/views/DocumentsView.vue") },
        { path: "spaces/:id/docs/:docId", component: () => import("@/views/DocWikiView.vue") },
        { path: "spaces/:id/docs/:docId/edit", component: () => import("@/views/DocView.vue") },
        { path: "spaces/:id/ingest", component: () => import("@/views/IngestView.vue") },
        { path: "spaces/:id/search", component: () => import("@/views/SearchView.vue") },
        { path: "spaces/:id/apis", component: () => import("@/views/ApiStudioView.vue") },
        { path: "spaces/:id/apis/new", component: () => import("@/views/ApiWorkspaceView.vue") },
        { path: "spaces/:id/apis/:docId/edit", component: () => import("@/views/ApiWorkspaceView.vue") },
        { path: "spaces/:id/apis/:docId", component: () => import("@/views/ApiWorkspaceView.vue") },
        { path: "spaces/:id/chat", component: () => import("@/views/ChatView.vue") },
        { path: "spaces/:id/logs", component: () => import("@/views/LogsView.vue") },
        { path: "spaces/:id/settings", component: () => import("@/views/SettingsView.vue") },
      ],
    },
  ],
});

router.beforeEach((to) => {
  const authed = Boolean(getToken());
  if (!to.meta.public && !authed) return "/login";
  if (to.path === "/login" && authed) return "/";
  return true;
});

export default router;
