# Project Agent Upgrade Context

> 生成日期：2026-08-17  
> 分析对象：`main` 分支当前工作区（包含未提交修改与未跟踪文件）  
> 说明：本文描述代码事实，不是目标架构设计。除特别标记为“推断/未确认”外，结论均来自当前工作区源码。行号会随代码变化，稳定定位优先采用 `路径::符号`。

## 1. Executive Summary

当前 PaperAI 已不是单一 RAG 问答应用。它由三层能力叠加而成：

1. 论文资产层：PDF 上传、解析、版面元素/章节/图表结构化、父子分块、Chroma 向量索引、PDF 阅读器与页框引用定位。
2. 问答工作流层：混合检索、确定性与模型重排、证据审查、LangGraph QA/摘要/解析工作流、Redis 队列、可恢复 SSE、持久化回答 Trace。
3. 初步 Research Agent 层：`ResearchProject`、项目论文多对多关系、长期 JSON memory、写作产物、基于 SKILL.md 的工具注册、Lead Agent ReAct tool-calling loop、Critique SubAgent、跨论文检索、外部 arXiv/Semantic Scholar 搜索及写作工作台。

因此当前系统本质上是 **workflow-oriented RAG application + 已落地的 agent runtime 原型**。单论文 QA 仍保留图式工作流；项目模式已满足“模型按状态动态选择 Tool”的 Agent 判据。Agent 化并非从零开始，但 Project/Harness 大部分属于未提交工作，数据迁移、权限工具边界、任务持久化、前端状态拆分和运行时统一仍是升级重点。

事实边界：

- **已确认**：路由、模型、Agent、Tool、Skill、Worker 和项目页面均已在当前源码中接通。
- **高概率推断**：配置正确且第三方凭据可用时，DeepSeek/OpenAI-compatible LLM、DashScope embedding、arXiv 和 Semantic Scholar 可运行；本次未调用外部服务。
- **未确认**：生产数据规模、真实 Chroma collection 与数据库兼容性、线上 Nginx 配置是否与仓库一致、完整浏览器 E2E 体验。

## 2. Repository Overview

- 单仓库，后端 FastAPI/Python，前端 Vue 3/TypeScript。
- 关键顶层目录：`backend/app`（运行代码）、`backend/tests`（pytest）、`backend/evals`（RAG/E2E 评测）、`frontend/src`（SPA）、`deploy`（HTTPS/Nginx）、`docs`（架构与运维说明）。
- Git：分支 `main`；最近提交依次为管理员控制台、QA/检索/阅读工作台升级、论文处理优化。
- 工作树 **不干净**：既有大量已修改文件，也有未跟踪的 `backend/app/harness/`、项目模型/API/前端页面等。本文以这些文件存在且被 `main.py`/Router 实际引用为当前事实，但不能视为已发布版本。
- 没有发现 GitHub Actions、Alembic、Makefile、统一 lint/format 配置。

证据：`backend/app/main.py`、`frontend/src/main.ts`、`git status --short`、`git log -5 --oneline`。

## 3. Directory Structure

```text
PaperAI/
├── backend/
│   ├── app/
│   │   ├── main.py, config.py, database.py, worker.py
│   │   ├── api/              # auth/papers/analysis/chat/admin/projects 路由
│   │   ├── models/           # User/Paper/Chat/ResearchProject 等 ORM
│   │   ├── services/         # 上传、核心处理、索引、远程导入、版面与表格
│   │   ├── parsers/          # 图片、表格、多媒体提取与分析
│   │   ├── rag/              # Chroma KB、混合/表格检索、证据审查
│   │   ├── agent/            # LangGraph parser/QA/summarizer workflows
│   │   ├── harness/
│   │   │   ├── agents/       # Lead ReAct、Interpret、Critique、routing
│   │   │   ├── tools/        # 单论文、阅读、外部检索、项目复合工具
│   │   │   └── skills/       # SKILL.md 与注册器
│   │   ├── llm/client.py     # Provider、重试、流式、tool binding
│   │   └── utils/            # 任务状态、后台任务、导出、QA helpers
│   ├── tests/                # 单元/结构/API 边界测试
│   ├── evals/                # 检索和端到端评测数据与脚本
│   └── scripts/              # 回填、重建索引、迁移、冒烟验证
├── frontend/
│   ├── src/
│   │   ├── views/            # 首页、库、阅读器、项目、写作、管理页
│   │   ├── components/       # PDF/目录/壳层与项目组件
│   │   ├── api/              # Axios + SSE fetch 客户端
│   │   ├── utils/            # Markdown 安全渲染、PDF cache、账户会话
│   │   └── router/index.ts
│   ├── nginx.conf, Dockerfile, vite.config.ts
├── deploy/                    # 公网 Nginx 与 HTTPS 脚本
├── docker-compose.yml         # backend/worker/Postgres/Redis/frontend
└── docs/                      # 当前说明、评测/风险/架构文档
```

模块关系不是严格 Clean Architecture：API 常直接查询 ORM；复杂论文处理已抽到 Service；RAG 与 Agent 可独立调用；Harness Tools 又直接持有 `AsyncSession` 并操作 ORM。

## 4. Technology Stack

| 层 | 已确认技术 |
|---|---|
| Backend | Python；FastAPI 0.109.2、Pydantic 2.6.1/settings 2.1.0、SQLAlchemy async 2.0.25、Uvicorn 0.27.1 |
| AI orchestration | LangChain 0.1.20/core 0.1.52/community 0.0.38、LangGraph 0.0.40、自研 Harness/ReAct loop |
| LLM | `langchain-openai` 0.0.8、OpenAI SDK 1.12；DeepSeek 与 OpenAI-compatible provider；可配置 thinking、JSON mode、stream、tool calling |
| PDF | pypdf 4.1、pdfplumber 0.10.4、PyMuPDF 1.24；无独立 OCR 依赖 |
| Retrieval | ChromaDB 0.4.22、本地 BM25 实现、表格精确检索、规则与 LLM rerank |
| Data | PostgreSQL 15（Compose 默认）、SQLAlchemy 同时支持 SQLite、Redis 7、Chroma 持久目录、本地文件系统 |
| Frontend | Vue 3.4、TypeScript 5.3、Vite 5.1、Vue Router 4.3、Pinia 2.1（依赖存在但未见 store）、Arco Design Vue 2.55、Axios 1.6 |
| Rendering | pdfjs-dist 4.10、markdown-it 14.2、DOMPurify 3.4；无 KaTeX/MathJax/代码高亮插件 |
| Deploy | Docker、Compose、Nginx；backend 与 worker 同镜像 |

依赖版本证据：`backend/requirements.txt`、`frontend/package.json`、`docker-compose.yml`。

## 5. Current Product Capabilities

| 用户能力 | 前端入口 | 后端/核心 | AI/执行方式 | 持久化 |
|---|---|---|---|---|
| 注册、登录、管理员权限 | Login/Register/AdminUsers | `/api/auth/*` | 无；同步 | users + JWT(localStorage) |
| 上传/管理论文 | PaperList | `/papers/upload`、PaperUpload/CoreProcessing | Parser LLM；Redis Worker 异步 | PDF+SQL+Chroma+Redis task |
| 阅读 PDF、目录跳转、引用高亮 | PaperReader/PdfViewer/PaperOutline | pdf/sections/elements | 无 | 阅读状态 SQL；PDF cache 浏览器内 |
| 单论文连续问答 | PaperReader | chat session + worker | Harness/QA，SSE 可恢复 | sessions/messages/trace + Redis task |
| 摘要和多种解读 | PaperReader tabs | analysis/chat summary/interpret | LangGraph/Interpret Agent | cache tables |
| 收藏、进度、状态 | PaperList/Reader | PATCH paper status | 无 | papers |
| 项目管理与多论文库 | ResearchProjectList/Workspace | `/api/v1/projects` | 可由 Tool 操作 | project/project_papers |
| 外部论文搜索/导入 | TopicExplorer/Agent | arXiv search/import | 外部 API + upload worker | Paper + project relation |
| 项目长期记忆 | Workspace/Agent | memory endpoints/tools | Agent 可追加 | research_projects.memory JSON |
| 写作产物与编辑 | Workspace/WritingStudio | artifacts CRUD/download | Agent 或用户编辑 | writing_artifacts 三种内容表示 |
| 项目聊天与跨论文研究 | ProjectChat | project-bound ChatSession | Lead Agent 动态选 Tool | SQL + Redis + Trace |
| 管理监控 | AdminDashboard/Traces | `/api/admin/*` | 无 | SQL Trace/聚合 |

`Note`、`Folder`、`QAPair` 模型存在，但没有发现对应完整 CRUD 页面/API，属于部分资产而非完整用户功能。

## 6. Backend Architecture

实际分层为混合式：

```text
FastAPI Router
 ├─ 直接鉴权、校验、ORM 查询/写入、Response/SSE
 ├─ 调用 paper services / RAG / agent harness
 └─ 入 Redis job queue
       ↓
    worker.py dispatcher
       ├─ paper processing
       ├─ chat answer
       └─ reading execution/import
```

- Router 仍含大量业务编排：`api/papers.py`、`api/chat.py`、`api/projects.py` 都是大文件。
- 没有 Repository 层；Service/Tool 直接操作 ORM。
- `paper_upload.py`、`paper_core_processing.py`、`paper_indexing.py` 已形成可测试边界。
- `rag/` 是相对独立的检索域；`llm/client.py` 是 provider 边界。
- Agent Runtime 的现有插入点就是 Worker 的 chat job 与 `harness/agents/lead_agent.py`，无需塞入 ORM 或 Router；这是“扩展边界”事实，不是最终方案。

## 7. Frontend Architecture

Vue SPA 使用按路由懒加载。没有发现实际 Pinia store，状态主要散落在大型 View 的 `ref/reactive/computed` 中；认证令牌和用户信息使用 localStorage。Axios 承担普通 API，原生 `fetch` 解析 SSE。

大型页面：`PaperReader.vue`（约 2890 行）、`ProjectWorkspace.vue`（约 1899 行）、`PaperList.vue`（约 1023 行）、`Home.vue`（约 1083 行）。它们同时承担数据获取、状态机、事件处理和大量 scoped CSS，是扩展时的主要耦合点。

## 8. Database Architecture

- `AsyncEngine` + `async_sessionmaker`；启动时 `Base.metadata.create_all`。
- 默认 PostgreSQL；代码保留 SQLite 驱动与迁移脚本 `migrate_sqlite_to_postgres.py`。
- **无 Alembic/版本化 migration**。`create_all` 只建缺失表，不可靠地演进已有列/约束。
- 结构化业务数据在 SQL；向量及 chunk metadata 在 Chroma；任务/checkpoint 在 Redis；PDF/表格截图/导出在文件系统。

证据：`backend/app/database.py::init_db`、`backend/app/main.py::lifespan`。

## 9. Paper Processing Pipeline

```text
PaperList.vue 选择/拖拽 PDF
  → api/paper.ts::uploadPaper (multipart + Bearer)
  → POST /api/v1/papers/upload
  → PaperUploadService.receive
      校验 PDF/大小 → data/papers/{uuid}.pdf → SHA-256
  → Redis dedupe(user + sha256) / task_{paper_id}
  → enqueue_job("paper_process")
  → worker.py
  → PaperUploadService.extract_text (pypdf/pdfplumber fallback，具体见 paper_files.py)
  → PaperCoreProcessingService.extract_structure
      run_paper_parser (LangGraph/LLM)
      normalize/enrich sections
      PyMuPDF layout elements
  → persist_core: Paper + Section + DocumentElement
  → build_text_index
      element chunks → section/page fallback → SmartChunker
      → DashScopeEmbeddings batch → Chroma collection `papers`
  → multimedia/table/image enhancement
  → Redis task completed
  → PaperList 轮询 /tasks/{task_id}
```

失败路径会更新任务状态；文本解析异常删除 PDF；核心数据已就绪但图表增强失败时论文仍可用。任务支持启动恢复，但恢复次数上限为 2。

证据：`api/papers.py::upload_paper/_process_paper_async`、`services/paper_upload.py`、`services/paper_core_processing.py`、`worker.py`。

## 10. Chunking Architecture

`SmartChunker` 先按中英文标点句界切分，失败时按段落，再退到 200 字固定片段。生成 1200/200 overlap 的 large 父块和 400/100 overlap 的 small 子块；metadata 包含 `content/type/section/index/parent_index/sentence_range`，索引前再补 `paper_id/page/chunk_type/element_id/bbox/section_path` 等可用定位信息。

优先基于 `DocumentElement` 构建物理版面块；失败时按章节与 PDF 页回退，并额外补齐 front matter。Chunk 不在 SQL 独立建表，只存在 Chroma，ID/版本与重新解析生命周期较弱。

适配判断：页码、bbox、element、section 已能支持较好的精确引用；但缺少稳定 Evidence 实体、embedding/version lineage、project namespace、chunk revision 与跨产物引用外键，尚不足以完整支撑 Research Memory 和写作证据审计。

## 11. Embedding Architecture

- `DashScopeEmbeddings` 手写 OpenAI-compatible `/embeddings` 调用，默认模型环境变量名 `EMBEDDING_MODEL`，维度固定 1024。
- 认证复用配置中的 API key/base URL；实际构造逻辑见 `PaperKnowledgeBase.__init__`。
- 文档以 10 条批处理；查询单条；无显式 embedding cache。
- 代码主动警告旧/新模型向量空间不能混用，但未发现自动 collection version migration。
- 配置默认值 `text-embedding-3-small` 与实现注释中的 DashScope/qwen 路径存在认知不一致风险，应以运行配置和构造代码共同核实。

## 12. Vector Store Architecture

- 单个持久化 Chroma collection：`papers`，目录由 `VECTOR_STORE_PATH` 指定。
- 所有论文共享 collection，以 metadata `paper_id` 过滤；删除论文按 paper filter 删除。
- User isolation 不在 Chroma metadata 层表达，依赖 API 先验证 Paper/Project 所有权；Project 跨论文检索逐个 paper 查询/归并，而非 project namespace。
- 当前组织是 `User → Paper → (SQL elements/sections + Chroma chunks)`，同时新增 `User → ResearchProject ↔ Paper`。Evidence 尚非一级实体。

证据：`rag/knowledge_base.py::PaperKnowledgeBase.vectorstore/query/delete_paper`。

## 13. RAG Architecture

存在两条主要路径：

1. `PaperKnowledgeBase.query`：Chroma 相似检索、paper filter、父块恢复与本地重排。
2. `HybridPaperRetriever`：问题规划 → 指代消解 → vector/BM25/表格行/表格/图片多通道召回 → reciprocal/词汇规则重排 → 可选 LLM semantic rerank → 去重 → Evidence review/context/citation。

特性：动态 top_k（简单 4、一般 6、比较 10）、candidate_k 最多 40；比较问题拆分；表号/数值查询优先结构化表格；轻量历史改写；来源含页码、section、bbox/element 时可回到 PDF。无独立商业 reranker。跨项目检索在 `harness/tools/literature_research.py::_rank_project_chunks/project_search_content` 聚合多篇论文。

防幻觉基础包括证据质量审查、citation `[Sx]` 约束、confidence 和可选 second pass；它降低而不消除幻觉。

## 14. LLM Architecture

`app/llm/client.py` 集中封装 ChatOpenAI-compatible client：按 `LLM_PROVIDER` 选择 DeepSeek/OpenAI 配置，支持普通/异步生成、JSON mode、thinking content、流式、timeout、重试和 `bind_tools`。Vision 配置存在，图片分析器使用 `VISION_MODEL/VISION_BASE_URL`；并非统一多 provider 注册表。

外部边界与变量：`DEEPSEEK_API_KEY/MODEL/BASE_URL`、`OPENAI_API_KEY/MODEL/BASE_URL`、`VISION_MODEL/BASE_URL`、`EMBEDDING_MODEL`。不得在文档记录密钥值。

## 15. Chat Architecture

`ChatSession` 可绑定 `paper_id` 或 `project_id`；`ChatMessage` 一行同时保存一组 question/answer，而非通用 role-message。创建、列表、历史、删除、同步 ask、SSE ask、恢复、停止均在 `api/chat.py`。

SSE 请求不会在 HTTP handler 内直接跑完整 LLM：它创建 Redis answer task、入队，`worker.py` 调 Lead Agent/QA，再持续把 answer/reasoning/stage/citations 写 Redis；HTTP 流只增量读取任务。因此断线可通过 task ID + offset 恢复。

完成后写 `ChatMessage`、citations、confidence，并持久化 `AnswerTrace`。未发现 regenerate 专用 API；重试是 LLM/job 级，不是产品级“重新生成”。

## 16. Conversation & Context Management

- 多轮上下文来自 SQL `ChatMessage`，通常取最近 5 组 QA，格式化为文本注入 system prompt。
- 并非把全部历史作为标准消息数组发送；Lead Agent 只把压缩后的字符串拼进 prompt。
- 简单指代由 `rewrite_standalone_question` 结合历史上一问题改写。
- Project context 额外加载项目主题、memory、项目论文和近期 artifacts，并有字符截断。
- 没有独立通用 Context Manager、token-budget planner 或历史摘要实体；上下文策略分布在 chat worker、QA workflow 和 Lead Agent。

证据：`harness/agents/lead_agent.py::_load_project_context/stream_lead_agent`、`rag/hybrid_retrieval.py::rewrite_standalone_question`。

## 17. Prompt Architecture

| Prompt 类别 | 位置 | 形态/输入 |
|---|---|---|
| Skill instructions | `harness/skills/*/SKILL.md` | 文件化；registry 拼入 system prompt |
| Lead Agent 行为/上下文 | `harness/agents/lead_agent.py` | 硬编码模板 + paper/project/history/skills |
| Critique/Interpret | `harness/agents/*.py` | Python f-string；问题、证据、历史 |
| QA/retrieval/evidence | `agent/qa_agent/*`、`rag/*` | Python f-string；query/chunks/history |
| Paper parsing/summarization | `agent/paper_parser/graph.py`、`agent/summarizer/graph.py` | 节点内模板；原文/章节 |
| Image/table analysis | `parsers/*_analyzer.py` | Python 内模板 |

Prompt 没有数据库版本、实验标识或统一 template registry。SKILL.md 已是可扩展复合指令资产，但基础 prompts 仍散布且难以统一评测/版本回滚。

## 18. Current Workflow / Agent Capabilities

### LangGraph workflows

- Paper Parser state：paper_id/file_path/raw_text/metadata/sections/error；节点解析 metadata 与 sections，最后汇总。
- QA state：paper_id/question/history_context/intent/retrieved_chunks/answer/citations/confidence/follow-ups/error；检索、生成、审查/增强等图节点，具体图见 `qa_agent/workflow.py`。
- Summarizer state：paper/sections/summary/error；固定摘要图。

这些是固定 workflow，不因目录名而自动成为 Agent。

### 真正 Agent

`run_lead_agent` 从 SkillRegistry 加载工具与 SKILL.md，`bind_tools` 后循环：LLM 选择 tool → 执行 → ToolMessage 回填 → 再决策，最多 `max_iterations`，最后强制收尾；可特殊委派 `delegate_to_critique`。这是已确认的动态 Tool Agent。支持 Redis checkpoint 序列化消息，但 checkpoint 不是完整持久 Task/Event 模型。

Routing 在 direct/workflow/agent 之间选择，项目模式注入 project tools。当前属于 Agent + Workflow 并存，而不是统一 LangGraph Agent Runtime。

### Harness / Skill 当前完成度边界

这一部分是当前工作区中**正在建设、尚未完全收口**的架构，不能因为目录和类已经存在就认定为完整 Agent Platform。尤其是 `backend/app/harness/`、项目 API/模型和对应前端大多仍是 Git 未跟踪文件；它们已经被当前工作区入口引用并有测试/验证脚本，但尚未进入当前分支的提交历史。

| 模块 | 当前状态 | 已确认实现 | 尚缺或未确认 |
|---|---|---|---|
| SkillRegistry | **已接通，基础能力完成** | 扫描 Skill manifest/SKILL.md、加载关联工具、构建 system prompt | Skill 版本、依赖声明、冲突检测、热更新、权限元数据、发布生命周期 |
| SKILL.md 指令层 | **已接通，内容较完整** | `paper_internal`、`reading_assistant`、`external_literature`、`literature_research` 已定义适用边界、工具和典型步骤 | 指令没有统一 schema/version；缺少自动 lint、eval 绑定、逐 Skill 成功率与回滚机制 |
| Tool 层 | **大量能力已实现** | StructuredTool + Pydantic 输入；单论文、表格、阅读进度、外部搜索、项目 memory/artifact/研究写作工具可被注册 | 文件集中度高；没有统一权限/用户确认、side-effect 等级、幂等、超时、配额和事务协议 |
| Lead Agent | **核心 loop 已实现，仍属原型/半成品 Runtime** | LLM `bind_tools`、多轮 ToolMessage、最大迭代、流式回调、工具 Trace、项目上下文、无工具降级 | 没有正式 execution/event 数据模型、统一 budget、可重放日志、人工审批节点、并发分支、通用计划器和可靠长期恢复 |
| Routing | **已实现启发式分流** | direct/workflow/agent 选择、项目 action 识别、快速 intent + LLM intent | 规则与 prompt 可能漂移；没有策略版本、线上路由评测/灰度或统一 fallback contract |
| Checkpoint | **部分实现** | Agent 消息可序列化到 Redis，并能按 request_id 读写/删除 | Redis TTL 后不可审计；不是数据库级 durable checkpoint；Tool 副作用与 checkpoint 之间无原子一致性 |
| Streaming | **较完整** | reasoning/answer/stage/task/trace 通过 Redis-backed SSE 输出，可 offset 恢复和 stop | UI 中没有跨页面统一任务中心；所有 Tool 是否及时响应 cancel 未确认；背压和大量并发未验证 |
| Critique SubAgent | **单一委派路径已实现** | Lead Agent 通过虚拟 Tool 特殊分支委派 critique，并回收评分/结果 | 不是通用 SubAgent registry；没有子任务持久模型、权限隔离、上下文预算、递归/并行治理 |
| Project context | **已实现初版** | 加载 topic、memory、项目论文、近期产物并截断后注入 prompt | 截断以字符规则为主；没有 token planner、相关性选择、上下文快照/version 或 provenance graph |
| Project memory | **可用初版** | summary + notes JSON；API 与 Agent Tool 均可读写，Skill 给出记录规范 | 尚非独立 Memory 服务；缺少 note ID/索引/检索/去重/合并/审计/并发控制与容量策略 |
| 多论文研究 | **主要工具已实现，规模能力未验证** | project paper library、跨论文检索、卡片、筛选、领域地图、证据矩阵和阅读计划 | 跨论文检索为逐篇执行/归并；大项目性能、全局去重、citation lineage 与任务编排未验证 |
| 写作 Harness | **功能面很宽，但仍是早期实现** | blueprint、section draft、assemble、reference list、audit、finalize 等 Tool 与 artifact 持久化 | 质量门主要依赖结构化输入/规则；编辑器 schema、引用实体、人工批准、版本分支和可重复生成尚未完整 |
| 外部文献能力 | **已实现基础接入** | arXiv 与 Semantic Scholar 搜索、重试/降级、arXiv PDF 导入现有 Worker | Provider 覆盖有限；限流、版权/许可、元数据规范化、DOI 去重与生产稳定性未验证 |
| 测试与验证 | **后端结构测试较多，系统验证不完整** | agent routing、project contracts/retrieval、harness tools、manuscript flow 等 tests/scripts | 缺少前端 E2E、真实多轮长任务回归、故障注入、并发/恢复/成本测试和 CI gate |

综合判断：当前 Harness 不是空壳，也不是只有概念文档；动态 Tool Calling、Skill 注入、项目上下文、SubAgent 特例、Redis checkpoint/stream 和大量业务 Tools 都有真实代码。但是它也还不是完整、稳定、统一的 Agent Harness。更准确的描述是：**核心执行闭环已经跑通，业务能力铺设较多，而持久执行、权限治理、状态协议、版本评测、长任务可靠性和前端任务体验仍处于半成品阶段。**

## 19. API Inventory

所有业务 API 除登录/注册外均通过 Bearer JWT；管理员端另检查 role。

| Method | Path（前缀省略处已写全） | 功能/主要调用方 |
|---|---|---|
| POST | `/api/auth/login`, `/register` | 登录、注册 |
| GET/PATCH | `/api/auth/users/me`, `/admin/users*` | 当前用户、用户管理 |
| GET | `/api/v1/papers/` | 论文分页/搜索/状态筛选 |
| POST | `/api/v1/papers/upload` | 上传并入 worker |
| GET | `/api/v1/papers/tasks/{task_id}` | 上传进度 |
| GET | `/api/v1/papers/{id}`, `/{id}/pdf`, `/{id}/sections`, `/{id}/elements` | 阅读资产 |
| POST/PATCH/DELETE | `/{id}/sections/rebuild`, `/{id}/status`, `/{id}` | 重建、阅读状态、删除 |
| POST | `/api/v1/papers/{id}/qa`, `/interpret`, `/summarize` | 分析工作流 |
| GET | `/api/v1/chat/recent-messages`, `/sessions`, `/sessions/{id}/messages` | 聊天查询 |
| POST/DELETE | `/api/v1/chat/sessions`, `/sessions/{id}` | 会话生命周期 |
| POST | `/api/v1/chat/sessions/{id}/ask`, `/ask/stream` | 同步等待/SSE 回答 |
| GET/POST | `/api/v1/chat/answer-tasks/{id}[/stream|/trace|/stop]` | 任务查询、恢复、Trace、停止 |
| GET/POST | `/api/v1/chat/papers/{id}/summary`, `/interpret/{type}` | cache 读取/生成 |
| CRUD | `/api/v1/projects` | 项目 |
| GET/POST/PATCH/DELETE | `/api/v1/projects/{id}/papers*` | 项目文档库、论文卡片 |
| CRUD | `/api/v1/projects/{id}/artifacts*` | 写作产物与下载 |
| GET/PATCH/POST | `/api/v1/projects/{id}/memory[/note]` | 项目长期记忆 |
| GET/POST | `/api/v1/projects/{id}/external-papers/search|import` | 外部搜索/导入 |
| POST/GET | `/api/v1/projects/{id}/reading-executions*` | 启动/状态/pause/resume |
| GET | `/api/v1/projects/{id}/workflow-status` | 工作流就绪状态 |
| GET | `/api/admin/dashboard`, `/traces`, `/traces/{trace_id}` | 管理观测 |

完整装饰器事实索引：`backend/app/api/*.py`。注意 `/api/v1/papers/{paper_id}` 等动态路由与固定 `/upload` 的声明次序需持续用测试守护。

## 20. Data Model Inventory

| 表 | 主键/重要关系 | 用途与关键字段 |
|---|---|---|
| users | UUID string | username/email/password_hash/role/preferences；拥有 papers/projects/sessions |
| papers | UUID；user_id | 元数据、截断 full_text、pdf_path、阅读状态 |
| sections | paper_id | 标题、顺序、起始页、正文、图表公式 JSON |
| document_elements | paper_id/section_id | 页、bbox、类型、版面顺序、section_path、可索引标志 |
| tables / table_structures / table_cells | paper/section/table | 物理表、结构化网格/行记录/单元格与截图 |
| images | paper/section | 图片位置、caption、分析结果/路径 |
| qa_pairs | paper_id | 旧式 QA/阅读进度资产 |
| notes / folders | user/paper/folder | 笔记和层级目录；产品入口不完整 |
| chat_sessions | user_id；paper_id?；project_id? | 单论文或项目会话 |
| chat_messages | session_id + order_index | question/answer/citations/followups/confidence |
| summary_cache / interpret_cache | user+paper | AI 结果缓存 |
| answer_traces | trace_id/task/user/session | 延迟、token、调用/重试、citation 指标 |
| research_projects | user_id | topic/phase/status/memory/preferences |
| project_papers | unique(project,paper) | role/tags/notes/card/reading_plan/priority |
| writing_artifacts | project/author/parent? | type/version/content/markdown/html/status/meta |

## 21. File & Data Lifecycle

```text
PDF bytes → FILE_STORAGE_PATH/{paper_id}.pdf
       ├→ SQL Paper/Section/DocumentElement/Table/Image
       ├→ Chroma papers collection (chunk text + metadata + embeddings)
       ├→ generated table CSV/Markdown/screenshots under data paths
       └→ Redis upload task

Chat request → Redis job/task/checkpoint/cancel flag
            → SQL ChatMessage + AnswerTrace

Project → SQL project relation/memory/artifacts
        → optional exported manuscript response/file generation
```

删除 Paper：先删 Chroma filter，再 ORM cascade，再删 PDF。表格衍生文件/截图是否全部显式删除未能从删除 handler 确认，存在孤儿文件风险。数据库提交与 Chroma/文件删除没有跨存储事务，任一步失败可产生不一致。Project 移除论文只删关联，不删论文。

## 22. Authentication & Authorization

- JWT HS256，过期默认 7 天；密码由 passlib bcrypt 哈希。
- Router 从 Authorization header 解析 user；Paper/Session/Project 查询普遍带 user_id；无权限资源常返回 404 防枚举。
- PDF endpoint 检查所有权；管理员 API 检查 role/is_active。
- Chroma 自身不含 user namespace，因此所有调用链必须先完成 SQL ownership；Tools 是高风险边界，当前工厂注入 user/project 并在部分查询复核所有权。
- ResearchProject 已具备清晰 user_id 隔离基础，但默认管理员密码和生产 SECRET_KEY 依赖启动配置；配置 validator 在非 DEBUG 阻止弱默认 secret。

## 23. Frontend Pages

| Route | Page | 结构/用途 |
|---|---|---|
| `/home` | Home | 营销首页、导航、功能与流程展示 |
| `/guide` | Guide | 左侧目录 + 使用指南 |
| `/login`, `/register` | Auth pages | AuthShell 表单 |
| `/papers` | ResearchProjectList | 当前重定向语义为研究项目工作台（名称仍 PaperWorkbench） |
| `/library` | PaperList | 继续阅读、最近问题、论文筛选列表、上传弹窗 |
| `/paper/:id` | PaperReader | 顶栏；左目录 + 中 PDF + 右 AI tabs，可切布局/移动 pane |
| `/projects` | ResearchProjectList | 项目列表/创建 |
| `/project/:id` | ProjectWorkspace | 研究、阅读、写作三工作区，共享论文/产物/memory |
| `/project/:id/chat` | ProjectChat | 项目级 Agent 连续对话 |
| `/admin` | AdminDashboard | 系统健康、使用与评测指标 |
| `/admin/traces` | AdminTraces | Trace 查询与工具调用详情 |
| `/admin/users` | AdminUsers | 用户/权限管理 |

Router guard 校验 token，管理员 route 用 meta 控制；公共页面仅 home/guide/login/register。

## 24. Frontend Components

- 可直接复用通用壳：`ProductHeader`、`AuthShell`、`AdminShell`、`BrandMark`。
- 论文业务核心：`PdfViewer`（分页渲染、缩放、宽度适配、引用 bbox 高亮）、`PaperOutline`/Node。
- 项目组件：`TopicExplorer`（外部搜索筛选）、`WritingStudio`（章节、contenteditable、参考论文侧栏/引用）。
- 高耦合页面：PaperReader 内置会话、流式状态、摘要/解读、引用交互；ProjectWorkspace 内置大量 tab、API orchestration 与展示。

## 25. Frontend State Management

- 实际采用 Vue Composition API 局部状态；未发现 `stores/` 或 `defineStore`，虽安装 Pinia。
- User/token：localStorage + router guard；另有 `accountSessions.ts`。
- Paper/upload/stream：各 View 的 refs；上传靠轮询；流靠回调修改临时 message。
- 没有共享规范化 cache、server-state query 库或全局 task store。跨页面长期 Agent 活动和多并发任务会遇到状态复制/恢复复杂度。

## 26. Streaming Architecture

```text
LLM astream / Agent event callback
  → worker 更新 Redis answer task（reasoning、answer、stage、trace）
  → FastAPI StreamingResponse text/event-stream
  → api/paper.ts 原生 fetch + ReadableStream parser
  → onTask/onReasoning/onDelta/onCitation/onDone callbacks
  → PaperReader/ProjectChat 局部 reactive message
  → renderMarkdown + DOMPurify
```

支持 task id、answer/reasoning offset 续传、断开后 `/answer-tasks/{id}/stream` 恢复及 stop flag。不是 WebSocket。Nginx 配置必须关闭 buffering；API 已发送 `X-Accel-Buffering: no`。

## 27. Current UI Design System

`App.vue` 定义 OKLCH tokens：暖橙 primary、暖白 background/surface、深棕灰 text、蓝 info、绿 success、红 danger，以及统一 border/shadow/focus。系统字体栈为 Apple/Segoe UI/Roboto；代码用 SFMono/Consolas。Arco 提供基础控件，业务页面大量 scoped CSS。

整体风格是暖色、克制的学术工作台：阅读器偏 IDE 三栏，项目页偏 workspace/dashboard，首页偏营销落地页。Token 有基础但 semantic status 色仍散落硬编码，页面 CSS 重复较多。

证据：`frontend/src/App.vue`、各 View scoped style。

## 28. Markdown / PDF / Editor Capabilities

- Markdown：markdown-it；开启常用 Markdown，链接/表格样式；DOMPurify 防 XSS。未发现 KaTeX/MathJax、footnote、syntax highlighter，因此公式与复杂学术引用只会按普通文本/Markdown 表现。
- PDF：PDF.js canvas 多页阅读、缩放、跳页、引用页与 bbox overlay、高亮；PDF byte/cache 辅助在 `pdfCache.ts`。
- 编辑：WritingStudio 使用原生 `contenteditable`，章节数组保存在 artifact `content`，同时派生 markdown（通过剥 HTML 标签）与 html。不是 TipTap/Lexical/Slate，缺少强 schema、协同编辑、可靠 Markdown round-trip 和引用节点模型。

## 29. Search Capabilities

- 本地论文列表：SQL title/authors 等搜索与状态过滤。
- 单论文全文：Chroma + BM25 + 结构化表格/图片通道。
- 项目跨论文：遍历 ProjectPaper，聚合并统一排序来源。
- 外部：arXiv Atom API 和 Semantic Scholar REST；前端 TopicExplorer 直接走项目 API，Agent 也可 Tool 调用。
- 未发现 Google Scholar、Crossref、OpenAlex、PubMed、通用 Web Search；未发现聊天全文检索或 Note 搜索产品入口。

## 30. External Integrations

| Provider | 调用位置 | 配置/认证 |
|---|---|---|
| DeepSeek | `llm/client.py` | `DEEPSEEK_API_KEY`, model/base URL |
| OpenAI-compatible | 同上 | `OPENAI_API_KEY`, model/base URL |
| DashScope/Qwen vision & embeddings | analyzers/knowledge_base | API key + vision/embedding/base URL |
| arXiv | `tools/external_literature.py`, remote import | 公共 HTTP，无 key |
| Semantic Scholar | 同上 | 公共接口；代码实现 retry/rate-limit 降级 |
| LangSmith | config/env | tracing flag/key/endpoint/project |
| Langfuse | config/env | public/secret key/host/project；依赖是否完整需运行确认 |

无对象存储、外部身份认证、Analytics/Sentry/Prometheus。

## 31. Configuration System

Pydantic Settings 加载顺序：进程环境覆盖 env file；env file 优先 `backend/.env`，否则项目根 `.env`；代码默认值兜底。Compose 显式注入容器环境，前端 Axios base URL 由 Vite/同源配置决定。

重要变量：`DATABASE_URL`、`REDIS_URL`、任务 TTL、`SECRET_KEY`、`DEFAULT_ADMIN_PASSWORD`、JWT 算法/过期、各 LLM/Embedding/Vision provider、timeout/retry、`VECTOR_STORE_PATH`、`FILE_STORAGE_PATH`、`MAX_UPLOAD_SIZE`、`CORS_ORIGINS`、LangSmith/Langfuse 变量。

风险：`config.py` 启动时打印配置路径/provider/base URL；不打印 key，但生产日志仍暴露部署信息。`.env.example` 与 Compose/Settings 应持续同步。

## 32. Background Task System

- Redis 自研队列 + 独立 `worker.py`，不是 Celery/RQ。
- job 有状态、attempt、最多 3 次 retry；Worker heartbeat 暴露在 `/health`。
- upload/chat/remote import/reading execution 使用队列或 Redis task；旧的 background task helper 仍存在。
- 回答可 stop；reading execution 支持 pause/resume；upload 没有用户 cancel/pause。
- 当前可支撑分钟级任务的基础（持久 Redis、独立 worker、重试、heartbeat）已存在，但没有通用 DAG、优先级、公平调度、租约续期、任务事件表、资源配额或多 worker 幂等证明。长达数十步 Research Task 仍属中等准备度。

## 33. Error Handling

- API 以 HTTPException 返回校验/权限/不存在/worker unavailable。
- 上传校验 PDF header/大小；解析空文本和异常有专用异常；重启可恢复。
- LLM client 有 timeout、有限 retry；外部 HTTP 有 retry/友好降级。
- Worker job 失败可重试并记录 raw error；前端流展示 stage/error 并可恢复。
- 跨 SQL/Chroma/files/Redis 无统一 transaction/compensation；异常处理散落于大型 Router/Agent，错误 taxonomy 不统一。
- 用户 stop 使用 Redis cancel flag，但 Tool/外部请求是否都在细粒度检查 cancel 未完全确认。

## 34. Observability

- Python logging + 请求/task/trace ID；LLM 记录耗时与 first-token。
- `AnswerTrace` 保存 total/retrieval/first token、token counts、model calls、retry、citations、second pass；管理员页面可查看工具调用与失败。
- Redis 保存实时 answer trace；LangSmith/Langfuse 通过环境配置可选。
- 有 dashboard 与 RAG evaluation 报告。
- 缺少统一 OpenTelemetry trace/span、Prometheus metrics、结构化日志规范与跨 DB/Redis/Tool 的自动传播。20 次 Tool Call 可从 AgentTrace 看到列表，但还不是完整分布式追踪。

## 35. Testing

后端使用 pytest/pytest-asyncio，覆盖上传校验、paper processing、parser、layout/table、hybrid/project retrieval、evidence review、QA workflow、agent routing、LLM client、Redis job/task、stream、权限安全、API contracts、项目/远程导入/写作导出和 eval metrics。`backend/evals` 提供 JSONL 数据集、retrieval/e2e runner、评分与 dashboard。

未发现前端 Vitest/Jest/Playwright/Cypress，也无 coverage 配置/百分比。多项 `verify_*.py` 是手工/在线冒烟脚本，不等同自动 CI。

## 36. CI/CD

仓库未发现 `.github/workflows`、GitLab CI 或 Jenkins 配置。构建/测试/部署主要依赖 shell scripts、Docker Compose 和人工执行。无自动 lint/test/build/image/deploy gate。

## 37. Deployment Architecture

```text
Browser
  ↓ HTTP(S)
public Nginx (deploy config, TLS/reverse proxy)
  ├→ frontend Nginx :80 (host :5173, Vue SPA)
  └→ FastAPI backend :8000
          ├→ PostgreSQL 15 volume
          ├→ Redis 7 AOF volume ← worker heartbeat/jobs/tasks/checkpoints
          ├→ Chroma + PDF/generated files (shared paperai_data volume)
          └→ external LLM/arXiv/Semantic Scholar
                 ↑
          Python worker (same image/shared data)
```

Compose healthchecks 覆盖 backend、worker、db、redis；frontend depends on backend。backend 与 worker 共享 `paperai_data`，满足本机 Compose 文件可见性，但横向扩展到多主机会受本地文件/Chroma 限制。

## 38. Code Quality & Technical Debt

- 巨型 Router/View：chat、papers、projects、PaperReader、ProjectWorkspace。
- 无 Repository；DB、AI、stream orchestration 在 API/Tool 中交叉。
- 两套问答范式（LangGraph QA 与 Harness Agent）及多个 summary/interpret endpoint，行为易漂移。
- Prompt 散落；Skill 文件化仅覆盖 Harness。
- SQL schema 用 `create_all`，无 migration。
- `ChatMessage` 把问答绑一行，不适合 Tool/assistant/system/event 多角色时间线。
- Chroma 单 collection、无 user/project/version namespace。
- Pinia 依赖未实际使用；前端状态与 CSS 局部重复。
- `Note/Folder/QAPair` 模型存在但产品面不完整。
- 旧文档已出现失效：`docs/API.md` 声称 paper status PATCH 不存在，但当前 `papers.py` 已实现。
- TODO 搜索未发现大量源码 TODO/FIXME；主要债务是结构性而非注释标记。
- 明显 dead-code 判断：旧 `backend/app/skills/my_skill` 正在工作树删除；不应恢复。部分旧 QA/summary API 是否仍由前端使用需在统一路径前做调用统计。

## 39. Reusable Assets

| 分类 | 资产 |
|---|---|
| 可以直接复用 | JWT 用户与 ownership 模式、PDF 文件校验/保存、PdfViewer/引用 bbox、高质量版面元素、LLM client、Redis queue 基础、Trace/eval、Docker healthchecks |
| 小规模修改可复用 | Paper/Section/Table 模型、混合检索、SmartChunker、SSE resume、ResearchProject/ProjectPaper、WritingArtifact、SkillRegistry、外部搜索 tools |
| 需要重构后复用 | Chat schema/context、Lead Agent runtime/checkpoint、项目 memory JSON、项目大型 tools 文件、PaperReader/ProjectWorkspace 状态、prompt 集合 |
| 建议未来替换 | `create_all` schema 演进、原生 contenteditable 文档模型、单 collection 无版本策略、散落的进程内 task cache/双重 task helper |

绝对不应轻易重写的核心是 PDF→物理元素→页框引用链、混合表格检索、现有评测数据与 trace、可恢复 SSE/Redis Worker、用户已有 Paper/Project 数据契约。

## 40. Candidate Agent Tools

当前已经不只是“候选”，多数已有 StructuredTool 包装：

| Tool/能力 | Existing implementation | Input → Output | Side effect / Reuse |
|---|---|---|---|
| get_paper_metadata | `tools/paper_internal.py` | paper_id → metadata JSON | read；高 |
| list_paper_sections | 同上 | paper_id → outline | read；高 |
| search_paper_content | 同上 | paper/query/intent → sources | read + LLM rerank 可能；高 |
| lookup/compute tables | 同上 | paper/table/question → rows/result | read；高 |
| export_citation_format | 同上 | paper/format → text | read；高 |
| reading progress/term | `reading_assistant.py` | paper/user/term → progress/evidence | read；中高 |
| search_arxiv/S2 | `external_literature.py` | query/title/field → candidates | external network；中高 |
| project_search_content | `literature_research.py` | project/query → cross-paper sources | read/LLM；高 |
| project add/remove/import | 同上 | project/paper/arxiv → relation/task | DB/network/file side effects；需权限/幂等强化 |
| project memory | 同上 | note/tag/source → memory | DB write；需 schema/version |
| paper card/research map/reading plan/evidence matrix | 同上 | structured Pydantic input → artifact/card | DB write；可复用，文件过大 |
| experiment/design/draft/audit/finalize | 同上 | structured research outputs → artifacts | 强副作用/质量门；需审计与权限 |
| delegate critique | `lead_agent.py` | question/evidence → review | SubAgent/LLM；中高 |

## 41. Candidate Agent Skills

| Skill | 当前实现步骤 | 性质 |
|---|---|---|
| paper_internal | 元数据/目录/正文/表格/引用导出 | 已文件化 Skill，动态工具选择 |
| reading_assistant | 进度聚合、术语定位、阅读规划 | 已文件化；部分规划靠 prompt |
| external_literature | 当前论文线索→arXiv/S2→筛选 | 已文件化；依赖外部服务 |
| literature_research | brief→搜索筛选→导入→精读→memory/artifact | 已文件化的大型复合 Skill |
| critique | 收集证据→委派 CritiqueSubAgent→评分/意见 | Agent 内特殊 tool 分支 |
| summarization/interpretation | 固定 LangGraph/Agent pipeline | 可成为 Skill，但目前路径独立 |
| manuscript lifecycle | blueprint→section draft→assemble→reference→audit→finalize | tools+Skill 已描述，质量/人工批准边界仍需验证 |

## 42. Memory Readiness

区分现有状态：

- 短期执行状态：Redis answer task、Agent checkpoint、LangGraph state。
- 聊天历史：SQL ChatSession/ChatMessage，最近 5 组拼 prompt。
- 论文知识：SQL elements/sections + Chroma chunks。
- 长期项目状态：`ResearchProject.memory = {summary, notes[]}`。
- 用户偏好：User.preferences 与 Project.preferences。

准备度为 Medium：已有长期可写 memory 与来源字段使用规范，但 JSON 单字段缺少 note ID、独立索引、版本、权限/审计、冲突处理、semantic retrieval 与容量治理；聊天也没有自动总结/遗忘策略。

## 43. Research Project Readiness

已确认一级 `ResearchProject`；Paper 通过 ProjectPaper 多对多加入多个项目；Conversation 可属于 Project；项目拥有 memory、preferences、artifacts；ProjectPaper 保存语境化 card/plan/role。这已经能映射 Project/Paper/Memory/Document 的大部骨架。

缺口：Evidence/Citation/Task/ResearchNote/Topic 没有独立表；多种研究产物塞入多态 JSON；project phase 主要是字段而非强状态机；项目删除/归档、产物版本链和 Agent execution lineage 较弱。

## 44. Frontend Expansion Readiness

Router 与 Project Workspace 已容纳 Topic、Reading、Writing、Memory、Artifacts、Chat；PdfViewer、header、项目组件可复用，基础视觉 tokens 一致。准备度 Medium。

约束：工作区和阅读器体积过大；没有共享 task/activity store；写作编辑器数据模型脆弱；Agent tool activity 主要在 Admin Trace 而非用户任务面板；移动端三栏已有适配但更复杂 Workspace 未全面验证。

## 45. Backward Compatibility Requirements

1. 现有 `papers.id/pdf_path` 与 PDF URL 必须保持可读取。
2. Chroma `papers` collection 的 embedding 模型/维度和 paper filter 迁移必须显式处理。
3. 已有 sections/elements/table bbox 引用必须继续能定位 PDF。
4. ChatSession/ChatMessage、summary/interpret cache 与 citations JSON 必须可打开。
5. 保留 `/library`、`/paper/:id` 和主要 `/api/v1/*` 契约，或提供兼容层。
6. ResearchProject/ProjectPaper/WritingArtifact 当前虽未提交，但若已有测试/用户数据，需按正式数据对待。
7. Redis task 允许过期，但部署重启期间正在运行的 upload/chat/import 需有明确恢复语义。
8. 数据库新增/改列必须从 `create_all` 迁移到可回滚 migration，不能假定空库。
9. PDF/Chroma/SQL 的删除顺序与已有 volume 路径不能静默改变。
10. Markdown 与 artifact content/html 三种表示需定义兼容主源。

## 46. Agent Upgrade Constraints

- 一次请求已不等于一次 LLM，但 task schema 仍面向单个 answer/reading execution。
- ChatMessage 无法原生表达 tool/action/observation/approval/subagent/event。
- Lead Agent checkpoint 在 Redis，缺少永久 execution/event store。
- Tool 权限主要靠注入上下文和实现自检，缺少统一 permission/policy/confirmation 层。
- 多论文检索基于逐 paper 归并，规模上升后成本与 latency 线性增长。
- Memory 单 JSON 会产生并发写、增长、检索和审计约束。
- Prompt/Skill/tool version 未进入 trace，难以重放。
- 本地文件与 Chroma 限制多节点部署。
- SSE 可恢复但前端状态只在页面局部，跨路由任务可见性有限。
- fixed workflow 与 ReAct runtime 并存，状态/引用/错误协议尚未统一。

## 47. Agent Upgrade Risks

1. 未提交的大规模 Agent/Project 代码与已发布基线边界不清。
2. 无 schema migration，新增 project/chat 列可能在已有库失效。
3. Chat 数据模型不能表达 Agent 事件流。
4. Lead Agent 与旧 QA pipeline 双轨漂移。
5. `literature_research.py` 聚集大量读写工具与领域规则。
6. Tool side effect 缺统一授权、人工确认和幂等键。
7. Project memory JSON 并发覆盖、无限增长、不可索引。
8. Evidence 不是一级持久实体，写作引用 lineage 易断。
9. Chroma 无 user/project/embedding-version namespace。
10. SQL/Chroma/files/Redis 无原子生命周期。
11. 多论文逐篇检索在大项目中延迟/费用放大。
12. 长任务只有自研队列，缺少 DAG/资源与租约治理。
13. 本地持久 volume 阻碍横向扩容和灾备。
14. 大型 Vue View 和局部状态难承载并行 Agent tasks。
15. contenteditable + HTML/Markdown/JSON 三源可能数据漂移。
16. Prompt/Skill 无版本与评测绑定，回归难定位。
17. 外部搜索 API 限流/元数据质量会污染项目资产。
18. 模型默认/embedding provider 命名存在配置误配风险。
19. 前端无自动测试，复杂流/引用/恢复易回归。
20. 可观测性尚非统一 span，SubAgent/Tool 深链难完整归因。

## 48. Architecture Diagrams

### 图 1：当前整体架构

```text
Vue SPA ──Axios/SSE──> FastAPI Routers ──SQLAlchemy──> PostgreSQL
  │                         │                    
  │ PDF.js                  ├── Redis jobs/tasks/checkpoints <── Worker
  │                         │                         │
  └─ local state            ├── Services/RAG          ├── LangGraph workflows
                            │     └── Chroma           └── Harness Lead Agent
                            │                              ├── Skills/Tools
                            ├── local PDF/media files      └── Critique SubAgent
                            └── LLM / arXiv / Semantic Scholar
```

### 图 2：论文数据流

```text
PDF → validate/hash/store → Redis paper_process
    → text extract → LLM parser + PyMuPDF layout
    → Paper/Section/DocumentElement
    → parent-child chunks + page/bbox metadata
    → batch embedding → Chroma(papers)
    → table/image/formula enhancement → ready
```

### 图 3：AI 问答调用链

```text
PaperReader/ProjectChat → create/resume SSE task → Redis queue → Worker
 → route(direct/workflow/agent)
 → history + paper/project context
 → Lead Agent [LLM → Tool → observation]xN
      Tool → hybrid/vector/table/project/external retrieval or DB write
 → citations/evidence/confidence → Redis deltas → SSE UI
 → ChatMessage + AnswerTrace
```

### 图 4：数据库核心关系

```text
User 1──N Paper 1──N Section 1──N DocumentElement
 │          ├──N Table ──1 TableStructure ──N TableCell
 │          ├──N Image
 │          └──N Summary/Interpret cache
 ├──N ChatSession 1──N ChatMessage
 │       ├──0..1 Paper
 │       └──0..1 ResearchProject
 └──N ResearchProject 1──N WritingArtifact
              │
              N──ProjectPaper──N Paper
```

### 图 5：前端页面关系

```text
Home/Login/Register
       ↓
Projects list ─→ ProjectWorkspace ─→ ProjectChat
                      ├─ TopicExplorer
                      ├─ paper library/cards/memory/artifacts
                      └─ WritingStudio
Library ─→ PaperReader
             ├─ PaperOutline
             ├─ PdfViewer
             └─ QA/Summary/Interpret
Admin ─→ Dashboard / Traces / Users
```

## 49. Agent Readiness Matrix

| 维度 | 评级 | 证据/理由 |
|---|---|---|
| 模块化 | Medium | Services/RAG/Harness 已拆；Router/View/Tool 文件仍巨大 |
| LLM abstraction | Good | 单 client 支持 provider、stream、JSON、retry、tools |
| RAG abstraction | Good | KB + hybrid + table + evidence review，多论文可组合 |
| Tool readiness | Good | StructuredTool、Pydantic input、SkillRegistry 已运行 |
| Memory readiness | Medium | project JSON memory + chat/knowledge 分层已有，缺独立模型 |
| State management | Medium | LangGraph state/Redis task/checkpoint；协议未统一 |
| Async task | Medium | 独立 Redis worker/retry/heartbeat；无通用 durable DAG |
| Streaming | Good | Redis-backed resumable SSE、reasoning/answer offset、stop |
| Persistence | Medium | SQL/Redis/Chroma/files 齐全；跨存储一致性和 migration 弱 |
| Observability | Medium | AnswerTrace/admin/evals/可选 tracing；无全链 span |
| Testing | Medium | 后端与 RAG eval 广；前端/E2E/CI 缺失 |
| Frontend extensibility | Medium | Workspace 已成形；大 View、局部状态、弱 editor |
| Database extensibility | Weak | 模型丰富，但无 Alembic、JSON 多态字段较重 |

## 50. Key Decisions Required for Next Architecture Phase

1. 以现有 Harness 为统一 Runtime，还是保留 LangGraph QA 与 Agent 双轨？
2. Agent execution/task/event/tool call 是否成为持久 SQL 一级实体？
3. Chat 是否迁移为通用 role/content/event 模型，如何兼容旧 QA 行？
4. ResearchProject 的 phase 是否成为可验证状态机？Conversation 是否必须归属 Project？
5. Paper 多项目共享时，哪些分析是全局资产，哪些属于项目语境？
6. Evidence/Citation 是否一级实体，如何绑定 paper/chunk/element/bbox/artifact revision？
7. Memory 拆为 note/fact/decision/preference/task 哪些类型，如何检索、压缩、引用与遗忘？
8. Chroma 是否继续使用，如何做 user/project filter、embedding version 与重索引？
9. Tool 的 read/write/network/destructive 权限、用户确认、幂等和审计如何定义？
10. Skill/prompt/tool 如何版本化并与 eval/trace 绑定？
11. 长任务继续自研 Redis worker，还是引入更耐久的工作流执行器？
12. Pause/resume/cancel 的语义是在步骤边界还是任意 tool 内？
13. SubAgent 是否共享 memory/context，如何限制预算和循环？
14. Writing Document 的权威格式是结构化 JSON、Markdown 还是编辑器 schema？
15. 是否引入对象存储/托管向量库以支持多节点？
16. 如何为现有数据库正式建立 baseline migration 而不破坏数据？
17. 前端是否建立统一 task/activity/server-state store？
18. 外部文献的元数据可信度、去重、版权与导入许可如何治理？

## 51. Unknowns / Information Not Available

- 未读取生产 `.env` 值，也未输出任何 secret；真实 provider/model 选择未确认。
- 未连接生产 PostgreSQL/Redis/Chroma，数据量、旧 schema 和索引内容未知。
- 未运行在线 LLM、embedding、arXiv/S2 端到端调用。
- 未进行浏览器视觉/E2E、性能、并发、断线恢复实测。
- 未确认外部消费者是否依赖当前 API。
- 未确认 Langfuse 在当前 requirements 下是否实际安装/启用。
- OCR/扫描 PDF：未发现 OCR 引擎，故扫描件支持应视为 **未实现/未确认**；Vision 分析不能等同 OCR pipeline。
- 公式仅作为文本/Section JSON 提取；未确认 LaTeX 结构保真。
- CI/CD 与生产备份/灾难恢复信息不在仓库中。

## 52. Important File Index

| Category | File | Why Important |
|---|---|---|
| Backend entry | `backend/app/main.py` | 生命周期、Router、模型注册、health |
| Configuration | `backend/app/config.py` | provider、存储、安全、tracing 配置 |
| Database | `backend/app/database.py` | Async SQLAlchemy 与 create_all |
| Worker/queue | `backend/app/worker.py`, `backend/app/job_queue.py` | 长任务执行、重试、heartbeat |
| Paper API | `backend/app/api/papers.py` | 上传、处理、PDF、删除完整入口 |
| Chat API | `backend/app/api/chat.py` | session、Redis answer task、SSE/恢复/停止 |
| Project API | `backend/app/api/projects.py` | 项目、memory、artifacts、reading execution |
| Auth | `backend/app/api/auth.py`, `api/dependencies.py` | JWT、用户与管理员边界 |
| Core models | `backend/app/models/paper.py` | 论文/物理元素/表格/笔记数据结构 |
| Chat models | `backend/app/models/chat.py` | 对话、cache、Trace 契约 |
| Project models | `backend/app/models/project.py` | Project/Paper relation/artifact/memory |
| Upload boundary | `backend/app/services/paper_upload.py` | 文件校验、保存、hash、文本提取 |
| Processing | `backend/app/services/paper_core_processing.py` | parser→SQL→index 主流水线 |
| Chunk/index | `backend/app/services/paper_indexing.py` | section/page/front matter chunk 组织 |
| Vector KB | `backend/app/rag/knowledge_base.py` | SmartChunker、embedding、Chroma collection |
| Hybrid RAG | `backend/app/rag/hybrid_retrieval.py` | query plan、BM25、多通道、rerank |
| Table RAG | `backend/app/rag/table_retrieval.py` | 精确表格证据 |
| Evidence | `backend/app/rag/evidence_review.py` | 引用/支持度检查 |
| LLM adapter | `backend/app/llm/client.py` | generate/stream/retry/tool binding |
| QA workflow | `backend/app/agent/qa_agent/workflow.py` | 旧/固定 QA graph 主链 |
| Agent runtime | `backend/app/harness/agents/lead_agent.py` | ReAct loop、checkpoint、project context、trace |
| Routing | `backend/app/harness/agents/routing.py` | direct/workflow/agent 决策 |
| Tool registry | `backend/app/harness/skills/registry.py` | Skill→prompt/tools 装配 |
| Project tools | `backend/app/harness/tools/literature_research.py` | 跨论文、memory、研究/写作副作用 |
| Paper tools | `backend/app/harness/tools/paper_internal.py` | 单论文可复用 Tool contract |
| External tools | `backend/app/harness/tools/external_literature.py` | arXiv/Semantic Scholar 边界 |
| Front router | `frontend/src/router/index.ts` | 全部页面与权限 guard |
| API client | `frontend/src/api/index.ts`, `api/paper.ts`, `api/projects.ts` | token、REST、SSE contracts |
| Reader | `frontend/src/views/PaperReader.vue` | 当前核心阅读/问答 UX 与状态 |
| PDF | `frontend/src/components/PdfViewer.vue` | 页渲染、缩放、bbox citation |
| Project UI | `frontend/src/views/ProjectWorkspace.vue` | Research Workspace 聚合入口 |
| Writing | `frontend/src/components/project/WritingStudio.vue` | 当前 editor/artifact 数据契约 |
| Markdown | `frontend/src/utils/markdown.ts` | AI/产物安全渲染能力 |
| Design tokens | `frontend/src/App.vue` | 全局颜色、字体、focus、surface |
| Deploy | `docker-compose.yml`, `frontend/nginx.conf`, `deploy/nginx/paper.dongli.icu.conf` | 服务、volume、SSE proxy、生产入口 |
| Tests/evals | `backend/tests/`, `backend/evals/` | 回归边界与 RAG 质量基线 |

---

结论：后续设计不应按“给传统论文 QA 外挂一个 Agent”理解本项目。当前工作区已经具备 Project、Tool、Skill、ReAct、SubAgent、memory 和 writing artifact 的原型；真正需要设计的是如何把这些原型收敛为可迁移、可审计、可持久执行、可扩展且不破坏现有论文阅读资产的统一产品架构。
