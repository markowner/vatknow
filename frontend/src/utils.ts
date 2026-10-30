export const roleLabel: Record<string, string> = {
  owner: "所有者",
  admin: "管理员",
  editor: "编辑",
  viewer: "只读",
};

export const sourceLabel: Record<string, string> = {
  markdown: "Markdown",
  pdf: "PDF",
  web: "网页",
  openapi: "API 文档",
};

export function canEdit(role?: string) {
  return role === "owner" || role === "admin" || role === "editor";
}

export function canAdmin(role?: string) {
  return role === "owner" || role === "admin";
}

export function documentPath(spaceId: string, doc: { id: string; source_type: string }) {
  return doc.source_type === "openapi"
    ? `/spaces/${spaceId}/apis/${doc.id}`
    : `/spaces/${spaceId}/docs/${doc.id}`;
}

export function formatTime(value?: string) {
  if (!value) return "-";
  return new Date(value).toLocaleString();
}

export function renderMarkdown(md: string, options: { stripTitle?: string } = {}): string {
  const escaped = (md || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  const withCode = escaped.replace(
    /```([a-zA-Z0-9+-]*)\n?([\s\S]*?)```/g,
    (_m: string, lang: string, code: string) => {
      const body = code.replace(/\s+$/, "");
      const label = lang ? `<span class="code-lang">${lang}</span>` : "";
      return `<pre>${label}<code>${body}</code></pre>`;
    },
  );
  const lines = withCode.split("\n");
  const out: string[] = [];
  let inList = false;
  let titleSkipped = false;
  const wantTitle = options.stripTitle?.trim();

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    const heading = /^(#{1,4})\s+(.*)$/.exec(line);
    if (heading) {
      if (inList) {
        out.push("</ul>");
        inList = false;
      }
      if (!titleSkipped && wantTitle && heading[1].length === 1 && heading[2].trim() === wantTitle) {
        titleSkipped = true;
        continue;
      }
      titleSkipped = true;
      const level = Math.min(heading[1].length + 1, 4);
      out.push(`<h${level}>${inline(heading[2])}</h${level}>`);
      continue;
    }

    // table block: header row followed by a divider row
    if (/\|/.test(line) && /^\s*\|?[\s:|-]+\|[\s:|-]*$/.test(lines[i + 1] || "")) {
      if (inList) {
        out.push("</ul>");
        inList = false;
      }
      const header = cells(line);
      const rows: string[][] = [];
      i += 2;
      while (i < lines.length && /\|/.test(lines[i]) && lines[i].trim()) {
        rows.push(cells(lines[i]));
        i += 1;
      }
      i -= 1;
      const head = header.map((cell) => `<th>${inline(cell)}</th>`).join("");
      const body = rows
        .map((row) => `<tr>${row.map((cell) => `<td>${inline(cell)}</td>`).join("")}</tr>`)
        .join("");
      out.push(`<div class="table-wrap"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`);
      continue;
    }

    if (/^\s*[-*]\s+/.test(line)) {
      if (!inList) {
        out.push("<ul>");
        inList = true;
      }
      out.push(`<li>${inline(line.replace(/^\s*[-*]\s+/, ""))}</li>`);
      continue;
    }
    if (inList) {
      out.push("</ul>");
      inList = false;
    }
    if (!line.trim()) continue;
    if (line.startsWith("<pre>")) {
      out.push(line);
      continue;
    }
    out.push(`<p>${inline(line)}</p>`);
  }
  if (inList) out.push("</ul>");
  return out.join("\n");
}

function cells(row: string): string[] {
  return row
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

function inline(text: string): string {
  return text
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(
      /\[([^\]]+)\]\((https?:[^)]+)\)/g,
      '<a href="$2" target="_blank" rel="noreferrer">$1</a>',
    );
}
