# VatKnow

个人与团队知识库平台。收录 Markdown、PDF、网页摘录与 OpenAPI 规范文档，支持关键词 + 向量混合检索，基于 OpenAI 兼容接口提供带引用的 RAG 智能问答。

---

## 核心功能

### 知识管理
- **多类型文档收录**：Markdown 编写、PDF 上传、网页粘贴、OpenAPI 规范导入
- **目录树组织**：支持文件夹层级结构，文档可拖拽归档
- **文档层级管理**：发布/草稿状态控制，slug 自定义 URL

### 空间与协作
- **个人空间**：注册后自动创建，仅本人可见
- **团队空间**：支持邀请成员，四级角色体系（Owner / Admin / Editor / Viewer）
- **公开空间**：设置 slug 后对外发布，无需登录即可访问内容（`/p/:slug`）

### 检索与问答
- **混合检索**：PostgreSQL 全文检索（ILIKE + tsvector）+ pgvector 语义向量检索，通过 RRF 算法融合排序
- **智能问答（RAG）**：基于检索结果调用 LLM 生成答案，自动标注引用来源
- **跨空间检索**：在全局搜索页可同时查询多个空间
- **检索/问答历史**：按空间和用户隔离，管理员可查阅全空间记录

### API Studio
- **OpenAPI 文档管理**：在线创建、编辑、预览 API 文档
- **接口调试**：内置 API Playground，支持多环境配置、在线发送请求
- **参数编辑**：可视化编辑 Path / Query / Body 参数，支持公共参数复用
- **外链分享**：生成带密码和有效期的分享链接，可精确控制暴露哪些接口

### 分享与外链
- **文档/空间分享**：生成随机 token 链接，支持密码保护和过期时间
- **API 接口白名单**：分享 OpenAPI 文档时可选择只暴露部分接口
- **公开页面**：`/s/:token` 访问分享内容，`/p/:slug` 访问公开空间

### 站点管理
- **品牌定制**：管理员可修改站点名称、副标题、Logo
- **LLM 配置**：支持在设置页覆盖 .env 中的模型配置（对话模型，向量模型固定）
- **用户管理**：停用/启用账号，控制登录权限
- **审计日志**：记录所有 API 请求，支持按用户和空间筛选

---

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python · FastAPI · SQLAlchemy · PyJWT · bcrypt |
| 数据库 | PostgreSQL 16 + pgvector 扩展 |
| 向量检索 | pgvector（余弦相似度）+ RRF 混合排序 |
| LLM | OpenAI 兼容接口（可配置 base_url / model） |
| 前端 | Vue 3 · TypeScript · Vite · Naive UI · Pinia |
| 部署 | Docker Compose 或裸机部署（nginx + systemd） |

---

## 快速开始

### Docker Compose（最简单）

```bash
cp .env.example .env
# 编辑 .env，至少填写 JWT_SECRET；如需智能问答再填写 OPENAI_API_KEY
docker compose up --build -d
```

- 界面：[http://localhost:3000](http://localhost:3000)
- API 文档：[http://localhost:8000/docs](http://localhost:8000/docs)

**默认管理员账号**（首次启动自动创建，仅数据库为空时生效）：

| 邮箱 | 密码 |
|---|---|
| `admin@vat.com` | `vat123456` |

> 登录后请立即修改默认密码。若已有任何注册用户，则不会重复创建默认账号。

### 本地开发

脚本会自动检测 Docker，有则用容器启动，无则走本地环境。

**macOS / Linux：**

```bash
./start.sh            # 自动检测，优先 Docker
./start.sh --local    # 强制本地启动（不用 Docker）
./start.sh --docker   # 强制 Docker（没装会报错）
./start.sh --help     # 查看帮助
```

**Windows：**

双击 `start.bat`，或在 PowerShell 中执行：

```powershell
.\start.ps1            # 自动检测，优先 Docker
.\start.ps1 -Local     # 强制本地启动
.\start.ps1 -Docker    # 强制 Docker
.\start.ps1 -Help      # 查看帮助
```

> Windows 本地模式需预装 [PostgreSQL 16+](https://www.postgresql.org/download/windows/) 和 [Node.js 20+](https://nodejs.org/)，并确保 `psql` 和 `npm` 在 PATH 中。

> 未配置 `OPENAI_API_KEY` 时，文档管理与关键词检索仍可用，智能问答与向量检索会提示缺少配置。

---

## 开发调试

### 后端调试（Python / FastAPI）

**启动调试模式：**

```bash
cd backend
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 先在 .env 中开启文档接口（否则 /docs 返回 404）
# ENABLE_DOCS=true

# 方式 1：直接启动（带热重载）
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# 方式 2：使用 Python 调试器
python -m debugpy --listen 5678 --wait-for-client -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**VS Code 调试配置**（`.vscode/launch.json`）：

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "FastAPI Debug",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["app.main:app", "--reload", "--host", "127.0.0.1", "--port", "8000"],
      "env": {"DATABASE_URL": "postgresql+psycopg://vatknow:vatknow@localhost:5432/vatknow"},
      "cwd": "${workspaceFolder}/backend"
    }
  ]
}
```

**查看 API 文档：**

启动后访问 [http://localhost:8000/docs](http://localhost:8000/docs) 查看 Swagger UI，可直接测试所有接口。

**日志位置：**

- 本地模式：`.run/api.log`（标准输出）和 `.run/api.err.log`（错误）
- Docker 模式：`docker compose logs -f api`

### 前端调试（Vue 3 / Vite）

**启动开发服务器（带热重载）：**

```bash
cd frontend
npm run dev
```

Vite 默认启用热模块替换（HMR），修改代码后浏览器自动刷新。

**Vue DevTools：**

安装浏览器扩展 [Vue DevTools](https://devtools.vuejs.org/)，可检查组件状态、Pinia Store、路由等。

**VS Code 调试配置**（`.vscode/launch.json`）：

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Vue Chrome Debug",
      "type": "chrome",
      "request": "launch",
      "url": "http://localhost:3000",
      "webRoot": "${workspaceFolder}/frontend/src"
    }
  ]
}
```

**日志位置：**

- 本地模式：`.run/web.log`
- Docker 模式：`docker compose logs -f web`
- 浏览器控制台：F12 打开 DevTools

### 数据库调试

**连接数据库：**

```bash
# 本地模式
psql -U vatknow -d vatknow -h localhost

# Docker 模式
docker exec -it vatknow-db-1 psql -U vatknow -d vatknow
```

**常用查询：**

```sql
-- 查看所有用户
SELECT id, email, name, is_site_admin FROM users;

-- 查看所有空间
SELECT id, name, kind, visibility FROM spaces;

-- 查看文档数量
SELECT space_id, COUNT(*) FROM documents GROUP BY space_id;

-- 查看检索日志
SELECT * FROM search_logs ORDER BY created_at DESC LIMIT 10;
```

**重置数据库（清空所有数据）：**

```bash
# 本地模式
psql -U vatknow -d postgres -c "DROP DATABASE vatknow;"
psql -U vatknow -d postgres -c "CREATE DATABASE vatknow OWNER vatknow;"

# Docker 模式
docker compose down -v  # ⚠️ 会删除所有数据卷
docker compose up -d db
```

### Docker 调试

**查看容器状态：**

```bash
docker compose ps
```

**进入容器内部：**

```bash
# 进入后端容器
docker compose exec api bash

# 进入数据库容器
docker compose exec db psql -U vatknow -d vatknow
```

**查看实时日志：**

```bash
docker compose logs -f          # 所有服务
docker compose logs -f api      # 仅后端
docker compose logs -f web      # 仅前端
docker compose logs -f db       # 仅数据库
```

**重启单个服务：**

```bash
docker compose restart api      # 重启后端
docker compose restart web      # 重启前端
```

### 常见问题排查

**Q：API 返回 500 错误**

1. 查看后端日志：`.run/api.err.log` 或 `docker compose logs api`
2. 检查数据库连接：`psql -U vatknow -d vatknow` 能否正常连接
3. 检查 `.env` 配置：`JWT_SECRET` 是否设置，`DATABASE_URL` 是否正确

**Q：前端无法连接后端**

1. 确认后端已启动：`curl http://localhost:8000/api/v1/health`
2. 检查 CORS 配置：`.env` 中 `CORS_ORIGINS` 是否包含 `http://localhost:3000`
3. 前端代理配置：`frontend/vite.config.ts` 中 `/api` 代理是否指向 `http://127.0.0.1:8000`

**Q：数据库连接失败**

1. 检查 PostgreSQL 是否运行：`pg_isready`
2. 本地模式：确认 `start.sh` 已正确创建用户和数据库
3. Docker 模式：确认 `db` 容器健康：`docker compose ps`
4. 检查连接串：`DATABASE_URL` 格式是否正确

**Q：向量检索不可用**

1. 检查 `OPENAI_API_KEY` 是否在 `.env` 中配置
2. 查看后端日志是否有 API 调用错误
3. 确认 embedding 模型名称正确（默认 `text-embedding-3-small`）

**Q：热重载不生效**

1. 后端：确认使用 `--reload` 参数启动
2. 前端：检查文件是否保存在 `src/` 目录下
3. Docker 模式：需要重新构建镜像 `docker compose up --build`

---

## 线上部署

### 服务器要求

| 资源 | 最低配置 | 推荐配置 |
|---|---|---|
| CPU | 1 核 | 2 核以上 |
| 内存 | 1 GB | 2 GB 以上（向量检索消耗较多内存） |
| 磁盘 | 10 GB | 50 GB SSD（文档和向量数据增长较快） |
| 系统 | Docker 或 Linux（Ubuntu 22.04+） | 同左 |

### 服务器初始化

```bash
# 1. 克隆仓库
git clone https://github.com/your-org/vatknow.git
cd vatknow

# 2. 配置环境变量
cp .env.example .env
nano .env   # 务必修改 JWT_SECRET，填写 OPENAI_API_KEY

# 3. Docker 方式启动
docker compose up --build -d

# 或裸机方式，见下方「不使用 Docker 的裸机部署」章节
```

启动完成后访问 `http://your-server:3000`，使用默认账号 `admin@vat.com` / `vat123456` 登录并立即修改密码。

### 安全建议

上线前请确认以下几点：

1. **JWT_SECRET 使用随机字符串**，可用以下命令生成：
   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
2. **修改默认管理员账号密码**（`admin@vat.com` / `vat123456`）
3. **配置 HTTPS**，避免账号密码在网络上明文传输
4. **防火墙只开放 80 / 443 端口**，5432（数据库）和 8000（API）不应对外暴露
5. **定期备份数据库**，见下方「数据备份」章节

### 绑定域名与 HTTPS（推荐）

生产环境建议用 nginx 或 Caddy 做反向代理，统一处理域名和 TLS 证书。

**Caddy（最简单）**

```bash
# 安装 Caddy 后，创建 /etc/caddy/Caddyfile
your-domain.com {
    reverse_proxy localhost:3000
}
```

Caddy 会自动申请 Let's Encrypt 证书并续期。

**nginx + certbot**

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 50m;
    }
}
```

```bash
sudo certbot --nginx -d your-domain.com
```

### 数据备份

**Docker 部署**：数据库文件存储在 Docker 卷 `vatknow_pg` 中，定期备份该卷即可。

```bash
# 手动备份（导出 SQL）
docker exec vatknow-db-1 pg_dump -U vatknow vatknow > backup_$(date +%Y%m%d).sql

# 恢复
cat backup_20261030.sql | docker exec -i vatknow-db-1 psql -U vatknow vatknow

# 定时备份（加入 crontab，每天凌晨 3 点执行）
0 3 * * * cd /path/to/vatknow && docker exec vatknow-db-1 pg_dump -U vatknow vatknow > /backups/vatknow_$(date +\%Y\%m\%d).sql
```

**裸机部署**：直接用 `pg_dump` 备份本地数据库。

```bash
# 手动备份
pg_dump -U vatknow vatknow > /backups/vatknow_$(date +%Y%m%d).sql

# 恢复
psql -U vatknow vatknow < /backups/vatknow_20261030.sql

# 定时备份
0 3 * * * pg_dump -U vatknow vatknow > /backups/vatknow_$(date +\%Y\%m\%d).sql
```

### 更新版本

```bash
git pull origin main
docker compose up --build -d
# 数据库迁移在 API 启动时自动执行，无需手动操作
```

### 常见问题

**Q：端口 3000 / 8000 已被占用怎么办？**

修改 `docker-compose.yml` 中的端口映射，例如改为 `8080:3000` 和 `8081:8000`，同时更新 `.env` 中的 `CORS_ORIGINS`。

**Q：如何更换 LLM 模型？**

登录后进入「空间设置 → LLM 配置」，填写新的 API Key 和模型名即可覆盖 `.env` 中的默认值，无需重启服务。

**Q：忘记管理员密码怎么办？**

清空数据库卷后重新启动即可重置：

```bash
docker compose down -v   # ⚠️ 会删除所有数据
docker compose up --build -d
# 默认账号 admin@vat.com / vat123456 会重新创建
```

如果有其他可用账号，也可以通过用户管理页面重置密码。

### 不使用 Docker 的裸机部署

适用于无法安装 Docker 或希望直接控制各服务的场景。

#### 环境要求

| 组件 | 版本要求 |
|---|---|
| PostgreSQL | 16+ 并安装 pgvector 扩展 |
| Python | 3.12+ |
| Node.js | 20+ |
| nginx | 任意稳定版（用于反向代理和静态资源） |

#### 第一步：初始化数据库

```bash
# 安装 PostgreSQL 16 及 pgvector（Ubuntu 示例）
sudo apt install -y postgresql-16 postgresql-16-pgvector

# 创建用户和数据库
sudo -u postgres psql -c "CREATE USER vatknow WITH PASSWORD 'vatknow' SUPERUSER;"
sudo -u postgres psql -c "CREATE DATABASE vatknow OWNER vatknow;"
```

#### 第二步：启动后端 API

Python 是解释型语言，**不需要编译打包**，直接把源码目录部署到服务器、安装依赖即可运行。

先创建专用运行用户（systemd 服务中会用到）：

```bash
# 创建无登录权限的 www 用户，用于运行后端进程
sudo useradd -r -s /usr/sbin/nologin www
# 将项目目录归属给 www 用户，确保后端可读写
sudo chown -R www:www /var/www/vatknow
```

然后准备后端环境：

```bash
cd /var/www/vatknow/backend

# 创建虚拟环境并安装依赖
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 配置环境变量（参考 .env.example）
cp ../.env.example ../.env
nano ../.env   # 修改 DATABASE_URL、JWT_SECRET、OPENAI_API_KEY 等

# 测试启动（确认无报错后 Ctrl+C 停止）
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

生产环境建议用 gunicorn 管理 uvicorn 进程（多 worker + 崩溃自动重启）：

```bash
# 直接启动（systemd 会接管，这里仅作调试用）
.venv/bin/gunicorn app.main:app \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 127.0.0.1:8000 \
    --workers 2
```

> worker 数量建议：CPU 核数 × 2 + 1，内存不足时适当减少。

#### 第三步：构建并启动前端

```bash
cd /var/www/vatknow/frontend

npm ci
npm run build   # 产物输出到 dist/
```

#### 第四步：配置 nginx

将 [`deploy/nginx.prod.conf`](deploy/nginx.prod.conf) 复制到 nginx 配置目录，并按需修改：

```bash
sudo cp deploy/nginx.prod.conf /etc/nginx/sites-available/vatknow
sudo ln -s /etc/nginx/sites-available/vatknow /etc/nginx/sites-enabled/
sudo nano /etc/nginx/sites-available/vatknow
# 修改 server_name、root 路径等
sudo nginx -t && sudo systemctl reload nginx
```

#### 第五步：用 systemd 守护后端进程

将 [`deploy/vatknow-api.service`](deploy/vatknow-api.service) 安装为系统服务：

```bash
sudo cp deploy/vatknow-api.service /etc/systemd/system/vatknow-api.service
# 确认 User/Group 和路径与实际部署目录一致
sudo systemctl daemon-reload
sudo systemctl enable --now vatknow-api
sudo systemctl status vatknow-api   # 确认 active (running)
```

服务日志由 gunicorn 写入 `/var/log/vatknow-api-access.log` 和 `/var/log/vatknow-api-error.log`，需要先创建并授权：

```bash
sudo touch /var/log/vatknow-api-access.log /var/log/vatknow-api-error.log
sudo chown www:www /var/log/vatknow-api-*.log
```

可用 `journalctl -u vatknow-api -f` 查看 systemd 托管日志。建议配置 logrotate 防止日志无限增长：

```bash
sudo tee /etc/logrotate.d/vatknow-api << 'EOF'
/var/log/vatknow-api-*.log {
    daily
    rotate 14
    compress
    missingok
    notifempty
    copytruncate
}
EOF
```

#### 第六步：配置 HTTPS（可选）

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

certbot 会自动修改 nginx 配置并设置定期续期任务。

---

## 环境变量

| 变量 | 必填 | 说明 |
|---|---|---|
| `JWT_SECRET` | ✅ | JWT 签名密钥，建议 32 字符以上 |
| `OPENAI_API_KEY` | 推荐 | OpenAI 兼容接口密钥，留空则问答与向量检索不可用 |
| `OPENAI_BASE_URL` | | 接口地址，默认 `https://api.openai.com/v1` |
| `OPENAI_MODEL` | | 对话模型，默认 `gpt-4o-mini` |
| `EMBEDDING_MODEL` | | 向量模型，默认 `text-embedding-3-small` |
| `EMBEDDING_DIM` | | 向量维度，默认 `1536` |
| `DATABASE_URL` | | 数据库连接串，Docker 内自动配置 |
| `CORS_ORIGINS` | | 允许的跨域来源，逗号分隔。生产环境须改为实际域名，如 `https://your-domain.com` |
| `ENABLE_DOCS` | | 是否开放 Swagger API 文档（`/docs`、`/redoc`）。默认 `false`，本地开发可设为 `true` |

---

## 项目结构

```
vatknow/
├── backend/
│   ├── app/
│   │   ├── api/          # 路由层：auth / chat / documents / search / shares / public / site / users ...
│   │   ├── models/       # SQLAlchemy 实体定义
│   │   ├── schemas/      # Pydantic 请求/响应模型
│   │   ├── services/     # 业务逻辑：检索、RAG、索引、权限、审计 ...
│   │   ├── config.py     # 环境变量加载
│   │   ├── db.py         # 数据库连接与会话管理
│   │   └── main.py       # FastAPI 应用入口
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/   # API 文档编辑器、调试面板、目录树等组件
│   │   ├── views/        # 页面视图：空间、文档、检索、问答、设置 ...
│   │   ├── stores/       # Pinia 状态管理
│   │   ├── composables/  # 页面缓存、路由参数等组合式函数
│   │   ├── router.ts     # Vue Router 路由定义
│   │   └── api.ts        # HTTP 请求封装
│   ├── nginx.conf        # 生产环境 nginx 配置（反向代理 + 静态资源）
│   ├── Dockerfile        # 多阶段构建：node 编译 + nginx 运行
│   └── package.json
├── .env.example          # 环境变量模板
├── deploy/               # 裸机部署配置
│   ├── nginx.prod.conf   # nginx 生产配置（反向代理 + 静态资源）
│   └── vatknow-api.service # systemd 服务单元文件
├── docker-compose.yml
├── start.sh              # 本地开发启动脚本（macOS / Linux）
├── start.ps1             # 本地开发启动脚本（Windows PowerShell）
└── start.bat             # Windows 双击入口
```

---

## 主要页面

| 路由 | 说明 |
|---|---|
| `/` | 空间列表（首页） |
| `/spaces/:id` | 空间概览 |
| `/spaces/:id/docs` | 文档 Wiki（目录树 + 正文） |
| `/spaces/:id/docs/:docId/edit` | 文档编辑 |
| `/spaces/:id/ingest` | 收录新文档（Markdown / PDF / 网页 / OpenAPI） |
| `/spaces/:id/search` | 空间内检索 |
| `/spaces/:id/chat` | 智能问答（带引用） |
| `/spaces/:id/apis` | API Studio 列表 |
| `/spaces/:id/apis/:docId` | API 文档编辑与调试 |
| `/spaces/:id/logs` | 审计日志 |
| `/spaces/:id/settings` | 空间设置（成员、LLM 配置等） |
| `/search` | 全局跨空间检索 |
| `/p/:slug` | 公开空间页面 |
| `/s/:token` | 分享链接页面 |

---

## 许可证

[MIT License](LICENSE)
