# Architecture

本文档描述 PaperAI 当前代码结构，作为后续迭代前的快速上下文。

## 系统边界

PaperAI 是前后端分离应用：

- 前端位于 `frontend/`，负责登录注册、论文列表、PDF 阅读、论文问答和摘要/解读展示。
- 后端位于 `backend/app/`，提供认证、论文管理、聊天会话、PDF 解析、RAG 检索和 LLM 调用。
- 运行环境统一由 Docker Compose 管理，数据库使用 PostgreSQL，并使用 Redis。

## 后端入口

入口文件：`backend/app/main.py`

启动流程：

1. 创建 FastAPI 应用。
2. 配置 CORS。
3. lifespan 启动阶段调用 `init_db()` 初始化数据库表。
4. 挂载 API router。

已挂载 router：

- `app.api.auth.router`，前缀 `/api/auth`
- `app.api.papers.router`，前缀 `/api/v1/papers`
- `app.api.chat.router`，前缀 `/api/v1/chat`

## 后端模块

`backend/app/api/`

- `auth.py`：注册、登录、JWT 签发、当前用户读取。
- `papers.py`：论文上传、列表、详情、PDF 文件、章节、任务状态、删除、问答、解读、结构化摘要。
- `chat.py`：对话会话、会话消息、会话内问答、摘要缓存、解读缓存。

`backend/app/models/`

- `user.py`：用户表。
- `paper.py`：论文、章节、问答、表格、图片；遗留的笔记/文件夹模型未挂载为业务 API。
- `chat.py`：聊天会话、聊天消息、摘要缓存、解读缓存。

`backend/app/agent/`

- `paper_parser/graph.py`：论文元信息抽取、章节解析、解析结果整理。
- `qa_agent/graph.py`：基础论文问答 Agent。
- `qa_agent/enhanced_graph.py`：增强论文问答 Agent，包含意图识别、元信息回答、答案生成和后续问题生成。
- `summarizer/graph.py`：结构化摘要 Agent，抽取概览、方法、实验、贡献。
- `state.py`：Agent 状态类型。

`backend/app/rag/knowledge_base.py`

- `SmartChunker`：论文文本智能分块。
- `DashScopeEmbeddings`：Embedding 适配。
- `PaperKnowledgeBase`：论文知识库管理、检索、向量存储。

`backend/app/parsers/`

- `multimedia_extractor.py`：从 PDF 抽取图片、表格等多媒体信息。
- `image_filter.py`：过滤非核心论文图片。
- `image_analyzer.py`：图片语义分析。
- `table_analyzer.py`：表格语义分析。

`backend/app/llm/client.py`

- 统一封装 LLM 调用。配置来自 `backend/app/config.py` 和 `.env`。

## 前端结构

入口：

- `frontend/src/main.ts`
- `frontend/src/App.vue`
- `frontend/src/router/index.ts`

页面：

- `Home.vue`：首页。
- `Login.vue`：登录。
- `Register.vue`：注册。
- `PaperList.vue`：论文列表和上传。
- `PaperReader.vue`：论文阅读。
- `PaperQA.vue`：论文问答。

组件：

- `PdfViewer.vue`：PDF 阅读组件。

API 客户端：

- `frontend/src/api/index.ts`：Axios 实例、token 注入、401 处理。
- `frontend/src/api/auth.ts`：认证 API 调用。
- `frontend/src/api/paper.ts`：论文、任务、聊天、摘要、解读 API 调用。

## 核心业务流程

### 登录

1. 前端调用 `/api/auth/login`。
2. 后端校验用户名和密码。
3. 后端签发 JWT。
4. 前端将 `access_token` 保存到 `localStorage`。
5. Axios request interceptor 自动附加 `Authorization: Bearer <token>`。

### 上传论文

1. 前端 `uploadPaper(file)` 调用 `/api/v1/papers/upload`。
2. 后端保存 PDF 文件。
3. 后端创建论文记录和后台任务。
4. 后台流程解析文本、章节、图表、多媒体内容。
5. 解析结果写入数据库。
6. 文本内容进入知识库，供问答和检索使用。
7. 前端轮询 `/api/v1/papers/tasks/{task_id}` 获取任务状态。

### 论文问答

1. 前端调用 `/api/v1/papers/{paper_id}/qa` 或会话内 `/api/v1/chat/sessions/{session_id}/ask`。
2. 后端校验用户和论文权限。
3. 后端通过知识库检索相关 chunks。
4. 后端调用 enhanced QA Agent 生成答案。
5. 会话路径会额外保存消息历史。

### 摘要和解读

1. 摘要路径通过 summarizer Agent 生成结构化内容。
2. 解读路径根据 interpret type 生成指定角度内容。
3. `chat.py` 中存在摘要和解读缓存模型，避免重复生成。

## 数据与文件位置

- PostgreSQL：`postgres_data` Docker volume
- 上传 PDF、向量库和任务状态：`paperai_data` Docker volume，容器内位于 `/app/data`
- 服务日志：通过 `docker compose logs` 查看

## 启动与部署

项目统一由 Docker Compose 管理：

- backend
- frontend
- postgres
- redis

启动和更新使用 `docker compose up -d --build`。停止服务使用 `docker compose down`，不要附加 `-v`，否则会删除数据卷。
