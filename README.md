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
- systemd
- Docker Compose
- SQLite / PostgreSQL

## 目录结构

```text
.
├── backend/
│   ├── app/
│   │   ├── agent/      # 论文解析、摘要和问答 Agent
│   │   ├── api/        # 认证、论文、会话和分析接口
│   │   ├── llm/        # 大模型客户端
│   │   ├── models/     # 数据模型
│   │   ├── parsers/    # PDF、表格和图片解析
│   │   ├── rag/        # 分块、向量库和检索
│   │   ├── services/   # 文件与索引服务
│   │   └── utils/      # 后台任务与状态管理
│   └── tests/          # 后端测试
├── frontend/
│   ├── src/components/
│   ├── src/views/
│   └── src/api/
├── deploy/nginx/
├── docs/
├── docker-compose.yml
├── paperai-backend.service
└── paperai-frontend.service
```

## 本地开发

### 环境要求

- Python 3.10+
- Node.js 20+
- npm
- 可用的 Chat / Embedding 模型服务

### 配置环境变量

```bash
cp .env.example .env
```

至少配置：

```dotenv
SECRET_KEY=replace-with-at-least-32-characters
LLM_PROVIDER=qwen
OPENAI_API_KEY=your-key
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
OPENAI_MODEL=qwen-plus
EMBEDDING_MODEL=text-embedding-v3
```

### 启动后端

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cd backend
../.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 启动前端

```bash
cd frontend
npm ci
npm run dev
```

开发地址：

- Web：`http://localhost:5173`
- API：`http://localhost:8000`
- OpenAPI：`http://localhost:8000/docs`

## 测试与构建

后端测试：

```bash
cd backend
PYTHONPATH=. ../.venv/bin/pytest -q
```

前端构建：

```bash
cd frontend
npm run build
```

## 生产部署

### systemd + Nginx

前端构建后发布到 `/var/www/paperai`，Nginx 负责 HTTPS、静态资源和 `/api/` 反向代理。

```bash
sudo cp paperai-backend.service paperai-frontend.service /etc/systemd/system/
sudo cp deploy/nginx/paper.dongli.icu.conf /etc/nginx/sites-available/paper.dongli.icu.conf
sudo systemctl daemon-reload
sudo systemctl enable --now paperai-backend paperai-frontend
sudo nginx -t && sudo systemctl reload nginx
```

### Docker Compose

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

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/API.md`](docs/API.md)
- [`docs/DEV_NOTES.md`](docs/DEV_NOTES.md)
- [`docs/SMOKE_TESTS.md`](docs/SMOKE_TESTS.md)
- [`docs/TODO_OR_RISKS.md`](docs/TODO_OR_RISKS.md)
