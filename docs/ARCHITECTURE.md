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
- `app.api.paper_analysis.router`，前缀 `/api/v1/papers`（问答、解读、摘要）

## 后端模块

`backend/app/api/`

- `auth.py`：注册、登录、JWT 签发、当前用户读取。
- `papers.py`：论文上传、列表、详情、PDF 文件、章节、任务状态、删除。
- `chat.py`：对话会话、会话消息、流式问答、摘要缓存、解读缓存。
- `paper_analysis.py`：论文问答（agent 路径 + 旧 workflow fallback）、解读、结构化摘要。

`backend/app/models/`

- `user.py`：用户表。
- `paper.py`：论文、章节、问答、表格、图片；遗留的笔记/文件夹模型未挂载为业务 API。
- `chat.py`：聊天会话、聊天消息、摘要缓存、解读缓存。

`backend/app/harness/`（Agent 运行时层，与 API 网关解耦）

- `agents/lead_agent.py`：主 Agent，ReAct loop + 意图分析 + 多意图分解 + 流式输出。
- `agents/interpret_agent.py`：解读 Agent，调用 search_paper_content tool 并生成带 [Sx] 引用的结构化解读。
- `agents/critique_subagent.py`：批判性分析子 Agent（审稿意见、创新性评估）。
- `skills/registry.py`：Skill 注册与 tool 加载。
- `tools/paper_internal.py`：论文内部检索 tool（元数据、正文、表格）。
- `tools/external_literature.py`：外部文献检索 tool（arXiv API、Semantic Scholar API）。
- `tools/reading_assistant.py`：阅读辅助 tool（阅读进度、术语定义）。

`backend/app/agent/`（离线处理 pipeline + 旧 QA fallback）

- `paper_parser/graph.py`：论文元信息抽取、章节解析、解析结果整理。
- `qa_agent/enhanced_graph.py`：追问生成（`generate_follow_up_questions`）和旧 QA fallback 入口（`run_enhanced_qa_agent`）。工具函数已迁移至 `utils/qa_helpers.py`。
- `qa_agent/workflow.py`：确定性 QA workflow（`UnifiedQAWorkflow`），作为 agent 路径的 fallback。
- `summarizer/graph.py`：结构化摘要 Agent，抽取概览、方法、实验、贡献。
- `state.py`：Agent 状态类型（`QAAgentState`、`PaperParserState`、`SummarizerState`）。

`backend/app/utils/`

- `qa_helpers.py`：QA 工具函数（意图检测、引用构建、置信度计算），供 harness 和 api 层共用。
- `background_tasks.py`、`task_manager.py`：后台任务管理。

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
