<script setup lang="ts">
import { computed, h, onMounted, ref } from "vue";
import {
  NButton,
  NEmpty,
  NInput,
  NModal,
  NSelect,
  NSpin,
  NSwitch,
  NTag,
  useDialog,
  useMessage,
} from "naive-ui";
import { AuthApi, UsersApi, type AdminUser } from "@/api";
import { useBrandStore } from "@/stores/brand";
import { useAuthStore } from "@/stores/auth";
import { formatTime } from "@/utils";

const message = useMessage();
const dialog = useDialog();
const brand = useBrandStore();
const auth = useAuthStore();

const users = ref<AdminUser[]>([]);
const loading = ref(false);
const keyword = ref("");
/** 正在改行的 user id，用来只让那一行转圈，不是整页。 */
const busyId = ref<string | null>(null);

const canManage = computed(() => brand.isSiteAdmin);

const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase();
  if (!kw) return users.value;
  return users.value.filter(
    (u) => u.email.toLowerCase().includes(kw) || u.name.toLowerCase().includes(kw),
  );
});

const activeCount = computed(() => users.value.filter((u) => u.is_active).length);
const adminCount = computed(() => users.value.filter((u) => u.is_site_admin && u.is_active).length);

async function load() {
  if (!canManage.value) return;
  loading.value = true;
  try {
    users.value = await UsersApi.list();
  } catch (err) {
    message.error(err instanceof Error ? err.message : "读取用户失败");
  } finally {
    loading.value = false;
  }
}

async function patch(user: AdminUser, body: Parameters<typeof UsersApi.update>[1]) {
  busyId.value = user.id;
  try {
    const next = await UsersApi.update(user.id, body);
    const idx = users.value.findIndex((u) => u.id === next.id);
    if (idx >= 0) users.value[idx] = next;
    return next;
  } catch (err) {
    message.error(err instanceof Error ? err.message : "更新失败");
    return null;
  } finally {
    busyId.value = null;
  }
}

/** 停用会把对方立刻踢下线，属于不可逆的打扰，必须二次确认。 */
function toggleActive(user: AdminUser, next: boolean) {
  if (!next) {
    dialog.warning({
      title: `停用「${user.name}」`,
      content: "该账号将立即无法登录，已登录的会话也会失效。空间和数据都会保留，之后可以再启用。",
      positiveText: "确认停用",
      negativeText: "取消",
      onPositiveClick: () => patch(user, { is_active: false }),
    });
    return;
  }
  patch(user, { is_active: true });
}

async function toggleAdmin(user: AdminUser, next: boolean) {
  if (!next) {
    dialog.warning({
      title: `取消「${user.name}」的站点管理员`,
      content: "取消后他将无法进入用户管理、改全站设置和模型配置。",
      positiveText: "确认取消",
      negativeText: "取消",
      onPositiveClick: () => patch(user, { is_site_admin: false }),
    });
    return;
  }
  await patch(user, { is_site_admin: true });
}

/* ---------- 编辑资料 ---------- */
const editing = ref<AdminUser | null>(null);
const editName = ref("");
const editEmail = ref("");
const savingEdit = ref(false);

function openEdit(user: AdminUser) {
  editing.value = user;
  editName.value = user.name;
  editEmail.value = user.email;
}

async function saveEdit() {
  if (!editing.value) return;
  savingEdit.value = true;
  const body: { name?: string; email?: string } = {};
  if (editName.value.trim() && editName.value.trim() !== editing.value.name) {
    body.name = editName.value.trim();
  }
  if (editEmail.value.trim() && editEmail.value.trim() !== editing.value.email) {
    body.email = editEmail.value.trim();
  }
  if (!Object.keys(body).length) {
    editing.value = null;
    savingEdit.value = false;
    return;
  }
  const ok = await patch(editing.value, body);
  savingEdit.value = false;
  if (ok) {
    message.success("资料已更新");
    // 改的可能是自己，同步一下左上角的显示名。
    if (ok.id === auth.user?.id) auth.user = await AuthApi.me();
    editing.value = null;
  }
}

/* ---------- 重置密码 ---------- */
const resetting = ref<AdminUser | null>(null);
const newPassword = ref("");
const savingPassword = ref(false);

function openReset(user: AdminUser) {
  resetting.value = user;
  newPassword.value = "";
}

async function savePassword() {
  if (!resetting.value) return;
  if (newPassword.value.length < 8) {
    message.warning("密码至少 8 位");
    return;
  }
  savingPassword.value = true;
  try {
    await UsersApi.resetPassword(resetting.value.id, newPassword.value);
    message.success(`已重置「${resetting.value.name}」的密码，请把新密码告知对方`);
    resetting.value = null;
  } catch (err) {
    message.error(err instanceof Error ? err.message : "重置失败");
  } finally {
    savingPassword.value = false;
  }
}

const roleLabel: Record<string, string> = {
  owner: "所有者",
  admin: "管理员",
  editor: "编辑",
  viewer: "只读",
};

onMounted(() => {
  load();
});
</script>

<template>
  <div>
    <div class="page-head">
      <div>
        <div class="eyebrow">Admin</div>
        <h1 class="page-title">用户管理</h1>
        <p class="page-desc">
          共 {{ users.length }} 个账号，{{ activeCount }} 个可用，{{ adminCount }} 个站点管理员。
          <span v-if="!canManage">只有站点管理员可以进入这里。</span>
        </p>
      </div>
      <div class="head-acts">
        <n-input v-model:value="keyword" placeholder="搜索邮箱或名称" clearable style="width: 220px" />
        <n-button :loading="loading" @click="load">刷新</n-button>
      </div>
    </div>

    <div v-if="!canManage" class="panel">
      <n-empty description="只有站点管理员可以管理用户" />
    </div>

    <n-spin v-else :show="loading">
      <div v-if="!filtered.length" class="panel">
        <n-empty :description="keyword ? '没有匹配的用户' : '还没有用户'" />
      </div>

      <div v-else class="list">
        <article v-for="user in filtered" :key="user.id" class="user-card" :class="{ off: !user.is_active }">
          <div class="head">
            <div class="avatar" :class="{ muted: !user.is_active }">{{ user.name.slice(0, 1) }}</div>
            <div class="ident">
              <div class="name-row">
                <span class="name">{{ user.name }}</span>
                <n-tag v-if="user.is_site_admin" size="tiny" :bordered="false" type="warning">站点管理员</n-tag>
                <n-tag v-if="!user.is_active" size="tiny" :bordered="false" type="error">已停用</n-tag>
                <n-tag v-if="user.id === auth.user?.id" size="tiny" :bordered="false">我</n-tag>
              </div>
              <div class="email">{{ user.email }}</div>
            </div>
            <div class="switches">
              <label class="sw">
                <span>超管</span>
                <n-switch
                  size="small"
                  :value="user.is_site_admin"
                  :loading="busyId === user.id"
                  @update:value="(v: boolean) => toggleAdmin(user, v)"
                />
              </label>
              <label class="sw">
                <span>启用</span>
                <n-switch
                  size="small"
                  :value="user.is_active"
                  :loading="busyId === user.id"
                  @update:value="(v: boolean) => toggleActive(user, v)"
                />
              </label>
            </div>
          </div>

          <div class="meta">
            <span>注册于 {{ formatTime(user.created_at) }}</span>
            <span class="dot">·</span>
            <span>{{ user.space_count }} 个空间</span>
          </div>

          <div v-if="user.spaces.length" class="spaces">
            <span v-for="s in user.spaces" :key="s.id" class="space-chip">
              {{ s.name }}
              <em>{{ roleLabel[s.role] || s.role }}</em>
            </span>
          </div>

          <div class="acts">
            <n-button size="small" quaternary @click="openEdit(user)">编辑资料</n-button>
            <n-button size="small" quaternary @click="openReset(user)">重置密码</n-button>
          </div>
        </article>
      </div>
    </n-spin>

    <n-modal
      :show="Boolean(editing)"
      preset="card"
      title="编辑用户资料"
      style="width: 420px"
      @update:show="(v: boolean) => { if (!v) editing = null; }"
    >
      <div class="form">
        <label>名称</label>
        <n-input v-model:value="editName" placeholder="用户名称" />
        <label>邮箱</label>
        <n-input v-model:value="editEmail" placeholder="you@example.com" />
        <p class="hint">邮箱同时是登录账号，修改后对方需要用新邮箱登录。</p>
      </div>
      <template #footer>
        <div class="modal-acts">
          <n-button @click="editing = null">取消</n-button>
          <n-button type="primary" :loading="savingEdit" @click="saveEdit">保存</n-button>
        </div>
      </template>
    </n-modal>

    <n-modal
      :show="Boolean(resetting)"
      preset="card"
      :title="`重置「${resetting?.name || ''}」的密码`"
      style="width: 420px"
      @update:show="(v: boolean) => { if (!v) resetting = null; }"
    >
      <div class="form">
        <label>新密码</label>
        <n-input v-model:value="newPassword" type="password" show-password-on="click" placeholder="至少 8 位" />
        <p class="hint">系统没有邮件找回，重置后请把新密码直接告诉对方。</p>
      </div>
      <template #footer>
        <div class="modal-acts">
          <n-button @click="resetting = null">取消</n-button>
          <n-button type="primary" :loading="savingPassword" @click="savePassword">确认重置</n-button>
        </div>
      </template>
    </n-modal>
  </div>
</template>

<style scoped>
.head-acts {
  display: flex;
  gap: 8px;
  flex: none;
}
.list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.user-card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 16px 18px;
  box-shadow: var(--shadow-sm);
}
.user-card.off {
  background: #fbfbfc;
  border-style: dashed;
}
.head {
  display: flex;
  align-items: center;
  gap: 12px;
}
.avatar {
  width: 38px;
  height: 38px;
  border-radius: 11px;
  display: grid;
  place-items: center;
  font-weight: 700;
  font-size: 16px;
  background: #eff4ff;
  color: #1d4ed8;
  flex: none;
}
.avatar.muted {
  background: #f1f2f4;
  color: var(--faint);
}
.ident {
  flex: 1;
  min-width: 0;
}
.name-row {
  display: flex;
  align-items: center;
  gap: 7px;
  flex-wrap: wrap;
}
.name {
  font-size: 15px;
  font-weight: 650;
  color: var(--text-1);
}
.email {
  margin-top: 2px;
  font-size: 12.5px;
  color: var(--faint);
  word-break: break-all;
}
.switches {
  display: flex;
  gap: 16px;
  flex: none;
}
.sw {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  font-size: 11.5px;
  color: var(--faint);
}
.meta {
  margin-top: 12px;
  font-size: 12px;
  color: var(--faint);
  display: flex;
  align-items: center;
  gap: 6px;
}
.dot {
  opacity: 0.5;
}
.spaces {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.space-chip {
  font-size: 12px;
  color: var(--text-2);
  background: #f5f7fa;
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 3px 10px;
}
.space-chip em {
  font-style: normal;
  color: var(--faint);
  margin-left: 4px;
}
.acts {
  margin-top: 12px;
  display: flex;
  gap: 4px;
  margin-left: -6px;
}
.form {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.form label {
  font-size: 13px;
  color: var(--text-2);
  font-weight: 600;
}
.form label:not(:first-child) {
  margin-top: 6px;
}
.hint {
  margin: 2px 0 0;
  font-size: 12px;
  color: var(--faint);
  line-height: 1.6;
}
.modal-acts {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
