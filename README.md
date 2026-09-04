# PaperAI

PaperAI 是一个面向学术论文阅读的 AI 辅助系统。用户上传 PDF 后，系统会解析论文结构、抽取正文与图表内容，构建论文级知识库，并提供结构化摘要、深度解读和带引用来源的论文问答。

## 核心功能

- PDF 上传、文件校验和后台解析任务管理
- 论文标题、作者、摘要、章节、表格和图片信息抽取
- 基于论文内容的向量检索和问答
- 多轮会话式论文问答
- 结构化摘要、概念解释、方法对比和关键结论提取
- 回答引用来源、PDF 页码定位和原文高亮
- 登录注册、论文列表、论文阅读器和阅读状态管理

## 技术栈

前端：

- Vue 3
- TypeScript
- Vite
- Arco Design Vue
- PDF.js
- Axios

后端：

- FastAPI
- SQLAlchemy Async
- LangGraph / LangChain
- ChromaDB
- PyMuPDF / pdfplumber
- OpenAI-compatible LLM API

部署：

- Nginx
- Docker Compose
- PostgreSQL

## 目录结构

```text
.
├── backend/
│   ├── app/
│   │   ├── agent/      # 离线 pipeline（论文解析、摘要）+ 旧 QA fallback
│   │   ├── api/        # 认证、论文、会话和分析接口
│   │   ├── harness/    # Agent 运行时层（lead_agent、tools、skills）
│   │   ├── llm/        # 大模型客户端
│   │   ├── models/     # 数据模型
│   │   ├── parsers/    # PDF、表格和图片解析
│   │   ├── rag/        # 分块、向量库和检索
│   │   ├── services/   # 文件与索引服务
│   │   └── utils/      # QA 工具函数、后台任务管理
│   └── tests/          # 后端测试
├── frontend/
│   ├── src/components/
│   ├── src/views/
│   └── src/api/
├── deploy/nginx/
├── docs/
└── docker-compose.yml
```

## 启动项目

### 环境要求

- Docker
- Docker Compose v2
- 可用的 Chat / Embedding 模型服务

### 配置环境变量

```bash
cp .env.example .env
```

至少配置：

```dotenv
SECRET_KEY=replace-with-at-least-32-characters
DEFAULT_ADMIN_PASSWORD=replace-with-a-strong-password
LLM_PROVIDER=qwen
OPENAI_API_KEY=your-key
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
OPENAI_MODEL=qwen-plus
EMBEDDING_MODEL=text-embedding-v3
```

### 启动服务

```bash
docker compose up -d --build
```

服务地址：

- Web：`http://localhost:5173`
- API：`http://localhost:8000`
- OpenAPI：`http://localhost:8000/docs`

### 开发模式（推荐日常开发）

首次启动需要构建开发镜像：

```bash
./dev.sh
```

之后修改代码不需要重新构建：

- `frontend/src/`：Vite 浏览器热更新
- `backend/app/`：Uvicorn 自动重载 API
- `backend/app/`：文件监听器自动重启 Worker
- 数据库和 Redis 数据继续保存在原有 Docker volumes 中

开发模式常用命令：

```bash
./dev.sh --no-build  # 使用已经构建的开发镜像
./dev-logs.sh        # 跟踪前端、后端和 Worker 日志
./dev-stop.sh        # 停止开发环境并保留数据
```

只有修改 `requirements.txt`、`package-lock.json`、Dockerfile 或 Compose
配置时才需要再次运行不带 `--no-build` 的 `./dev.sh`。数据库表结构变化仍会在
应用自动重载时执行项目当前的启动迁移。

常用命令：

```bash
docker compose ps
docker compose logs -f backend
docker compose restart backend frontend
docker compose down
```

仓库也提供只封装 Docker Compose 的快捷脚本：

```bash
./start.sh             # 构建并启动
./start.sh --no-build  # 使用现有镜像启动
./restart.sh           # 重新构建并重启
./stop.sh              # 停止容器并保留数据卷
```

不要使用 `docker compose down -v`，除非明确需要删除 PostgreSQL 和 PaperAI 数据卷。

## 测试与构建

后端测试：

```bash
docker compose exec backend pytest -q
```

前端构建：

```bash
docker compose build frontend
```

## 生产部署

项目统一使用 Docker Compose 部署：

```bash
SECRET_KEY='replace-with-at-least-32-characters' docker compose up -d --build
```

## 主要 API

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | `/api/auth/register` | 注册 |
| POST | `/api/auth/login` | 登录 |
| GET | `/api/v1/papers/` | 论文列表 |
| POST | `/api/v1/papers/upload` | 上传论文 |
| GET | `/api/v1/papers/tasks/{task_id}` | 查询解析任务 |
| GET | `/api/v1/papers/{paper_id}` | 论文详情 |
| GET | `/api/v1/papers/{paper_id}/pdf` | 获取 PDF |
| POST | `/api/v1/papers/{paper_id}/qa` | 单轮论文问答 |
| POST | `/api/v1/chat/sessions/{session_id}/ask` | 多轮会话问答 |
| POST | `/api/v1/papers/{paper_id}/summarize` | 结构化摘要 |
| POST | `/api/v1/papers/{paper_id}/interpret` | 深度解读 |

当前不提供笔记功能，`/api/v1/notes` 未挂载。

## 更多文档

- [`docs/spec-v2/README.md`](docs/spec-v2/README.md)
- [`docs/spec-v2/architecture/SYSTEM_ARCHITECTURE.md`](docs/spec-v2/architecture/SYSTEM_ARCHITECTURE.md)
- [`docs/API.md`](docs/API.md)
- [`docs/DEV_NOTES.md`](docs/DEV_NOTES.md)
- [`docs/SMOKE_TESTS.md`](docs/SMOKE_TESTS.md)
- [`docs/TODO_OR_RISKS.md`](docs/TODO_OR_RISKS.md)
