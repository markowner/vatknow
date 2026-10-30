export type User = {
  id: string;
  email: string;
  name: string;
  created_at: string;
  is_site_admin?: boolean;
};
export type Space = {
  id: string;
  name: string;
  kind: string;
  role: string;
  visibility: string;
  slug: string | null;
  created_at: string;
};
export type Member = { user_id: string; email: string; name: string; role: string };
export type Document = {
  id: string;
  space_id: string;
  title: string;
  source_type: string;
  slug?: string | null;
  parent_id?: string | null;
  is_folder?: boolean;
  published?: boolean;
  mime: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
  content_text?: string;
  content_md?: string | null;
  api_summary?: string | null;
  endpoint_count?: number | null;
  api_version?: string | null;
  api_server?: string | null;
};
export type SearchHit = {
  document_id: string;
  document_title: string;
  chunk_id: string;
  content: string;
  score: number;
  source_type?: string | null;
  /** 跨空间检索时标注来源空间，也决定点开后跳哪个空间。 */
  space_id?: string | null;
  space_name?: string | null;
};
export type Citation = {
  document_id: string;
  document_title: string;
  chunk_id: string;
  snippet: string;
};
export type SpaceStats = {
  document_count: number;
  member_count: number;
  chunk_count: number;
  by_source: Record<string, number>;
};
export type ShareLink = {
  id: string;
  token: string;
  document_id: string | null;
  has_password: boolean;
  expires_at: string | null;
  revoked: boolean;
  created_at: string;
  url: string;
  endpoint_keys: string[] | null;
};
export type AuditLog = {
  id: string;
  user_id: string | null;
  space_id: string | null;
  action: string;
  method: string;
  path: string;
  status_code: number;
  ip: string | null;
  created_at: string;
};

const TOKEN_KEY = "vatknow_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}
export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

function detailMessage(data: unknown, status: number): string {
  if (data && typeof data === "object" && "detail" in data) {
    const detail = (data as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((item) => (item && typeof item === "object" && "msg" in item ? String((item as { msg: string }).msg) : String(item)))
        .join("; ");
    }
  }
  return `请求失败 (${status})`;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const isForm = typeof FormData !== "undefined" && init.body instanceof FormData;
  if (!isForm && !headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json");
  }
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  let res: Response;
  try {
    res = await fetch(`/api/v1${path}`, { ...init, headers });
  } catch {
    throw new Error("无法连接后端，请确认 API 已在 http://127.0.0.1:8000 运行");
  }
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(detailMessage(data, res.status));
  return data as T;
}

export const AuthApi = {
  register: (email: string, password: string, name: string) =>
    api<{ user: User; access_token: string }>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, name }),
    }),
  login: (email: string, password: string) =>
    api<{ user: User; access_token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  me: () => api<User>("/auth/me"),
  updateMe: (name: string, email?: string) =>
    api<User>("/auth/me", { method: "PATCH", body: JSON.stringify({ name, email }) }),
  password: (old_password: string, new_password: string) =>
    api<{ detail: string }>("/auth/password", {
      method: "POST",
      body: JSON.stringify({ old_password, new_password }),
    }),
};

export const SpacesApi = {
  list: () => api<Space[]>("/spaces"),
  create: (name: string) => api<Space>("/spaces", { method: "POST", body: JSON.stringify({ name }) }),
  get: (id: string) => api<Space>(`/spaces/${id}`),
  update: (id: string, body: { name?: string; visibility?: string; slug?: string | null }) =>
    api<Space>(`/spaces/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  remove: (id: string) => api<void>(`/spaces/${id}`, { method: "DELETE" }),
  stats: (id: string) => api<SpaceStats>(`/spaces/${id}/stats`),
  members: (id: string) => api<Member[]>(`/spaces/${id}/members`),
  addMember: (id: string, email: string, role: string) =>
    api<Member>(`/spaces/${id}/members`, { method: "POST", body: JSON.stringify({ email, role }) }),
  updateMember: (id: string, userId: string, role: string) =>
    api<Member>(`/spaces/${id}/members/${userId}`, { method: "PATCH", body: JSON.stringify({ role }) }),
  removeMember: (id: string, userId: string) => api<void>(`/spaces/${id}/members/${userId}`, { method: "DELETE" }),
};

export const DocsApi = {
  list: (
    spaceId: string,
    params: { q?: string; source_type?: string; is_folder?: boolean; page?: number; page_size?: number } = {},
  ) => {
    const query = new URLSearchParams();
    if (params.q) query.set("q", params.q);
    if (params.source_type) query.set("source_type", params.source_type);
    if (params.is_folder !== undefined) query.set("is_folder", String(params.is_folder));
    query.set("page", String(params.page || 1));
    query.set("page_size", String(params.page_size || 20));
    return api<{ items: Document[]; total: number; page: number; page_size: number }>(
      `/spaces/${spaceId}/documents?${query.toString()}`,
    );
  },
  create: (spaceId: string, title: string, content_md: string) =>
    api<Document>(`/spaces/${spaceId}/documents`, { method: "POST", body: JSON.stringify({ title, content_md }) }),
  upload: (spaceId: string, file: File, title?: string) => {
    const form = new FormData();
    form.append("file", file);
    if (title) form.append("title", title);
    return api<Document>(`/spaces/${spaceId}/documents/upload`, { method: "POST", body: form });
  },
  paste: (spaceId: string, title: string, html?: string, text?: string) =>
    api<Document>(`/spaces/${spaceId}/documents/paste`, { method: "POST", body: JSON.stringify({ title, html, text }) }),
  fromUrl: (spaceId: string, url: string, title?: string) =>
    api<Document>(`/spaces/${spaceId}/documents/from-url`, { method: "POST", body: JSON.stringify({ url, title }) }),
  openapi: (spaceId: string, spec: string, title?: string, slug?: string) =>
    api<Document>(`/spaces/${spaceId}/documents/openapi`, {
      method: "POST",
      body: JSON.stringify({ spec, title, slug, published: true }),
    }),
  get: (id: string) => api<Document>(`/documents/${id}`),
  update: (
    id: string,
    body: {
      title?: string;
      content_md?: string;
      slug?: string | null;
      published?: boolean;
      parent_id?: string | null;
      move_parent?: boolean;
      is_folder?: boolean;
    },
  ) => api<Document>(`/documents/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  remove: (id: string) => api<void>(`/documents/${id}`, { method: "DELETE" }),
  createFolder: (spaceId: string, title: string, parentId?: string | null) =>
    api<Document>(`/spaces/${spaceId}/documents/folders`, {
      method: "POST",
      body: JSON.stringify({ title, parent_id: parentId || null }),
    }),
};

export type DocSearchHit = {
  id: string;
  title: string;
  source_type: string;
  snippet: string;
  in_body: boolean;
};

export const DocSearchApi = {
  query: (spaceId: string, q: string) =>
    api<{ items: DocSearchHit[]; total: number }>(
      `/spaces/${spaceId}/docs-search?q=${encodeURIComponent(q)}&limit=20`,
    ),
};

export const SharesApi = {
  list: (spaceId: string) => api<ShareLink[]>(`/spaces/${spaceId}/shares`),
  create: (
    spaceId: string,
    body: { document_id?: string; password?: string; expires_days?: number; endpoint_keys?: string[] | null },
  ) => api<ShareLink>(`/spaces/${spaceId}/shares`, { method: "POST", body: JSON.stringify(body) }),
  update: (
    spaceId: string,
    shareId: string,
    body: {
      password?: string;
      clear_password?: boolean;
      expires_days?: number;
      clear_expiry?: boolean;
      endpoint_keys?: string[] | null;
      clear_endpoint_keys?: boolean;
    },
  ) => api<ShareLink>(`/spaces/${spaceId}/shares/${shareId}`, { method: "PATCH", body: JSON.stringify(body) }),
  endpoints: (spaceId: string, shareId: string) =>
    api<{ items: string[]; selected: string[] }>(`/spaces/${spaceId}/shares/${shareId}/endpoints`),
  revoke: (spaceId: string, shareId: string) => api<void>(`/spaces/${spaceId}/shares/${shareId}`, { method: "DELETE" }),
  /** 找到某个文档已有的有效公开链接，避免每次点都生成新链接。 */
  forDocument: async (spaceId: string, documentId: string) => {
    const rows = await SharesApi.list(spaceId);
    return rows.find((item) => item.document_id === documentId) || null;
  },
};

export const LogsApi = {
  list: (spaceId: string, page = 1, page_size = 20) =>
    api<{ items: AuditLog[]; total: number; page: number; page_size: number }>(
      `/spaces/${spaceId}/logs?page=${page}&page_size=${page_size}`,
    ),
};

export type SiteBrand = {
  site_name: string;
  site_tagline: string;
  has_logo: boolean;
  logo_version: number;
  is_site_admin: boolean;
};

export type AdminUserSpace = { id: string; name: string; kind: string; role: string };

export type AdminUser = {
  id: string;
  email: string;
  name: string;
  created_at: string;
  is_site_admin: boolean;
  is_active: boolean;
  space_count: number;
  spaces: AdminUserSpace[];
};

/** 站点级用户管理，只有站点管理员能用。 */
export const UsersApi = {
  list: () => api<AdminUser[]>("/users"),
  update: (
    userId: string,
    body: { name?: string; email?: string; is_site_admin?: boolean; is_active?: boolean },
  ) => api<AdminUser>(`/users/${userId}`, { method: "PATCH", body: JSON.stringify(body) }),
  resetPassword: (userId: string, new_password: string) =>
    api<{ detail: string }>(`/users/${userId}/password`, {
      method: "POST",
      body: JSON.stringify({ new_password }),
    }),
};

export const SiteApi = {
  /** 公开读，登录页没有 token 时也能拿到站名和 Logo。 */
  brand: () => api<SiteBrand>("/site/brand"),
  /** 登录后读，额外带回「我能不能改」。 */
  brandMine: () => api<SiteBrand>("/site/brand/me"),
  update: (body: { site_name?: string; site_tagline?: string }) =>
    api<SiteBrand>("/site/brand", { method: "PATCH", body: JSON.stringify(body) }),
  /** 带版本号，换图后浏览器不会继续用旧的缓存。 */
  logoUrl: (version: number) => `/api/v1/site/logo?v=${version}`,
  uploadLogo: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api<SiteBrand>("/site/logo", { method: "POST", body: form });
  },
  removeLogo: () => api<SiteBrand>("/site/logo", { method: "DELETE" }),
};

export type LLMSettings = {
  base_url: string;
  model: string;
  api_key_hint: string;
  has_api_key: boolean;
  api_key_source: "settings" | "env" | "none";
  embedding_model: string;
  embedding_dim: number;
};

export const LLMApi = {
  get: () => api<LLMSettings>("/site/llm"),
  update: (body: {
    base_url?: string;
    model?: string;
    api_key?: string;
    clear_api_key?: boolean;
  }) => api<LLMSettings>("/site/llm", { method: "PATCH", body: JSON.stringify(body) }),
  /** 真发一条请求验证配置，比"保存成功"更能说明问题。 */
  test: () => api<{ model: string; reply: string }>("/site/llm/test", { method: "POST" }),
};

export const PublicApi = {
  space: (slug: string) => fetch(`/api/v1/public/spaces/${slug}`).then(async (res) => {
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "公开空间不存在");
    return data as { name: string; slug: string; document_count: number };
  }),
  posts: (slug: string) => fetch(`/api/v1/public/spaces/${slug}/posts`).then(async (res) => {
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "加载失败");
    return data as { items: Array<{ id: string; slug: string | null; title: string; source_type: string; excerpt: string; updated_at: string }>; total: number };
  }),
  post: (slug: string, key: string) => fetch(`/api/v1/public/spaces/${slug}/posts/${key}`).then(async (res) => {
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "文章不存在");
    return data as { id: string; slug: string | null; title: string; source_type: string; content_md: string | null; content_text: string };
  }),
  shareMeta: (token: string) =>
    fetch(`/api/v1/public/shares/${token}/meta`).then(async (res) => {
      const data = await res.json();
      if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "分享无效");
      return data as { title: string; source_type: string | null; need_password: boolean; expires_at: string | null };
    }),
  share: (token: string, password?: string) => {
    const q = password ? `?password=${encodeURIComponent(password)}` : "";
    return fetch(`/api/v1/public/shares/${token}${q}`).then(async (res) => {
      const data = await res.json();
      if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "分享无效");
      return data as {
        kind: string;
        space_name: string;
        title: string;
        source_type?: string;
        content_md?: string | null;
        content_text?: string;
        items?: Array<{ id: string; title: string; source_type: string; slug: string | null }>;
      };
    });
  },
};

export const ApiProxy = {
  send: (
    spaceId: string,
    body: { document_id: string; method: string; url: string; headers: Record<string, string>; body?: string | null },
  ) =>
    api<{ status_code: number; elapsed_ms: number; headers: Record<string, string>; body: string; error: string | null }>(
      `/spaces/${spaceId}/api-proxy`,
      { method: "POST", body: JSON.stringify(body) },
    ),
};

export type SearchLog = {
  id: string;
  user_id: string | null;
  user_name: string | null;
  query: string;
  hit_count: number;
  hits: HistoryDocRef[];
  created_at: string;
};
export type ChatLog = {
  id: string;
  user_id: string | null;
  user_name: string | null;
  question: string;
  answer: string;
  citations: HistoryDocRef[];
  created_at: string;
};
export type HistoryDocRef = { document_id: string; document_title: string };
export type HistoryPage<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  scope: "self" | "space";
};

export const SearchApi = {
  query: (spaceId: string, q: string) =>
    api<{ items: SearchHit[] }>(`/spaces/${spaceId}/search?q=${encodeURIComponent(q)}&limit=20`),
  /** 在「全部空间」里跨库检索，后端只返回当前用户可见的空间。 */
  queryAll: (q: string) =>
    api<{ items: SearchHit[] }>(`/search?q=${encodeURIComponent(q)}&limit=30`),
  logs: (spaceId: string, page = 1, page_size = 20, scope: "self" | "space" = "self") =>
    api<HistoryPage<SearchLog>>(
      `/spaces/${spaceId}/search-logs?page=${page}&page_size=${page_size}&scope=${scope}`,
    ),
  /** 跨库检索的历史，只有自己的。 */
  globalLogs: (page = 1, page_size = 20) =>
    api<HistoryPage<SearchLog>>(`/search-logs?page=${page}&page_size=${page_size}`),
};

export const ChatApi = {
  ask: (spaceId: string, question: string, history: { role: string; content: string }[]) =>
    api<{ answer: string; citations: Citation[] }>(`/spaces/${spaceId}/chat`, {
      method: "POST",
      body: JSON.stringify({ question, history }),
    }),
  logs: (spaceId: string, page = 1, page_size = 20, scope: "self" | "space" = "self") =>
    api<HistoryPage<ChatLog>>(
      `/spaces/${spaceId}/chat-logs?page=${page}&page_size=${page_size}&scope=${scope}`,
    ),
};
