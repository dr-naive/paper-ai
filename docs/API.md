# API

> 状态：ACTIVE / CURRENT-CONTRACT-ONLY
>
> 本文档只记录当前代码中已经存在并完成验证的 API。
> `docs/spec-v2/` 中出现的未来 endpoint、DTO 或 route 只是施工目标，在对应实现与测试完成前不得提前写入本文。
>
> 每个实施 Phase 如果新增、删除或修改真实 API，必须在同一 Phase 更新本文和
> `docs/spec-v2/execution/IMPLEMENTATION_PROGRESS.md`。

本文档记录当前后端主要 API 路径，以及前端 API 客户端的调用关系。以后修改接口时，先同步这里，避免前后端路径漂移。

## 认证

Router：`backend/app/api/auth.py`

前缀：`/api/auth`

| Method | Path | 用途 | 前端调用 |
| --- | --- | --- | --- |
| POST | `/api/auth/login` | 登录并返回 access token | `frontend/src/api/auth.ts` |
| POST | `/api/auth/register` | 注册用户 | `frontend/src/api/auth.ts` |
| GET | `/api/auth/users/me` | 获取当前用户及角色 | `frontend/src/api/auth.ts` |
| GET | `/api/auth/admin/users` | 管理员获取用户列表 | `frontend/src/api/auth.ts` |
| PATCH | `/api/auth/admin/users/{user_id}` | 管理员更新角色或启用状态 | `frontend/src/api/auth.ts` |

认证方式：

```text
Authorization: Bearer <access_token>
```

角色目前分为 `admin` 和 `user`。管理员接口只允许 `admin` 角色访问。
系统每次启动都会确保固定的 `admin` 管理员存在并处于启用状态；密码由 `DEFAULT_ADMIN_PASSWORD` 环境变量提供。

兼容性说明：如前端仍调用 `/api/auth/logout` 而后端没有对应路由，应在 `docs/TODO_OR_RISKS.md` 中以当前代码重新验证后记录；本文件只保留已经确认的接口事实。

## 管理员观测

Router：`backend/app/api/admin.py`

| Method | Path | 用途 |
| --- | --- | --- |
| GET | `/api/admin/dashboard` | 系统健康、使用量、AI Trace、七日趋势和最新评测汇总 |

该接口仅允许 `admin` 角色访问。AI Token 来自回答 Trace 的估算值，
用于观察趋势，不代表模型供应商账单；部署本版本后产生的回答会持久化统计。

## 论文

Router：`backend/app/api/papers.py`

前缀：`/api/v1/papers`

| Method | Path | 用途 |
| --- | --- | --- |
| GET | `/api/v1/papers/` | 获取论文列表，支持分页、状态、搜索；同时返回当前用户尚未生成 Paper 记录的 `import_tasks` |
| POST | `/api/v1/papers/upload` | 上传 PDF 论文 |
| GET | `/api/v1/papers/tasks/{task_id}` | 获取后台处理任务状态 |
| POST | `/api/v1/papers/tasks/{task_id}/retry` | 重试当前用户失败的导入任务，或仅重试已可用论文失败的图表增强阶段 |
| GET | `/api/v1/papers/{paper_id}` | 获取论文详情 |
| GET | `/api/v1/papers/{paper_id}/pdf` | 获取论文 PDF 文件 |
| POST | `/api/v1/papers/{paper_id}/pdf/telemetry` | 上报本次 PDF 阅读首屏加载耗时（仅写日志，不持久化） |
| GET | `/api/v1/papers/{paper_id}/sections` | 获取论文章节 |
| GET | `/api/v1/papers/{paper_id}/elements` | 获取可定位的正文/媒体元素 |
| POST | `/api/v1/papers/{paper_id}/sections/rebuild` | 按当前解析结果重建章节 |
| PATCH | `/api/v1/papers/{paper_id}/status` | 更新论文处理状态（受保护的内部任务契约） |
| DELETE | `/api/v1/papers/{paper_id}` | 删除论文 |
| POST | `/api/v1/papers/{paper_id}/qa` | 针对论文提问 |
| POST | `/api/v1/papers/{paper_id}/interpret` | 论文解读 |
| POST | `/api/v1/papers/{paper_id}/summarize` | 生成结构化摘要 |
| GET | `/api/v1/papers/{paper_id}/summary` | 获取结构化摘要 |

前端主要调用文件：`frontend/src/api/paper.ts`

阅读状态相关接口若在前后端存在契约差异，应以当前分支重新验证后记录到 `docs/TODO_OR_RISKS.md`；不要把未重新验证的历史风险继续固化在 API Contract 中。

## Research Projects

Router：`backend/app/api/projects.py`

前缀：`/api/v1/projects`

所有接口要求 Bearer token，并按当前用户校验 Project 所有权；不存在和无权访问统一返回 `404`，避免泄漏 Project 是否存在。

| Method | Path | 用途 |
| --- | --- | --- |
| GET | `/api/v1/projects` | 分页列出当前用户的 Projects，支持 `status` 与 `q` |
| POST | `/api/v1/projects` | 创建 Project |
| GET | `/api/v1/projects/{project_id}` | 获取 Project metadata 与论文/产物计数 |
| PATCH | `/api/v1/projects/{project_id}` | 部分更新 Project metadata |
| DELETE | `/api/v1/projects/{project_id}` | 删除当前用户的 Project |
| GET | `/api/v1/projects/{project_id}/papers` | 列出正式加入 Project 的论文，可按 `role` 筛选 |
| POST | `/api/v1/projects/{project_id}/papers` | 将当前用户拥有的论文加入 Project；重复加入时更新关系 metadata |
| PATCH | `/api/v1/projects/{project_id}/papers/{paper_id}` | 更新 Project Paper 关系 metadata |
| DELETE | `/api/v1/projects/{project_id}/papers/{paper_id}` | 从 Project 移除论文关系 |
| GET | `/api/v1/projects/{project_id}/papers/{paper_id}/profile` | 获取项目语境下的版本化 Paper Profile |
| POST | `/api/v1/projects/{project_id}/papers/{paper_id}/profile/regenerate` | 异步重试或重新生成 Paper Profile |

创建 Project 必须提供：

```json
{
  "title": "项目名称",
  "research_topic": "研究主题"
}
```

创建与更新可提供结构化 `research_scope`：

```json
{
  "field": "学科领域",
  "research_subject": "研究对象",
  "research_question": "研究问题",
  "research_goal": "研究目标",
  "keywords": ["关键词"],
  "method_direction": "方法或技术方向",
  "notes": "补充说明"
}
```

Project list/detail/create/update 响应均返回完整 `research_scope` shape。该字段兼容存储在现有 `preferences.research_scope` JSON 中，因此没有新增数据库列；原有 `abstract`、`phase`、`status`、`preferences` 等字段保持兼容。

Paper Profile 复用 `ProjectPaper.analysis_card.paper_profile`，状态为 `pending / generating / ready / failed / stale`，并返回 `profile_version`、`generator_version`、`source_model`、`source_fingerprint` 和生成时间。只有已加入 Project 且完成解析的论文会进入现有 Worker 队列；生成失败仅更新 Profile 状态，不影响 Reader、Project Papers 或原有 QA。手动重试接口返回 `202`，未完成解析返回 `409`，Worker 队列不可用返回 `503`。

启用 `ENABLE_MEMORY_V2` 时，项目级 Research Notes / Evidence 路由还提供：

| Method | Path | 用途 |
| --- | --- | --- |
| GET | `/api/v1/projects/{project_id}/notes` | 读取项目笔记（可选包含旧 JSON notes） |
| POST | `/api/v1/projects/{project_id}/notes` | 创建结构化项目笔记 |
| PATCH | `/api/v1/projects/{project_id}/notes/{note_id}` | 更新结构化项目笔记 |
| DELETE | `/api/v1/projects/{project_id}/notes/{note_id}` | 删除结构化项目笔记 |
| GET | `/api/v1/projects/{project_id}/evidence` | 读取项目证据 |
| POST | `/api/v1/projects/{project_id}/evidence` | 创建已加入项目文档库论文的证据 |
| DELETE | `/api/v1/projects/{project_id}/evidence/{evidence_id}` | 删除项目证据 |
| GET | `/api/v1/evidence/{evidence_id}` | 获取仍属于当前用户项目的单条证据 |

除既有研究笔记类型外，V1 typed Literature Memory 使用 `project_decision`、`literature_intent`、`literature_preference` 和 `literature_exclusion`。这些类型只会在 Context Manager 的相应用例中读取；普通聊天、原始 provider 响应和 raw reasoning 不会自动进入长期上下文。旧 `/memory` JSON 读写端点保持兼容，但不作为新的 Discovery Context 来源。

Writing Context 的内部服务链为 `Project Profile → ready/stale Paper Profiles → 最多 5 篇候选论文 → 候选范围内 Hybrid Retrieval → EvidenceCandidate`。候选论文和检索结果均由服务端按 Project 所有权与 `ProjectPaper` 关系限定，客户端或模型提供的论文 ID 不会绕过该范围。没有正式导入论文、没有可用 Profile、或没有支持证据时分别返回 typed status，不会从 Discover-only metadata、普通聊天或模型记忆补造引用。

Evidence 创建仍复用既有 `EvidenceItem`。`POST /evidence` 现在要求 section / document element 等来源定位可在目标论文内验证；无法验证的 chunk 返回 `422`。读取有效 Evidence 时还会校验论文仍属于当前 Project，因此已移出 Project 的论文证据不会继续作为当前写作来源。

`EvidenceItem` 现在持久化 `source_type`、`status`、`source_fingerprint`、`verification_status/reason/model/version` 与 `updated_at`。`status` 为 `active / stale / invalid`。确定性完整性和 lexical gate 通过后仍是 `unverified`；只有语义 verifier 直接确认支持后才更新为 `verified`，其余为 `weak / unsupported`。

`POST /api/v1/documents/{document_id}/citation-audit` 复用现有 Citation Node，并通过 `CitationVerificationService` 依次执行 Project/Paper/Evidence 完整性、source locator/fingerprint、lexical gate 和结构化语义支持验证。响应保留 `issues/passed`，并返回结构化 `citation_results`：每项包含 `status`（`verified / weak / unsupported`）、`code`、`reason`、`confidence`、原始/调整后 claim 和 Evidence snippet。`weak` 产生 warning，`unsupported` 产生 error；超时、无效响应、鉴权失败和限流均不会标记为 verified。

语义 verifier 复用既有 `LLMClient` 和已配置模型，只接收当前 claim、单条 Evidence 及必要论文 metadata。`CITATION_VERIFIER_TIMEOUT_SECONDS` 默认 30 秒，允许范围 1–120 秒。Application service 可为后续生成 workflow 启用最多一次保守 claim adjustment + re-verification；citation audit 不会静默修改现有文档内容。

正式写作文档继续使用既有 `/api/v1/projects/{project_id}/documents`、`/api/v1/documents/{document_id}` 与 append-only revision endpoints。旧 `POST /api/v1/documents/{document_id}/ai-actions` 保持兼容。

`POST /api/v1/projects/{project_id}/writing/agent/rewrite` 提供 V1 selection rewrite proposal。请求包含 `document_id`、自由 `instruction`、带结构化 citation placeholder 的 `selected_text`、selection range、`section_path`、可选 `nearby_text/base_revision_id/citations`。服务端重新校验 Project/Document ownership；若 base revision 已变化则返回 `409 WRITING_DOCUMENT_CONFLICT`。响应只返回 `ready / partially_verified / verification_failed` proposal，不修改正文或创建 revision；用户显式接受后仍通过现有 editor transaction 与 revision endpoint 保存。

Citation-aware rewrite 使用 `[[CITATION:<citation_key>]]` 作为内部不可变 placeholder，并要求 `citation_keys` 与输入 mapping 数量、顺序完全一致。返回内容保留原 `paper_id/evidence_id`，随后调用既有 `CitationVerificationService`；模型结构无效时只进行一次 repair，仍失败返回 `503 WRITING_REWRITE_ERROR`。Rewrite 不自动生成新 Evidence。

`POST /api/v1/projects/{project_id}/writing/agent/generate` 提供 V1 单段 Evidence-backed generation。请求包含 `document_id`、自由 `instruction`、`section_path`、可选 `nearby_text/base_revision_id` 和 `citation_style`（`gbt7714 / apa / ieee`）。服务端固定执行现有 `ProjectContextManager → CandidatePaperSelector → ProjectEvidenceRetrievalService → EvidenceService → CitationVerificationService` 路径，只允许当前 Project 中已导入、已有可用 Paper Profile 且能通过既有 Hybrid Retrieval 取得来源定位的论文。

模型只能从服务端提供的临时 `E1…En` Evidence 键中选择，并返回一个段落、结构化 `citation_key/evidence_key/claim_text` 以及正文 placeholder；服务端验证 claim 确实来自正文后，重新校验 Evidence 来源、持久化实际使用的 Evidence，再解析为真实 `paper_id/evidence_id` 并强制验证。响应是 `ready / partially_verified / verification_failed` proposal，不修改正文。`unsupported` citation 保持显式 warning，绝不标记为 verified。失败码包括 `NO_IMPORTED_PAPERS`、`NO_RELEVANT_PAPERS`、`NO_SUPPORTING_EVIDENCE`、`GENERATION_ERROR`、`VERIFICATION_ERROR` 和既有 `WRITING_DOCUMENT_CONFLICT`；模型结构失败只 repair 一次。

段落草案在 Evidence 持久化前经过 bounded Writing Reviewer。Reviewer 只返回
`pass / repair`、受限 issue codes 和修复指令，不返回推理过程；`repair` 最多触发一次额外
生成，修复结果必须重新满足单段、Evidence key、claim 和 citation placeholder Schema，失败
即返回 `503 WRITING_REVIEW_ERROR`。proposal 的 `review` 字段记录 `passed / repaired`、
issue codes 和 `repair_count: 0 | 1`。

前端调用文件：`frontend/src/api/projects.ts`。Project 页面 canonical routes 为：

```text
/projects/:projectId/overview
/projects/:projectId/discover
/projects/:projectId/papers
/projects/:projectId/writing
```

旧 `/project/:id` 链接重定向到 Overview；独立 `/paper/:id` Reader route 保持不变。

## 聊天会话

Router：`backend/app/api/chat.py`

前缀：`/api/v1/chat`

| Method | Path | 用途 |
| --- | --- | --- |
| GET | `/api/v1/chat/sessions` | 获取会话列表 |
| POST | `/api/v1/chat/sessions` | 创建会话 |
| DELETE | `/api/v1/chat/sessions/{session_id}` | 删除会话 |
| GET | `/api/v1/chat/sessions/{session_id}/messages` | 获取会话消息 |
| POST | `/api/v1/chat/sessions/{session_id}/ask` | 在会话中提问 |
| GET | `/api/v1/chat/papers/{paper_id}/summary` | 获取摘要缓存 |
| POST | `/api/v1/chat/papers/{paper_id}/summarize` | 生成摘要并缓存 |
| GET | `/api/v1/chat/papers/{paper_id}/interpret/{interpret_type}` | 获取解读缓存 |
| POST | `/api/v1/chat/papers/{paper_id}/interpret/{interpret_type}` | 生成解读并缓存 |

前端主要调用文件：`frontend/src/api/paper.ts`

## Writing Documents 与 Citation Verification

Router：`backend/app/api/documents.py`。接口受 `ENABLE_WRITING_V2` feature flag 保护，所有
文档按 Project 所有权校验；revision 是 append-only。

| Method | Path | 用途 |
| --- | --- | --- |
| GET | `/api/v1/projects/{project_id}/documents` | 列出项目写作文档 |
| POST | `/api/v1/projects/{project_id}/documents` | 创建文档及初始 revision |
| GET | `/api/v1/documents/{document_id}` | 获取文档与当前 revision |
| PATCH | `/api/v1/documents/{document_id}` | 更新标题或文档状态 |
| GET | `/api/v1/documents/{document_id}/revisions` | 列出 append-only revisions |
| POST | `/api/v1/documents/{document_id}/revisions` | 创建新 revision |
| POST | `/api/v1/documents/{document_id}/ai-actions` | 旧兼容 proposal 接口，不直接改正文 |
| POST | `/api/v1/documents/{document_id}/citation-audit` | 执行完整性、lexical 与语义 Citation Verification |
| POST | `/api/v1/projects/{project_id}/writing/agent/rewrite` | 返回选中文本 rewrite proposal |
| POST | `/api/v1/projects/{project_id}/writing/agent/generate` | 返回单段 evidence-backed proposal |

Writing Agent 的两个 V1 endpoint 都只返回 proposal；用户明确 Replace/Copy 后才由编辑器提交
revision。`verified`、`weak`、`unsupported` 等 Citation 状态保持结构化，不从正文标记推断。

## Agent Execution / SSE

Router：`backend/app/api/executions.py`。接口受 `ENABLE_AGENT_RUNTIME_V2` 保护，所有执行按用户
和 Project 所有权校验；事件可通过分页接口重放，也可通过 SSE 持续读取。

创建契约同时兼容既有 `agent_type: "writing_generate"` 和 Goal-driven
`agent_type: "research_goal"`。前者继续直接进入既有 Writing WorkerJob；后者将用户目标
持久化为同一张 `AgentExecution`（语义别名为 ResearchExecution/GoalExecution），生成持久化
Execution Plan 与 `ResearchTask` 图，再通过现有 Redis Queue/Worker 执行。公开事件仅包含阶段、
计数和状态，不包含 prompt、模型原始响应或推理过程。

`research_goal` 的 `input.goal_type` 目前为 `READ_PAPERS`、`WRITE_SECTION` 或
`DISCOVER_AND_IMPORT`。规划按“目标所需能力 - 可复用 Project 资产 + 缺失 Hard Dependency”
裁剪；`ResearchTask` 是可恢复的业务步骤，`WorkerJob` 只是队列载体。任务结果统一返回
`task_id/status/output_refs/completion/metrics/error`，产物引用使用结构化的
`artifact_type/artifact_id/project_id/source_task_id`。

三类目标的用户可见进度分别映射为“精读项目论文”“整理可用论文证据”“生成章节草稿”“检查引用可靠性”等
ProgressStep。论文列表确认使用 `POST /api/v1/executions/{execution_id}/respond` 恢复同一执行，
不会创建新的执行链。

`writing_generate` durable execution 会激活版本化
`writing_evidence_generation` Skill，并持久化 `skill_activated`、Reviewer、一次有限修复和
`skill_completion_evaluated` 事件。最终 `result_payload` 同时包含 `proposal`、
`skill_completion` 与 `completion`；Skill completion 未通过时 Completion Gate 必须失败，执行
不能进入 `completed`。

| Method | Path | 用途 |
| --- | --- | --- |
| POST | `/api/v1/projects/{project_id}/executions` | 创建执行并排队（202） |
| GET | `/api/v1/projects/{project_id}/executions` | 列出项目执行 |
| GET | `/api/v1/executions` | 列出当前用户执行 |
| GET | `/api/v1/executions/{execution_id}` | 获取执行状态 |
| GET | `/api/v1/executions/{execution_id}/events` | 分页读取事件 |
| GET | `/api/v1/executions/{execution_id}/trace` | 返回隐私安全的结构化执行链路报告 |
| GET | `/api/v1/executions/{execution_id}/evaluation` | 返回确定性的执行质量评分与命名检查 |
| GET | `/api/v1/executions/{execution_id}/stream` | SSE 读取事件并支持断点 `after` |
| POST | `/api/v1/executions/{execution_id}/cancel` | 取消执行 |
| POST | `/api/v1/executions/{execution_id}/pause` | 暂停执行 |
| POST | `/api/v1/executions/{execution_id}/resume` | 恢复执行 |
| POST | `/api/v1/executions/{execution_id}/approve` | 通过等待用户审批的执行 |
| POST | `/api/v1/executions/{execution_id}/respond` | 提交等待中的论文选择并恢复同一 Goal Execution |

Trace 报告由 PostgreSQL 中的 `AgentExecution + AgentEvent` 确定性投影，包含有序 stage
span、耗时、暂停/恢复/取消转换、预算使用和 Completion Gate 质量摘要。报告只保留文档 ID、
章节深度、是否存在邻近上下文等输入元数据，不返回 instruction、nearby text、prompt、模型
原始输出、provider payload 或 chain-of-thought。

Evaluation 使用版本化的确定性 rubric，检查终态、Completion Gate、Citation 支持、trace
完整性、预算与耗时完整性。它不调用 LLM：完整 verified 结果可通过；weak 结果扣分但仍可通过；
unsupported、Completion Gate 失败或结构异常不能通过；暂停、取消和未结束执行标记为
`incomplete`。响应包含总分以及每项检查的 `earned/maximum/detail`，便于测试和面试演示。

## 路由兼容与未挂载接口

顶层 `/api/v1/notes` 没有挂载；笔记只通过启用 `ENABLE_MEMORY_V2` 后的项目作用域
`/api/v1/projects/{project_id}/notes` 提供。旧 `/project/:id` 和 `/project/:id/chat` 是前端
路由兼容重定向，不是后端 Project Chat API；canonical Project 页面只使用 Overview、Discover、
Papers、Writing。

旧 Project artifact、memory、reading-execution 和 `/external-papers/*` 路由仍可能被旧脚本或
兼容客户端调用，但不属于 V1 主导航，也不应作为新的用户入口扩展。

## Literature Discovery API

前缀：`/api/v1/projects/{project_id}/discovery`。所有接口要求 Bearer token，并校验项目归属。

| Method | Path | 用途 |
| --- | --- | --- |
| POST | `/api/v1/projects/{project_id}/discovery/search` | 执行一次最多三轮的有界学术检索 |
| GET | `/api/v1/projects/{project_id}/discovery/executions/{execution_id}` | 获取 Redis 中的检索阶段与结果快照 |
| POST | `/api/v1/projects/{project_id}/discovery/favorites` | 保存或更新项目内的检索结果收藏 |
| GET | `/api/v1/projects/{project_id}/discovery/favorites` | 获取当前项目收藏 |
| DELETE | `/api/v1/projects/{project_id}/discovery/favorites/{favorite_id}` | 删除当前项目收藏 |
| POST | `/api/v1/projects/{project_id}/discovery/import` | 从已批准的 arXiv 标识进入现有安全导入/解析队列 |

POST 请求体为 `{intent, filters?, max_results?}`：`intent.topic` 必填，`filters` 支持年份、语言、领域和出版物类型，`max_results` 为 1–10。响应包含 `execution_id`、结构化 `papers`、`result_count`、`search_rounds`、`provider` 和 `warnings`；摘要保留 Provider 返回的完整内容，不以文本解析替代结构化结果。

检索使用 Semantic Scholar 的未认证公开路径作为主 Provider，Crossref 作为 metadata 补充/回退；Semantic Scholar API Key 是可选增强，不是 V1 启动条件。真实 Provider 的 401/403/429/超时会映射为有界错误或回退，不伪造论文。

收藏请求必须提交经过校验的结构化论文 metadata；服务端按 `source + source_paper_id` 幂等保存到项目偏好 JSON，不创建 `ProjectPaper`。导入请求只接受 `source=arxiv`、合法 arXiv 标识及匹配的 approved locator / result id，不接受任意下载 URL；实际下载、解析、索引和 ProjectPaper 关联继续复用现有 `remote_paper_import` 与 Worker pipeline。

## 前端 Axios 约定

文件：`frontend/src/api/index.ts`

- `baseURL = import.meta.env.VITE_API_BASE_URL || ''`
- 请求前自动从 `localStorage.access_token` 注入 Bearer token。
- 收到 401 时删除 token 并跳转 `/login`。

如果前后端不同源运行，需要配置：

- `VITE_API_BASE_URL=http://localhost:8000`，或
- 反向代理。

当前 Docker 前端通过 Nginx 将 `/api/` 代理到 backend 容器，通常无需设置该变量。

## 文档维护规则

`API.md` 是当前实现 Contract，不是未来 API 设计文档；上面的兼容路由明确标记为非 V1 主入口。

新增接口只有在对应 Phase 实现、测试通过后才能加入；以下是维护检查项，不代表这些未来能力
已经存在：

- Project V1 后续新增 / 调整接口
- Literature Discovery API
- Favorite / Import API
- Project Context / Paper Profile API（如果最终对前端暴露）
- Writing Agent API
- Citation Verification API
- 新 Execution / SSE API

实现 API 时必须同步记录：

1. Method
2. Path
3. Request schema
4. Response schema
5. Ownership / auth requirement
6. Frontend caller
7. Backward compatibility
8. 对应测试

未来施工目标请查看 `docs/spec-v2/`，实施状态查看
`docs/spec-v2/execution/IMPLEMENTATION_PROGRESS.md`。
