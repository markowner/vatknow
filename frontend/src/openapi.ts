export type OpenParam = {
  name: string;
  in: string;
  required?: boolean;
  description?: string;
  schema?: { type?: string; example?: unknown; default?: unknown };
};

export type OpenOp = {
  method: string;
  path: string;
  summary: string;
  description: string;
  notes: string;
  status: "undone" | "done";
  tags: string[];
  parameters: OpenParam[];
  body?: { contentType: string; example: string; required: boolean; description: string };
  responses: { status: string; description: string; example?: string }[];
};

/** 环境：一套 Base URL 对应开发 / 测试 / 生产等。 */
export type OpenEnv = { name: string; url: string };

export type OpenSpec = {
  title: string;
  version: string;
  description: string;
  notes: string;
  servers: string[];
  categories: string[];
  ops: OpenOp[];
  /** 环境列表，第一项作为默认环境；与 servers 保持同源。 */
  environments: OpenEnv[];
  /** 全局公共参数：所有接口都会带上的 query / header，例如签名、租户标识。 */
  commonParams: OpenParam[];
};

const METHODS = ["get", "post", "put", "patch", "delete", "head", "options"];

function exampleFromSchema(schema: Record<string, unknown> | undefined): unknown {
  if (!schema) return {};
  if (schema.example !== undefined) return schema.example;
  if (schema.default !== undefined) return schema.default;
  if (schema.type === "array") return [exampleFromSchema(schema.items as Record<string, unknown>)];
  if (schema.type === "string") return "";
  if (schema.type === "integer" || schema.type === "number") return 0;
  if (schema.type === "boolean") return false;
  if (schema.type === "object" || schema.properties) {
    const out: Record<string, unknown> = {};
    const props = (schema.properties || {}) as Record<string, Record<string, unknown>>;
    for (const [key, value] of Object.entries(props)) out[key] = exampleFromSchema(value);
    return out;
  }
  return {};
}

function stringifyExample(value: unknown): string {
  if (value === undefined || value === null) return "";
  return typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

export function emptySpec(): OpenSpec {
  return {
    title: "未命名 API",
    version: "1.0.0",
    description: "",
    notes: "",
    servers: ["https://api.example.com"],
    categories: ["公共分类"],
    ops: [],
    environments: [{ name: "开发", url: "https://api.example.com" }],
    commonParams: [],
  };
}

/** 老文档没有环境列表时，用 Base URL 的主机名兜底命名。 */
export function envNameFromUrl(url: string): string {
  try {
    return new URL(url).host || url;
  } catch {
    return url;
  }
}

/**
 * 合并接口自身参数与全局公共参数。
 * 同名同位置时以接口自己的定义为准，避免公共参数盖掉具体接口的说明。
 */
export function mergeCommonParams(params: OpenParam[], common: OpenParam[] = []): OpenParam[] {
  const seen = new Set(params.map((item) => `${item.in}:${item.name}`));
  return [...params, ...common.filter((item) => item.name && !seen.has(`${item.in}:${item.name}`))];
}

export function emptyOp(tag = "公共分类"): OpenOp {
  return {
    method: "GET",
    path: "/demo",
    summary: "未命名接口",
    description: "",
    notes: "",
    status: "undone",
    tags: [tag],
    parameters: [],
    responses: [{ status: "200", description: "成功", example: "" }],
  };
}

export function emptyCommonParam(): OpenParam {
  return { name: "", in: "header", required: false, description: "", schema: { type: "string", example: "" } };
}

export function parseOpenApi(raw: string): OpenSpec | null {
  let data: Record<string, unknown>;
  try {
    data = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!data || typeof data !== "object") return null;
  const info = (data.info || {}) as { title?: string; version?: string; description?: string; "x-notes"?: string };
  const servers: string[] = [];
  for (const item of (data.servers as { url?: string }[]) || []) {
    if (item?.url) servers.push(item.url.replace(/\/$/, ""));
  }
  if (typeof data.host === "string") {
    const scheme = ((data.schemes as string[]) || ["https"])[0];
    servers.push(`${scheme}://${data.host}${typeof data.basePath === "string" ? data.basePath : ""}`.replace(/\/$/, ""));
  }
  if (!servers.length) servers.push("https://api.example.com");

  const ops: OpenOp[] = [];
  const paths = (data.paths || {}) as Record<string, Record<string, Record<string, unknown>>>;
  for (const [path, methods] of Object.entries(paths)) {
    if (!methods || typeof methods !== "object") continue;
    for (const method of METHODS) {
      const op = methods[method];
      if (!op) continue;
      const parameters = (
        (op.parameters as OpenParam[] | undefined) ||
        (methods.parameters as unknown as OpenParam[] | undefined) ||
        []
      ).map((item) => ({
        name: item.name,
        in: item.in,
        required: Boolean(item.required) || item.in === "path",
        description: item.description,
        schema: item.schema,
      }));
      let body: OpenOp["body"];
      const requestBody = op.requestBody as
        | {
            required?: boolean;
            description?: string;
            content?: Record<string, { schema?: Record<string, unknown>; example?: unknown }>;
          }
        | undefined;
      if (requestBody?.content) {
        const contentType = Object.keys(requestBody.content)[0] || "application/json";
        const media = requestBody.content[contentType] || {};
        const example = media.example !== undefined ? media.example : exampleFromSchema(media.schema);
        body = {
          contentType,
          required: Boolean(requestBody.required),
          description: requestBody.description || "",
          example: stringifyExample(example),
        };
      }
      const responses = Object.entries((op.responses || {}) as Record<string, { description?: string; content?: Record<string, { example?: unknown }> }>).map(
        ([status, item]) => {
          const media = item?.content ? Object.values(item.content)[0] : undefined;
          return {
            status,
            description: item?.description || "",
            example: stringifyExample(media?.example),
          };
        },
      );
      ops.push({
        method: method.toUpperCase(),
        path,
        summary: String(op.summary || op.operationId || path),
        description: String(op.description || ""),
        notes: String(op["x-notes"] || ""),
        status: op["x-status"] === "done" ? "done" : "undone",
        tags: (op.tags as string[]) || ["公共分类"],
        parameters,
        body,
        responses,
      });
    }
  }
  const categories = ((data["x-categories"] as string[]) || []).filter(Boolean);
  for (const op of ops) {
    for (const tag of op.tags) {
      if (tag && !categories.includes(tag)) categories.push(tag);
    }
  }
  if (!categories.length) categories.push("公共分类");

  // 环境：优先读 x-environments，老文档则按 servers 逐条补出名称。
  const rawEnvs = (data["x-environments"] as OpenEnv[] | undefined) || [];
  const environments: OpenEnv[] = rawEnvs
    .filter((item) => item && typeof item.url === "string")
    .map((item) => ({ name: String(item.name || "").trim() || envNameFromUrl(item.url), url: item.url }));
  if (!environments.length) {
    environments.push(...servers.map((url) => ({ name: envNameFromUrl(url), url })));
  }

  const commonParams = ((data["x-common-parameters"] as OpenParam[] | undefined) || [])
    .filter((item) => item && item.name)
    .map((item) => ({
      name: item.name,
      in: item.in || "header",
      required: Boolean(item.required) || item.in === "path",
      description: item.description,
      schema: item.schema,
    }));

  return {
    title: info.title || "API 文档",
    version: info.version || "1.0.0",
    description: info.description || "",
    notes: info["x-notes"] || String(data["x-notes"] || ""),
    servers: Array.from(new Set(servers)),
    categories,
    ops,
    environments,
    commonParams,
  };
}

export function serializeOpenApi(spec: OpenSpec): string {
  const paths: Record<string, Record<string, unknown>> = {};
  for (const op of spec.ops) {
    const path = op.path.startsWith("/") ? op.path : `/${op.path}`;
    if (!paths[path]) paths[path] = {};
    const parameters = op.parameters
      .filter((item) => item.name.trim())
      .map((item) => ({
        name: item.name.trim(),
        in: item.in || "query",
        required: Boolean(item.required) || item.in === "path",
        description: item.description || "",
        schema: { type: item.schema?.type || "string", example: item.schema?.example },
      }));
    const operation: Record<string, unknown> = {
      summary: op.summary || path,
      description: op.description || "",
      "x-notes": op.notes || "",
      "x-status": op.status || "undone",
      tags: op.tags.filter(Boolean).length ? op.tags : ["公共分类"],
      parameters,
      responses: Object.fromEntries(
        (op.responses.length ? op.responses : [{ status: "200", description: "成功" }]).map((item) => [
          item.status || "200",
          {
            description: item.description || "",
            ...(item.example
              ? { content: { "application/json": { example: tryParse(item.example) } } }
              : {}),
          },
        ]),
      ),
    };
    if (op.body) {
      operation.requestBody = {
        required: op.body.required,
        description: op.body.description || "",
        content: {
          [op.body.contentType || "application/json"]: {
            example: tryParse(op.body.example),
          },
        },
      };
    }
    paths[path][op.method.toLowerCase()] = operation;
  }
  // 环境列表为准，servers 由它派生，保证两者不会各说各话。
  const environments = (spec.environments || [])
    .filter((item) => item.url.trim())
    .map((item) => ({ name: item.name.trim() || envNameFromUrl(item.url), url: item.url.trim() }));
  const servers = environments.length
    ? environments.map((item) => item.url)
    : spec.servers.length
      ? spec.servers
      : ["https://api.example.com"];

  const commonParams = (spec.commonParams || [])
    .filter((item) => item.name.trim())
    .map((item) => ({
      name: item.name.trim(),
      in: item.in || "header",
      required: Boolean(item.required) || item.in === "path",
      description: item.description || "",
      schema: { type: item.schema?.type || "string", example: item.schema?.example },
    }));

  return JSON.stringify(
    {
      openapi: "3.0.3",
      info: {
        title: spec.title || "API 文档",
        version: spec.version || "1.0.0",
        description: spec.description || "",
        "x-notes": spec.notes || "",
      },
      servers: servers.map((url) => ({ url })),
      ...(environments.length ? { "x-environments": environments } : {}),
      ...(commonParams.length ? { "x-common-parameters": commonParams } : {}),
      "x-categories": spec.categories.length ? spec.categories : ["公共分类"],
      paths,
    },
    null,
    2,
  );
}

function tryParse(text: string): unknown {
  const raw = (text || "").trim();
  if (!raw) return {};
  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
}

export function methodColor(method: string) {
  return methodStyle(method).bg;
}

export function methodStyle(method: string) {
  const map: Record<string, { bg: string }> = {
    GET: { bg: "#3b82f6" },
    POST: { bg: "#10b981" },
    PUT: { bg: "#f59e0b" },
    PATCH: { bg: "#8b5cf6" },
    DELETE: { bg: "#ef4444" },
    HEAD: { bg: "#57534e" },
    OPTIONS: { bg: "#57534e" },
  };
  return map[method] || { bg: "#57534e" };
}

export function buildUrl(server: string, path: string, params: OpenParam[], values: Record<string, string>) {
  let url = `${server.replace(/\/$/, "")}${path.startsWith("/") ? path : `/${path}`}`;
  const query: string[] = [];
  for (const param of params) {
    const value = values[`${param.in}:${param.name}`] ?? "";
    if (param.in === "path") url = url.replace(`{${param.name}}`, encodeURIComponent(value));
    if (param.in === "query" && value) query.push(`${encodeURIComponent(param.name)}=${encodeURIComponent(value)}`);
  }
  if (query.length) url += (url.includes("?") ? "&" : "?") + query.join("&");
  return url;
}
