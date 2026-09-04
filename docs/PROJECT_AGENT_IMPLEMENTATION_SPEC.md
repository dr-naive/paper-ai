# PaperAI Research Agent 产品化与工程实施规格

> 文档版本：v1.0  
> 适用对象：Codex / AI Coding Agent / PaperAI 开发者  
> 目标：在现有 PaperAI 基础上，将“论文精读 + RAG 问答 + 初步 Agent 原型”升级为真正可用的一站式 Research Agent Workspace。  
> 本文是**实施规格**，不是概念方案。除非本文明确允许，否则不要自行改变产品方向、增加 Agent、增加 Tool、增加页面或更换基础技术栈。

---

# 0. 为什么要重构，而不是继续加功能

当前 PaperAI 已经具备较成熟的论文资产能力：

- PDF 上传、解析、章节、版面元素、表格、图片结构化
- Chunk / Embedding / Chroma
- Hybrid RAG / 表格检索 / Evidence Review
- PDF Viewer / bbox 引用定位
- SSE 可恢复流式回答
- Redis Worker
- PostgreSQL
- QA / Summary / Interpret 等固定工作流
- ResearchProject / ProjectPaper
- 初步 Lead Agent / Tool / Skill / Critique Agent
- Project Workspace / WritingStudio

因此本次升级**不是重新做论文助手**。

当前最大问题不是“功能少”，而是：

1. Agent 原型铺设过快，Runtime / State / Permission / Execution / Memory / Evidence 基础不够稳定。
2. Tool 粒度不统一，部分 Tool 实际上包含完整业务流程，Agent 只是形式上的调用者。
3. Skill 缺少正式 manifest、版本、预算、完成标准和评测绑定。
4. Project Memory 仍是 JSON，不适合作为长期研究记忆。
5. Evidence / Citation 没有成为一级实体，阅读与写作之间的证据链没有完全打通。
6. WritingStudio 使用原生 `contenteditable`，文档数据模型不稳定。
7. `ProjectWorkspace.vue`、`PaperReader.vue` 过大，前端状态散落，无法很好承载长期 Agent 任务。
8. Agent 过程向用户暴露过多内部信息，但真正有价值的“结果、证据、下一步”不够突出。
9. 现有数据库仍依赖 `create_all`，无法安全支持大规模 schema 演进。
10. “功能做出来”优先于“用户是否真的需要、是否真的能完成任务”。

本次重构的核心目标：

> **把 PaperAI 从“很多 AI 功能的集合”升级成“能够真正陪用户完成选题、调研、阅读、知识沉淀和写作的 Research Workspace”。**

---

# 1. 产品目标

PaperAI 的核心用户任务不是“使用 Agent”。

用户真正想完成的是：

```text
我需要完成一个研究课题 / 论文
        ↓
不知道选什么
        ↓
找到值得研究的方向
        ↓
找到相关论文
        ↓
快速理解论文
        ↓
建立领域认知
        ↓
找到研究空白 / 冲突 / 可行方向
        ↓
形成自己的研究问题
        ↓
组织证据和笔记
        ↓
建立论文大纲
        ↓
开始写作
        ↓
找到支撑当前论点的论文和证据
        ↓
检查引用、逻辑、事实
        ↓
完成论文
```

因此产品必须围绕 **Research Project** 组织，而不是围绕“聊天框”组织。

---

# 2. 产品设计原则

## 2.1 用户永远不需要理解 Tool / Skill / ReAct / Harness

以下名词只存在于开发实现中：

- Tool
- Skill
- Workflow
- Agent
- SubAgent
- ReAct
- Runtime
- Context Engine

用户界面禁止出现类似：

```text
正在调用 project_search_content
正在执行 literature_research skill
Agent iteration 5
Tool result received
```

用户只应该看到：

```text
正在搜索相关论文
已找到 28 篇候选论文
正在筛选与“Agent Memory”高度相关的研究
已完成 8 篇核心论文的初步阅读
发现 3 个主要研究方向
```

---

## 2.2 结果优先，过程其次

Agent 页面默认展示：

1. 当前结论
2. 支撑证据
3. 已完成的工作
4. 下一步建议

Agent 活动日志默认折叠。

禁止把大量内部执行过程作为主要 UI。

---

## 2.3 每个 AI 结果必须回答四件事

所有研究类输出统一考虑：

```text
What
结论是什么？

Why
为什么得出这个结论？

Evidence
依据是什么？

Next
下一步用户可以做什么？
```

如果 AI 无法给出 Evidence，则不能把推测表达成事实。

---

## 2.4 少即是多

禁止为了“显得 Agent 很强”增加：

- 无意义工具
- 无意义卡片
- 无意义状态
- 无意义推荐
- 无意义统计图
- 无意义 Agent 消息

每一个功能都必须明确：

```text
用户什么时候需要？
解决什么问题？
如果没有这个功能，用户损失是什么？
用户完成任务后得到什么？
```

没有明确答案的功能不要做。

---

## 2.5 不要把 Workflow 强行 Agent 化

以下能力保持确定性 Workflow：

- PDF 解析
- Chunk
- Embedding
- Indexing
- Citation formatting
- 文档导出
- 固定数据转换
- deterministic table lookup
- schema validation
- reference formatting

Agent 负责：

- 不确定的搜索策略
- 是否继续搜索
- 哪篇值得读
- 哪些证据相关
- 需要补充什么信息
- 如何组织调研
- 如何发现 gap
- 如何根据已有研究帮助写作

---

# 3. 目标产品形态

产品名称暂时继续使用 PaperAI。

核心形态：

```text
PaperAI
└── Research Project
    ├── Overview
    ├── Discover
    ├── Library
    ├── Reading
    ├── Notes
    ├── Writing
    └── Activity

Research Agent 不是单独页面。
Research Agent 是贯穿整个 Project 的能力。
```

---

# 4. 核心用户流程

## 4.1 流程 A：选题

用户：

```text
我想做 Agent Memory 相关研究，但还不知道具体方向。
```

系统应该：

1. 询问或读取已有 Project Brief：
   - 学科
   - 研究水平
   - 论文类型
   - 时间范围
   - 技术限制
   - 是否偏理论 / 工程
2. 搜索领域论文。
3. 识别主要研究方向。
4. 找最近研究趋势。
5. 找论文之间反复出现的问题。
6. 找有争议或不足的地方。
7. 给出 3~5 个“可研究方向”。

每个方向必须包含：

```text
方向名称
研究问题
为什么值得做
已有工作
潜在 gap
实现难度
数据 / 实验可行性
代表论文
风险
推荐下一步
```

禁止只输出：

```text
方向1：多 Agent Memory
方向2：长期记忆
方向3：知识图谱
```

这种结果没有实际价值。

---

## 4.2 流程 B：文献调研

用户选择方向后：

```text
帮我系统了解这个领域。
```

系统不是直接生成一篇“文献综述”。

应该：

```text
定义搜索范围
↓
搜索候选论文
↓
去重
↓
筛选
↓
确定核心论文
↓
形成阅读计划
↓
读取核心论文
↓
主题聚类
↓
整理共识 / 分歧
↓
识别关键方法
↓
识别 research gap
↓
生成领域概览
```

最终结果：

- 领域地图
- 核心论文
- 主题分类
- 每类代表工作
- 共同结论
- 相互冲突
- 研究空白
- 后续需要继续搜索的问题

这些属于 **Skill 结果 / Artifact**，不是单个 Tool。

---

## 4.3 流程 C：精读

用户打开论文。

阅读界面需要：

```text
目录
PDF
Research Assistant
```

用户可以：

- 问当前论文
- 问选中内容
- 找某个概念
- 找实验设置
- 找贡献
- 找限制
- 对比项目里的其他论文
- 保存为 Evidence
- 保存为 Research Note
- 加入写作引用库

AI 回答必须尽量绑定：

```text
Paper
Section
Page
Element
bbox
```

---

## 4.4 流程 D：知识积累

用户不应该看到“Memory JSON”。

用户看到的是：

```text
Research Notes
```

分为：

- Findings
- Questions
- Hypotheses
- Decisions
- Definitions
- Constraints

例如：

```text
Finding
多个 Agent Memory 系统仍依赖固定 retrieval policy。

来源：
Paper A p.6
Paper B p.11

标签：
memory
retrieval
adaptive
```

---

## 4.5 流程 E：写作

用户写论文时：

```text
Outline
Editor
Evidence
References
AI Assistance
```

AI 的默认行为不是直接替用户“写整篇论文”。

优先帮助：

- 构建大纲
- 找支撑证据
- 检查当前论点
- 提供改写建议
- 对比多篇研究
- 找缺少引用的地方
- 检查引用是否真的支持当前句子
- 找逻辑跳跃
- 提醒已有研究冲突

涉及正文自动修改时默认：

```text
生成建议
↓
显示 Diff
↓
用户确认
↓
应用修改
```

---

# 5. 当前代码必须保留的资产

以下能力原则上不要重写：

- PDF 上传与校验
- PDF 原始文件路径契约
- Section
- DocumentElement
- Table / TableStructure / TableCell
- Image
- bbox citation
- PdfViewer
- SmartChunker 基础思想
- Hybrid Retrieval
- Table Retrieval
- Evidence Review
- LLM Client
- Redis Worker
- Redis answer task
- SSE resume
- AnswerTrace
- 现有 RAG eval
- ResearchProject
- ProjectPaper
- JWT ownership
- PostgreSQL
- Redis
- Chroma
- Docker Compose

如果必须修改，需要提供兼容迁移。

---

# 6. 当前需要停止扩展的部分

在本文 Phase 1~4 完成前：

禁止新增：

- 新 SubAgent
- 新的“大型业务 Tool”
- 新的 Agent 页面
- 新的 memory JSON 字段
- 新的 WritingArtifact 类型
- 新的独立 Agent Runtime
- 第三套任务系统
- 第三套 Chat schema

Critique SubAgent 可以保留。

不要增加：

```text
SearchAgent
ReadingAgent
WritingAgent
CitationAgent
TopicAgent
```

---

# 7. 目标后端目录结构

目标不是一次性移动全部代码。

新代码必须按照目标边界创建，旧代码在触及时逐步迁移。

```text
backend/app/

├── main.py
├── config.py

├── api/
│   ├── auth.py
│   ├── papers.py
│   ├── projects.py
│   ├── conversations.py
│   ├── executions.py
│   ├── evidence.py
│   ├── memory.py
│   └── documents.py

├── domain/
│   ├── project/
│   │   ├── entities.py
│   │   ├── enums.py
│   │   └── contracts.py
│   │
│   ├── research/
│   │   ├── evidence.py
│   │   ├── memory.py
│   │   └── notes.py
│   │
│   ├── agent/
│   │   ├── execution.py
│   │   ├── events.py
│   │   ├── tool.py
│   │   └── skill.py
│   │
│   └── writing/
│       ├── document.py
│       ├── revision.py
│       └── citation.py

├── application/
│   ├── project_service.py
│   ├── evidence_service.py
│   ├── memory_service.py
│   ├── document_service.py
│   ├── execution_service.py
│   └── conversation_service.py

├── agent/
│   ├── runtime/
│   │   ├── executor.py
│   │   ├── context_engine.py
│   │   ├── tool_runtime.py
│   │   ├── skill_runtime.py
│   │   ├── policy.py
│   │   ├── budget.py
│   │   ├── checkpoint.py
│   │   └── event_bus.py
│   │
│   ├── agents/
│   │   ├── research_agent.py
│   │   └── critique_agent.py
│   │
│   ├── tools/
│   │   ├── paper/
│   │   ├── project/
│   │   ├── literature/
│   │   ├── evidence/
│   │   ├── memory/
│   │   └── writing/
│   │
│   └── skills/
│       ├── topic-exploration/
│       ├── literature-review/
│       ├── deep-reading/
│       ├── paper-comparison/
│       ├── gap-analysis/
│       ├── outline-planning/
│       ├── section-writing/
│       └── citation-audit/

├── workflows/
│   ├── paper_processing/
│   ├── qa/
│   ├── summarization/
│   └── citation_audit/

├── retrieval/
│   ├── knowledge_base.py
│   ├── hybrid.py
│   ├── tables.py
│   └── evidence_review.py

├── infrastructure/
│   ├── db/
│   │   ├── models/
│   │   ├── repositories/
│   │   └── migrations/
│   │
│   ├── redis/
│   ├── vector/
│   ├── storage/
│   └── external/
│       ├── arxiv.py
│       └── semantic_scholar.py

├── workers/
│   ├── worker.py
│   └── handlers/

└── llm/
    ├── client.py
    ├── provider.py
    └── models.py
```

---

# 8. 分层规则

## API Layer

负责：

- HTTP
- auth dependency
- request validation
- response serialization
- SSE connection

禁止：

- 直接写复杂 Agent 逻辑
- 直接实现多步骤业务
- 直接操作 Chroma
- 直接组 prompt

---

## Application Layer

负责：

- use case
- transaction boundary
- domain orchestration

例如：

```text
AddPaperToProject
SaveEvidence
CreateExecution
ApplyDocumentRevision
```

---

## Domain Layer

只描述业务规则。

禁止依赖：

- FastAPI
- Redis
- Chroma
- LangChain
- Vue
- HTTP

---

## Agent Layer

负责：

- 决策
- Tool 调用
- Skill 装载
- context
- execution lifecycle

禁止直接操作数据库 ORM。

Agent 必须通过 Application Service / Repository 接口。

---

## Infrastructure Layer

负责：

- PostgreSQL
- Redis
- Chroma
- filesystem
- external API

---

# 9. 现有文件迁移映射

| 当前文件 | 目标 |
|---|---|
| `harness/agents/lead_agent.py` | 拆成 `research_agent.py` + runtime executor/context/tool runtime |
| `harness/agents/routing.py` | 保留逻辑，迁入 agent routing/policy |
| `harness/skills/registry.py` | 改为正式 SkillRuntime |
| `harness/tools/literature_research.py` | 必须拆分 |
| `harness/tools/paper_internal.py` | 拆成 paper atomic tools |
| `harness/tools/external_literature.py` | 外部 API client + literature tools |
| `ResearchProject.memory JSON` | 兼容读取，逐步迁移到 memory_items |
| `WritingArtifact` | 保留 generic artifact；正式 manuscript 使用新 Document |
| `ProjectWorkspace.vue` | 拆成 route pages + feature components |
| `PaperReader.vue` | 拆 composables / panels / message / evidence components |
| `WritingStudio.vue` | 逐步替换为 TipTap editor |
| `api/chat.py` | 保留兼容 API，内部调用 ExecutionService |

不要一次大移动全部文件。

---

# 10. 技术栈决定

## 后端继续使用

- Python
- FastAPI
- Pydantic v2
- SQLAlchemy async
- PostgreSQL
- Redis
- Chroma
- LangChain / LangGraph（只用于适合的 workflow）
- 现有 LLM client

---

## 新增

### Alembic

必须。

从本轮升级开始：

> 所有数据库结构变化必须通过 Alembic migration。

禁止继续依赖：

```python
Base.metadata.create_all()
```

完成 schema 演进。

`create_all` 可以暂时作为开发空库初始化兜底，但生产 migration 以 Alembic 为准。

---

## 前端继续使用

- Vue 3
- TypeScript
- Vite
- Vue Router
- Arco Design
- Axios
- markdown-it
- DOMPurify
- PDF.js

---

## 前端新增

### Pinia

已有依赖，正式使用。

负责：

- project state
- active execution
- task center
- workspace UI state
- auth/session

---

### TipTap / ProseMirror

替换 WritingStudio 的原生 contenteditable。

原因：

- schema 稳定
- selection 稳定
- citation node 可扩展
- comment / mark / suggestion 可扩展
- JSON 可作为权威文档格式
- 易实现 Diff / AI patch

---

### KaTeX

用于 Markdown / Writing 中数学公式渲染。

---

# 11. 不引入的技术

当前阶段不要引入：

- Temporal
- Celery
- Kafka
- Kubernetes
- Milvus
- Qdrant
- Elasticsearch
- Graph Database
- LangChain 多 Agent Framework

原因：

当前规模不需要。

现有：

```text
PostgreSQL + Redis Worker + Chroma
```

足够完成第一版稳定 Research Agent。

---

# 12. Agent Runtime 核心模型

Research Agent 不再只是：

```text
LLM → tool → LLM
```

必须有正式 Execution。

---

# 13. AgentExecution

新增表：

```text
agent_executions
```

核心字段：

```text
id UUID
user_id
project_id nullable
conversation_id nullable

agent_type
goal
status

current_stage
active_skill

runtime_version

max_tool_calls
max_model_calls
max_tokens
max_seconds

tool_call_count
model_call_count
input_tokens
output_tokens

created_at
started_at
updated_at
completed_at

error_code
error_message
```

status：

```text
queued
running
waiting_user
paused
completed
failed
cancelled
```

---

# 14. AgentEvent

新增：

```text
agent_events
```

字段：

```text
id
execution_id
seq

event_type
stage
title
message

payload JSON

created_at
```

event_type：

```text
execution_started
stage_changed

search_started
search_completed

paper_selected
paper_read

tool_started
tool_completed
tool_failed

artifact_created

approval_required
approval_resolved

execution_paused
execution_resumed
execution_cancelled

execution_completed
execution_failed
```

重要：

**不要持久化模型私有 Chain-of-Thought。**

不要再向前端发送原始 reasoning。

前端只显示结构化 Activity。

---

# 15. ToolCall

新增：

```text
tool_calls
```

字段：

```text
id
execution_id
step_index

tool_name
tool_version

arguments JSON
result_summary
result_payload JSON

side_effect_level
status

started_at
completed_at

error_code
error_message

idempotency_key
```

Tool Call 是审计对象。

---

# 16. Redis 的职责

Redis：

- queue
- live execution state cache
- cancellation flag
- SSE event buffer
- temporary checkpoint
- worker lease / heartbeat

PostgreSQL：

- execution truth
- tool history
- durable events
- evidence
- memory
- documents
- revisions

原则：

> PostgreSQL = Truth  
> Redis = Runtime

---

# 17. Execution 生命周期

```text
create execution
↓
persist PostgreSQL
↓
enqueue Redis
↓
worker acquire
↓
execution_started
↓
load context
↓
load skill
↓
agent loop
↓
tool
↓
event
↓
checkpoint
↓
continue
↓
completion gate
↓
persist result
↓
execution_completed
```

---

# 18. Pause / Resume / Cancel

Cancel：

1. API 写 Redis cancel flag
2. worker 在每轮 Agent Loop 检查
3. ToolRuntime 在网络 / 批处理工具中检查 CancellationToken
4. 当前不可中断的原子操作完成后退出
5. PostgreSQL status → cancelled

Pause：

只允许在安全步骤边界暂停。

不要试图在数据库事务中途 pause。

---

# 19. Budget

每个 Execution 必须有预算。

例如：

```text
max_tool_calls
max_model_calls
max_tokens
max_seconds
max_external_searches
max_papers_to_read
```

用户不需要看到技术预算。

UI 可以显示：

```text
阅读上限：15 篇核心论文
```

---

# 20. Context Engine

当前项目把 project memory / papers / artifact 直接拼接 prompt 的方式必须升级。

Context Engine 输入：

```text
User Request
Project
Conversation
Active Paper
Active Document Section
Execution
Skill
```

输出：

```text
ContextBundle
```

结构：

```python
class ContextBundle:
    task: str
    project_brief: str | None
    active_paper: dict | None
    recent_conversation: list
    memories: list
    evidence: list
    document_context: dict | None
    constraints: list[str]
```

---

# 21. Context Token Budget

不要按字符简单截断。

第一版至少按 token 估算分配：

```text
System + Skill         25%
User task              10%
Recent conversation    10%
Project brief          10%
Retrieved memory       10%
Retrieved evidence     25%
Reserved output        10%
```

不同 Skill 可以覆盖策略。

---

# 22. Research Memory

停止继续扩展：

```text
ResearchProject.memory JSON
```

新增：

```text
memory_items
```

字段：

```text
id
project_id
user_id

type
title
content

source_type
source_id

confidence

tags JSON

created_by
created_at
updated_at

superseded_by nullable
```

type：

```text
finding
question
hypothesis
decision
definition
constraint
preference
summary
```

---

# 23. Memory 的产品名称

内部：

```text
MemoryItem
```

用户界面：

```text
Research Notes
```

不要向普通用户展示“Memory System”。

---

# 24. Memory 写入规则

Agent 不能每句话都写 memory。

只有满足以下条件才允许：

- 对后续研究有持续价值
- 是用户明确决定
- 是重要研究发现
- 是后续任务需要保留的约束
- 是关键未解决问题

禁止记录：

- 临时搜索结果
- 工具日志
- 无价值中间推理
- 重复内容

---

# 25. Evidence 一级实体

新增：

```text
evidence_items
```

字段建议：

```text
id
project_id
paper_id

section_id nullable
element_id nullable
chunk_id nullable

page_number
bbox JSON

evidence_type

snippet
normalized_claim

source_title
source_authors
source_year
doi nullable

created_by
created_at
```

evidence_type：

```text
quote
result
method
definition
limitation
comparison
background
```

---

# 26. Evidence 的价值

Evidence 用于连接：

```text
Paper
 ↓
Research Note
 ↓
Research Claim
 ↓
Writing Section
 ↓
Citation
```

以后所有研究类 Agent 都应该优先使用 Evidence，而不是简单把向量检索文本塞进最终结果。

---

# 27. Citation

Citation 不等同 Evidence。

```text
Evidence
= 支撑一个判断的具体来源内容

Citation
= 写作中引用这个来源的表现形式
```

后续增加：

```text
citation_refs
```

至少记录：

```text
document_id
revision_id
paper_id
evidence_id nullable
locator
citation_key
```

---

# 28. Tool 设计原则

Tool 必须是“原子能力”。

正确：

```text
search_external_papers
search_project_content
get_paper_outline
read_paper_section
save_memory_item
save_evidence
add_paper_to_project
create_document_revision
```

错误：

```text
complete_literature_review
finish_research
write_whole_paper
make_research_map_and_summary
```

后者属于 Skill。

---

# 29. Tool Contract

所有 Tool 必须实现统一元数据：

```python
class ToolSpec:
    name: str
    version: str
    description: str

    side_effect: Literal[
        "read",
        "write",
        "network",
        "destructive",
    ]

    requires_confirmation: bool

    timeout_seconds: int

    idempotent: bool

    input_schema: type[BaseModel]
```

结果统一：

```python
class ToolResult(BaseModel):
    ok: bool

    summary: str
    data: dict | list | None

    evidence_ids: list[str] = []
    artifact_ids: list[str] = []

    retryable: bool = False

    error_code: str | None = None
    error_message: str | None = None
```

禁止 Tool 返回一大段无结构 Markdown 作为唯一结果。

---

# 30. Tool 权限等级

### READ

例如：

- get paper metadata
- search project content

自动执行。

### NETWORK

例如：

- arXiv
- Semantic Scholar

默认允许，但受 project / user policy 控制。

### WRITE

例如：

- save note
- add paper
- save evidence

如果用户当前指令明确要求，可自动执行。

否则 Agent 应说明改变。

### DESTRUCTIVE

例如：

- delete paper
- delete project
- overwrite manuscript

必须用户确认。

---

# 31. 第一版标准 Tool 列表

不要无限扩张。

## Paper

```text
paper.get_metadata
paper.get_outline
paper.search_content
paper.get_context
paper.get_table
```

## Project

```text
project.list_papers
project.search_content
project.add_paper
project.update_paper_role
```

## Literature

```text
literature.search_external
literature.get_metadata
literature.import_paper
```

## Memory

```text
memory.search
memory.save
memory.update
```

## Evidence

```text
evidence.search
evidence.save
```

## Writing

```text
document.get_context
document.create_revision
citation.find_support
citation.audit
```

第一阶段控制在约 15~20 个核心 Tool。

---

# 32. Tool 用户体验规则

用户不需要手动点 Tool。

不要在 UI 做：

```text
[调用 search_project_content]
[调用 evidence.save]
```

应该做：

```text
[搜索项目论文]
[保存为研究证据]
```

工具是实现细节。

---

# 33. Skill 定义

Skill 是：

> 完成一类研究任务时，Agent 使用的一套领域方法、允许使用的工具、边界、预算和完成条件。

Skill 不是 Python function。

---

# 34. Skill 目录

```text
agent/skills/literature-review/

├── skill.yaml
├── SKILL.md
├── examples/
│   ├── good.md
│   └── bad.md
└── evals/
    └── cases.yaml
```

---

# 35. skill.yaml

示例：

```yaml
id: literature-review
version: 1.0.0
title: Literature Review

description: >
  对一个明确研究主题完成系统化的初步文献调研。

allowed_tools:
  - literature.search_external
  - project.search_content
  - project.add_paper
  - paper.get_metadata
  - paper.search_content
  - memory.save
  - evidence.save

permissions:
  network: true
  write_project: true
  write_memory: true
  destructive: false

budget:
  max_tool_calls: 40
  max_external_searches: 6
  max_papers_to_read: 15

completion:
  require_representative_papers: true
  require_theme_clusters: true
  require_evidence: true
  require_open_questions: true
```

---

# 36. SKILL.md 内容要求

必须包含：

```text
Purpose
When to use
When NOT to use
Inputs
Expected output
Recommended process
Evidence requirements
Failure handling
Completion criteria
Quality checklist
```

---

# 37. 第一版 Skill

## topic-exploration

解决：

```text
“我不知道选什么题。”
```

输出：

- 3~5 个方向
- gap
- feasibility
- evidence
- risks

---

## literature-review

解决：

```text
“帮我系统了解这个领域。”
```

输出：

- 主题
- 代表论文
- 共识
- 分歧
- gap
- unanswered questions

---

## deep-reading

解决：

```text
“帮我真正读懂这篇论文。”
```

不是全文摘要。

重点：

- research question
- method
- assumption
- experiment
- contribution
- limitation
- relation to project

---

## paper-comparison

输出：

```text
共同问题
方法差异
数据差异
实验差异
结论差异
优缺点
```

---

## gap-analysis

不能只让 LLM 凭印象生成 gap。

必须基于：

- representative papers
- evidence
- limitations
- conflicting findings

输出：

```text
Gap
Evidence
Why unresolved
Research opportunity
Feasibility
Risk
```

---

## outline-planning

输入：

- project
- research question
- notes
- evidence

输出可编辑 outline。

---

## section-writing

输入：

- selected section
- outline
- evidence

默认输出：

```text
Suggested draft
Evidence map
Missing evidence
```

不要自动覆盖正文。

---

## citation-audit

检查：

- citation exists
- citation supports claim
- source actually available
- duplicate citation
- unsupported claim

---

# 38. Skill 不是聊天 Prompt

禁止把 Skill 写成：

```text
你是一个优秀的论文助手……
请认真回答……
```

必须写研究任务方法。

---

# 39. Agent Routing

保留：

```text
direct
workflow
agent
```

但是定义清楚。

## Direct

- 获取 metadata
- 简单状态
- CRUD

## Workflow

- paper parsing
- summary
- deterministic analysis
- citation export

## Agent

- topic exploration
- literature review
- research gap
- complex cross-paper question
- writing with research context

---

# 40. Research Agent

只保留一个主 ResearchAgent。

职责：

```text
Understand goal
Select skill
Build context
Choose tools
Observe results
Decide next action
Check completion
Return user result
```

不负责：

- 数据库实现
- HTTP
- Redis
- UI
- PDF parsing

---

# 41. Critique Agent

现有 Critique Agent 可以保留。

只用于：

- 审核复杂 research conclusion
- 评估 evidence sufficiency
- 写作逻辑 critique

不要用于所有回答。

否则成本和延迟过高。

---

# 42. 不建立 Multi-Agent 平台

除 Critique 外，当前不要做通用 SubAgent registry。

未来只有满足以下场景再考虑：

```text
一个任务需要并行阅读 > 10 篇论文
单个 context 已明显无法承载
并行子任务能显著降低时间
```

---

# 43. Writing 数据模型

现有 WritingArtifact 保留：

用途：

- reading plan
- research map
- evidence matrix
- comparison report
- generated analysis

不要把正式论文正文继续塞进泛化 Artifact。

新增：

```text
writing_documents
document_revisions
```

---

# 44. writing_documents

字段：

```text
id
project_id
title
document_type
status

current_revision_id

created_at
updated_at
```

---

# 45. document_revisions

权威内容：

```text
content_json
```

使用 TipTap / ProseMirror JSON。

字段：

```text
id
document_id
version

content_json

created_by
source_execution_id nullable

created_at
```

Markdown / HTML 都由 JSON 派生。

不要三份权威数据。

---

# 46. AI 编辑流程

```text
用户选中段落
↓
点击 AI Action
↓
AI 生成 patch / replacement suggestion
↓
前端显示 Diff
↓
Accept / Reject
↓
Accept 后创建新 revision
```

AI 不直接覆盖 document。

---

# 47. API 设计

新增：

## Execution

```text
POST   /api/v1/projects/{project_id}/executions
GET    /api/v1/executions/{execution_id}
GET    /api/v1/executions/{execution_id}/events
GET    /api/v1/executions/{execution_id}/stream
POST   /api/v1/executions/{execution_id}/cancel
POST   /api/v1/executions/{execution_id}/pause
POST   /api/v1/executions/{execution_id}/resume
POST   /api/v1/executions/{execution_id}/approve
```

---

## Memory

```text
GET    /api/v1/projects/{id}/notes
POST   /api/v1/projects/{id}/notes
PATCH  /api/v1/projects/{id}/notes/{note_id}
DELETE /api/v1/projects/{id}/notes/{note_id}
```

产品叫 Notes。

后端 domain 可叫 MemoryItem。

---

## Evidence

```text
GET    /api/v1/projects/{id}/evidence
POST   /api/v1/projects/{id}/evidence
GET    /api/v1/evidence/{id}
DELETE /api/v1/evidence/{id}
```

---

## Writing

```text
GET    /api/v1/projects/{id}/documents
POST   /api/v1/projects/{id}/documents

GET    /api/v1/documents/{id}
POST   /api/v1/documents/{id}/revisions
GET    /api/v1/documents/{id}/revisions
POST   /api/v1/documents/{id}/ai-actions
```

---

# 48. SSE Event Protocol

统一：

```json
{
  "id": "event_uuid",
  "seq": 18,
  "execution_id": "uuid",
  "type": "stage_changed",
  "timestamp": "ISO8601",
  "stage": "screening",
  "message": "正在筛选与研究主题最相关的论文",
  "data": {}
}
```

禁止 SSE 直接返回模型私有 reasoning。

---

# 49. 前端总体架构

目标：

```text
App Shell
├── Global Top Bar
├── Project Sidebar
├── Workspace
└── Agent / Activity Drawer
```

推荐 Desktop First。

最佳：

```text
1440px+
```

支持：

```text
1024px+
```

手机端优先支持：

- 查看项目
- 查看任务
- 阅读简单内容

完整三栏 PDF / Writing 不要求第一期实现优秀移动体验。

---

# 50. 全局布局

```text
┌─────────────────────────────────────────────────────────────┐
│ Logo  Project Switcher                       Tasks   User    │
├─────────────┬──────────────────────────────┬────────────────┤
│             │                              │                │
│ Project Nav │        Main Workspace        │ Agent Drawer   │
│             │                              │                │
│             │                              │                │
└─────────────┴──────────────────────────────┴────────────────┘
```

尺寸：

```text
TopBar        56px
Sidebar       220px
Agent Drawer  360px
Main          flex
```

Agent Drawer 可折叠。

---

# 51. 全局导航

Project Sidebar：

```text
Overview
Discover
Library
Reading
Notes
Writing
Activity
```

不要用：

```text
Agent
Memory
Tools
Skills
```

作为用户导航。

---

# 52. 全局 TopBar

左：

- PaperAI Logo
- Project Switcher

中间不放复杂内容。

右：

- Running Tasks 图标 + 数字 Badge
- 全局搜索（后续）
- User Avatar

---

# 53. Agent Drawer

右侧 Agent Drawer 是全局能力。

顶部：

```text
Research Assistant
```

内容：

```text
Current Context
Conversation
Latest result
Suggested actions
```

底部输入：

```text
Ask about this project...
```

快捷操作最多 3 个。

例如：

```text
Explore topic
Find papers
Check evidence
```

不要堆 10 个功能按钮。

---

# 54. Agent Drawer Activity

默认不展示所有 Tool。

结果下方：

```text
Activity · 8 steps
```

点击展开才显示：

```text
Searched 3 queries
Reviewed 24 candidates
Read 6 papers
Saved 9 evidence items
```

用户不需要看到：

```text
tool_call #17
```

---

# 55. 视觉风格

继续沿用当前“暖色、克制、学术工作台”方向。

不要改成：

- 五颜六色 SaaS Dashboard
- 大量渐变
- 大量统计卡
- 霓虹 AI 风格

目标：

```text
Notion 的克制
+
Linear 的清晰
+
论文阅读器的信息密度
```

---

# 56. 色系

目标 Design Tokens：

```css
--color-bg: #F7F5F2;
--color-surface: #FFFFFF;
--color-surface-subtle: #FBFAF8;

--color-text: #292522;
--color-text-secondary: #6F6861;
--color-text-tertiary: #968F88;

--color-border: #E6E0D9;
--color-border-strong: #D7CFC7;

--color-primary: #C96A2B;
--color-primary-hover: #B75C21;
--color-primary-soft: #F8EADF;

--color-info: #356AE6;
--color-success: #2F855A;
--color-warning: #B7791F;
--color-danger: #C2413A;
```

与现有 App.vue token 做映射，不要求一次重写全部 CSS。

---

# 57. Typography

正文：

```text
14px / 1.6
```

主页面标题：

```text
24px / 32px / 600
```

Section：

```text
18px / 26px / 600
```

Card Title：

```text
15px / 22px / 600
```

辅助文本：

```text
13px
```

研究工具不需要巨大标题。

---

# 58. Card 规范

默认 Card：

```text
white
1px border
8~12px radius
16px padding
轻 shadow 或无 shadow
```

一页不要超过 2~3 种 Card 风格。

不要所有东西都 Card 化。

---

# 59. 页面：Projects

Route：

```text
/projects
```

顶部：

```text
Research Projects
                         [New Project]
```

主体：

- Active Projects
- Archived Projects

Project Card：

```text
Project title
Research topic / one-line brief

Phase badge
12 papers
3 notes
1 running task

Last activity

[Open]
```

不要显示没有用户价值的统计：

- tool calls
- token usage
- vector count

---

# 60. New Project Dialog

字段：

```text
Project Name *
Research Topic / Idea
Field
Research Goal
Expected Output
```

高级选项折叠：

```text
Year range
Language
Method preference
```

创建后进入 Overview。

---

# 61. 页面：Overview

Route：

```text
/project/:id/overview
```

顶部：

```text
Project Title
Topic
Phase
[Ask Research Assistant]
```

第一块：

## Research Brief

包含：

- Current Research Question
- Goal
- Constraints

按钮：

```text
[Edit Brief]
```

第二块：

## Next Steps

只显示 1~3 个高价值行动：

```text
Explore possible directions
Review 6 unread core papers
Resolve 2 evidence gaps
```

第三块：

## Active Work

显示当前 Agent Execution。

第四块：

## Recent Research

- recently added papers
- recently saved findings
- recently edited document

Overview 禁止堆 Dashboard 图表。

---

# 62. 页面：Discover

Route：

```text
/project/:id/discover
```

目标：

帮助用户：

- 找方向
- 搜论文
- 判断论文是否值得加入

---

# 63. Discover 顶部

搜索框：

```text
Search papers, topics, methods...
```

按钮：

```text
[Search]
```

旁边：

```text
[Explore Research Directions]
```

这个按钮启动 topic-exploration Skill。

---

# 64. Discover Filters

左侧或顶部展开：

```text
Year
Source
Field
Sort
Open Access
```

不要做 15 个筛选项。

---

# 65. Search Result Card

每篇：

```text
Title

Authors · Year · Venue

2~3 line abstract summary

Why it may matter
AI-generated relevance reason

Tags:
Memory
Retrieval
Agent

Source
Citation Count（仅来源真实提供时）

[Preview]
[Add to Project]
```

导入 PDF：

```text
[Import & Parse]
```

只有 PDF 确实可获取时显示。

---

# 66. Why it may matter

必须基于：

- 用户 Project Topic
- Abstract / metadata

不能凭空编造。

语气：

```text
可能相关，因为……
```

不是：

```text
这是该领域最重要的论文。
```

除非有依据。

---

# 67. Research Directions 结果

展示 3~5 张 Direction Card。

每张：

```text
Direction Title

Research Question

Why now

Existing approaches

Potential gap

Feasibility
Low / Medium / High

Representative papers

[Investigate]
[Save to Project Brief]
```

---

# 68. 页面：Library

Route：

```text
/project/:id/library
```

顶部：

```text
Project Papers
[Add Paper]
```

Tabs：

```text
All
Core
Background
Method
Unread
```

---

# 69. Paper Row / Card

显示：

```text
Title
Authors
Year

Role
Reading status
Priority

AI Paper Card summary（如果已经生成）

[Read]
[Ask]
[…]
```

更多菜单：

- Change role
- Remove from project
- Open original PDF
- Reprocess

---

# 70. Library Bulk Action

最多：

```text
[Create Reading Plan]
[Compare Selected]
```

不要提供很多批量 AI 按钮。

---

# 71. 页面：Reading

Paper 阅读保持现有 PdfViewer 优势。

布局：

```text
┌─────────────┬────────────────────────┬─────────────────┐
│ Outline     │ PDF                    │ Research Assist │
│             │                        │                 │
└─────────────┴────────────────────────┴─────────────────┘
```

---

# 72. Reading 左侧

- Outline
- Search in paper
- Figures / Tables（可折叠）

点击 section：

跳转 PDF。

---

# 73. Reading 中间

保留：

- zoom
- page
- fit width
- bbox highlight

用户选中文本后显示轻量浮动菜单：

```text
[Ask]
[Save Note]
[Save Evidence]
```

---

# 74. Reading 右侧

Tabs：

```text
Ask
Notes
Evidence
```

Ask：

- 对当前论文问答
- 默认 answer 结果
- sources

每个关键 source：

```text
[S1] p.6 · Methods
```

点击定位 PDF。

---

# 75. AI Answer 设计

禁止长篇堆砌。

结构：

```text
Answer

Key evidence

Sources

Related question（最多 2）
```

没有证据：

```text
I couldn't find enough support in this paper.
```

不要强行回答。

---

# 76. 页面：Notes

Route：

```text
/project/:id/notes
```

用户名称：

```text
Research Notes
```

顶部：

```text
[New Note]
Search notes...
```

分类：

```text
Findings
Questions
Hypotheses
Decisions
Definitions
```

---

# 77. Note Card

```text
Finding

Adaptive retrieval remains a recurring limitation...

Sources:
Paper A p.6
Paper B p.11

Tags
Updated time

[Open]
```

点击进入右侧 detail drawer。

---

# 78. 页面：Writing

Route：

```text
/project/:id/writing
```

布局：

```text
┌──────────────┬──────────────────────────┬─────────────────┐
│ Outline      │ Editor                   │ Evidence        │
│              │                          │ References      │
│              │                          │ AI Assist       │
└──────────────┴──────────────────────────┴─────────────────┘
```

---

# 79. Writing 左侧 Outline

显示：

```text
Title
Abstract
1 Introduction
2 Related Work
3 Method
4 Experiments
5 Discussion
6 Conclusion
References
```

支持：

- drag reorder
- add section
- rename

---

# 80. Editor

TipTap。

顶部基础功能：

```text
Heading
Bold
Italic
Quote
List
Equation
Citation
```

不要做 Word 全功能替代。

---

# 81. Writing AI 浮动菜单

选中文字：

```text
Improve academic style
Make concise
Clarify argument
Find supporting evidence
Check this claim
```

生成结果显示 Diff。

按钮：

```text
[Accept]
[Reject]
[Regenerate]
```

---

# 82. Evidence Panel

右侧：

搜索：

```text
Search evidence...
```

默认根据当前 section 自动推荐：

```text
Relevant Evidence
```

每项：

```text
Finding / quote
Paper
Page
Section

[Insert Citation]
[Open Source]
```

---

# 83. Citation 行为

点击：

```text
Insert Citation
```

插入 citation node。

Citation node 内保存：

```text
paper_id
citation_key
evidence_id optional
```

渲染格式由 citation style 决定。

---

# 84. Unsupported Claim

AI audit 发现：

```text
“Existing approaches have solved long-term memory.”
```

但没有证据。

显示：

```text
Evidence needed
```

按钮：

```text
[Find Support]
[Rewrite Claim]
```

这比简单“AI 检查完成”有实际作用。

---

# 85. 页面：Activity

Route：

```text
/project/:id/activity
```

只展示用户可理解任务。

例如：

```text
Literature Review
Running

Searched 3 queries
Reviewed 24 papers
Read 6 core papers
Saved 8 findings

[Pause] [Cancel]
```

---

# 86. Global Task Center

TopBar 右侧：

```text
Tasks ②
```

点击打开 Drawer。

显示：

- running
- waiting approval
- failed
- recently completed

用户切换页面后 Agent 继续工作。

---

# 87. Approval UX

当 Agent 需要危险操作：

```text
The assistant wants to remove 3 papers from this project.
```

显示：

```text
[Review]
[Approve]
[Reject]
```

禁止在 Chat 里用一句：

```text
是否确认？
```

然后没有明确影响范围。

---

# 88. 前端目录结构

```text
frontend/src/

├── router/
├── stores/
│   ├── auth.ts
│   ├── project.ts
│   ├── executions.ts
│   └── workspace.ts

├── api/
│   ├── projects.ts
│   ├── papers.ts
│   ├── executions.ts
│   ├── evidence.ts
│   ├── notes.ts
│   └── documents.ts

├── views/
│   ├── ProjectsView.vue
│   └── project/
│       ├── OverviewView.vue
│       ├── DiscoverView.vue
│       ├── LibraryView.vue
│       ├── ReadingView.vue
│       ├── NotesView.vue
│       ├── WritingView.vue
│       └── ActivityView.vue

├── features/
│   ├── agent/
│   ├── discovery/
│   ├── library/
│   ├── reader/
│   ├── notes/
│   ├── writing/
│   └── executions/

├── components/
│   ├── layout/
│   └── ui/

└── composables/
```

---

# 89. Vue 页面代码规则

目标：

```text
View ≤ 400 行
Feature component ≤ 300 行
Composable 聚合复杂状态
```

不是硬性失败阈值，但超过时必须说明原因。

禁止继续出现 1800~3000 行 View。

---

# 90. Store 职责

## executions store

负责：

```text
running executions
event stream
resume stream
cancel
pause
approval
task badge
```

页面切换不能丢状态。

---

## project store

负责：

```text
current project
project brief
paper count
phase
```

---

## workspace store

只负责 UI：

```text
sidebar collapsed
agent drawer open
active panel
```

---

# 91. 代码开发安全策略

任何大改必须遵循：

```text
Baseline
↓
Migration
↓
Backward-compatible backend
↓
Tests
↓
Feature flag
↓
Frontend adoption
↓
Remove old path
```

禁止：

```text
直接删除旧代码
↓
一次重写全部
```

---

# 92. Phase 0：冻结当前基线

在开始重构前：

1. 创建 Git 分支：
   ```text
   agent-rearchitecture-v1
   ```
2. 当前未提交 Agent 工作建立 WIP commit。
3. 执行全部现有 backend tests。
4. 记录当前测试结果。
5. 启动 Docker Compose smoke test。
6. 手工验证：
   - login
   - upload
   - parse
   - open paper
   - ask paper
   - project open
   - project chat
7. 保存 baseline。

没有 baseline 不允许开始 schema 重构。

---

# 93. Phase 1：Alembic

第一项正式代码工作。

完成：

```text
alembic init
baseline current schema
migration docs
upgrade / downgrade test
```

要求：

- 新建空数据库可以 `alembic upgrade head`
- 已有数据库可以 baseline 后继续 migration
- migration 不丢已有 paper / chat / project

---

# 94. Phase 2：Execution Runtime

只做基础设施。

新增：

- AgentExecution
- AgentEvent
- ToolCall
- repositories
- ExecutionService
- EventBus
- SSE protocol

这一阶段不要重做 Topic UI。

Acceptance：

- 创建 execution
- worker 执行 mock agent
- PostgreSQL 有 execution
- Redis stream event
- frontend 能 resume event
- cancel 有效

---

# 95. Phase 3：Tool Runtime

把现有 Tool 收口。

优先迁移：

```text
paper.get_metadata
paper.get_outline
paper.search_content
project.list_papers
project.search_content
literature.search_external
```

每一个必须：

- input schema
- ToolSpec
- ToolResult
- ownership
- timeout
- trace
- unit test

---

# 96. Phase 4：Skill Runtime

建立：

- skill.yaml parser
- version
- allowed tools
- permissions
- budget
- completion metadata

先迁移：

```text
paper_internal
external_literature
literature_research
```

但将 `literature_research` 拆成：

```text
Skill
+
atomic tools
```

---

# 97. Phase 5：Evidence + Notes

新增：

- evidence_items
- memory_items
- API
- service
- UI Notes / Evidence

ResearchProject.memory：

继续兼容读取。

新增写入全部进入新表。

后续 migration 再迁旧 JSON。

---

# 98. Phase 6：Project Workspace 前端重构

先拆页面，不新增大量功能。

目标：

```text
ProjectWorkspace.vue
```

不再承担所有子功能。

建立：

- Overview
- Discover
- Library
- Notes
- Activity

先保证功能迁移，不追求一次视觉完美。

---

# 99. Phase 7：Topic / Literature UX

完成：

- search
- search results
- project import
- topic exploration
- literature review execution
- results artifact

Acceptance：

用户真的可以：

```text
输入模糊研究方向
↓
得到 3~5 个有依据方向
↓
查看代表论文
↓
将方向写入项目
↓
继续搜索
```

---

# 100. Phase 8：Reading Integration

把：

```text
Save Note
Save Evidence
Compare with project papers
```

接入现有 PaperReader。

不要重写 PdfViewer。

---

# 101. Phase 9：Writing V2

新增 TipTap。

步骤：

1. 新 Document schema
2. Revision
3. editor
4. outline
5. evidence panel
6. citation node
7. AI diff
8. citation audit

旧 WritingArtifact 保留。

---

# 102. Phase 10：质量体系

建立 CI。

至少：

Backend：

```text
pytest
ruff
mypy 或 pyright 二选一
```

Frontend：

```text
typecheck
eslint
build
vitest
```

E2E：

```text
Playwright
```

第一版 E2E：

- login
- create project
- search paper
- add paper
- open paper
- ask
- save evidence
- open writing
- insert citation

---

# 103. Agent 测试策略

不能全部靠在线模型。

必须有 Mock LLM。

测试：

```text
LLM requests tool A
Tool result
LLM requests tool B
Tool result
LLM final
```

验证：

- routing
- budget
- permission
- tool error
- cancel
- retry
- completion

---

# 104. Skill Eval

每个 Skill 至少 5 个 cases。

例如 literature-review：

```text
clear topic
broad topic
insufficient papers
conflicting evidence
external API failure
```

评估：

- 是否找到有效论文
- 是否有 evidence
- 是否覆盖核心主题
- 是否胡编 paper
- 是否超预算

---

# 105. RAG Eval 不得丢失

现有 RAG eval 继续作为回归基线。

任何 retrieval 重构必须比较：

```text
before
after
```

不能仅凭“Agent 看起来回答更好”。

---

# 106. Feature Flag

大模块增加 flag：

```text
ENABLE_AGENT_RUNTIME_V2
ENABLE_MEMORY_V2
ENABLE_WRITING_V2
```

新旧实现可短期并存。

确认稳定后删除旧实现。

---

# 107. Error Taxonomy

统一错误：

```text
AUTH_ERROR
PERMISSION_DENIED

NOT_FOUND
VALIDATION_ERROR

TOOL_TIMEOUT
TOOL_FAILED
EXTERNAL_RATE_LIMIT

MODEL_TIMEOUT
MODEL_FAILED

EXECUTION_BUDGET_EXCEEDED
EXECUTION_CANCELLED

EVIDENCE_NOT_FOUND

STORAGE_ERROR
DATABASE_ERROR
```

前端根据 code 决定提示。

不要直接展示 Python exception。

---

# 108. 用户错误提示

错误提示必须告诉用户：

```text
发生了什么
是否影响已有数据
可以做什么
```

例如：

```text
Semantic Scholar 暂时限制请求。
已保留当前搜索结果，你可以稍后重试或继续使用 arXiv 结果。
```

不是：

```text
Request failed with status code 429
```

---

# 109. Observability

所有 Execution 必须记录：

- execution id
- skill version
- tool version
- model
- tool calls
- latency
- tokens
- error
- evidence count
- artifact ids

AnswerTrace 可继续复用部分指标。

---

# 110. Prompt 版本

所有正式系统 Prompt 不继续散落无版本。

建议：

```text
agent/prompts/
```

或由 Agent / Skill 目录管理。

Trace 记录：

```text
prompt_version
skill_version
runtime_version
```

---

# 111. 给 AI Coding Agent 的文档体系

仓库根目录新增：

```text
AGENTS.md
```

Codex 每次修改前必须读。

---

# 112. docs 目录

```text
docs/

├── product/
│   ├── PRODUCT_PRINCIPLES.md
│   ├── USER_FLOWS.md
│   └── UX_SPEC.md

├── architecture/
│   ├── OVERVIEW.md
│   ├── DOMAIN_MODEL.md
│   ├── AGENT_RUNTIME.md
│   ├── EVENT_PROTOCOL.md
│   ├── CONTEXT_MEMORY.md
│   └── CURRENT_TO_TARGET.md

├── agent/
│   ├── TOOL_SPEC.md
│   ├── SKILL_SPEC.md
│   ├── PERMISSION_SPEC.md
│   └── EVAL_SPEC.md

├── frontend/
│   ├── FRONTEND_ARCHITECTURE.md
│   ├── DESIGN_SYSTEM.md
│   └── PAGE_SPEC.md

├── database/
│   ├── SCHEMA.md
│   └── MIGRATION_GUIDE.md

├── testing/
│   ├── QUALITY_GATES.md
│   └── E2E_CASES.md

└── decisions/
    ├── ADR-0001-agent-runtime.md
    ├── ADR-0002-evidence-model.md
    └── ...
```

---

# 113. AGENTS.md 必须写什么

内容：

```text
Project goal
Architecture rules
Files to read before editing
Do not break list
Database migration rules
Tool rules
Skill rules
Frontend rules
Testing requirements
Commands
Definition of Done
```

---

# 114. Codex 修改代码前必须执行

顺序：

```text
1. Read AGENTS.md
2. Read relevant architecture doc
3. Inspect current implementation
4. Identify affected tests
5. Write/change tests when applicable
6. Implement smallest scoped change
7. Run tests
8. Report changed files
9. Update docs if contract changed
```

---

# 115. Codex 禁止行为

禁止：

```text
“顺便重构”
“顺便统一”
“顺便优化”
```

除非任务明确要求。

禁止：

- 自行加入新框架
- 自行加入新 Agent
- 自行创建大 Tool
- 自行重命名 public API
- 修改数据库无 migration
- 删除旧字段无兼容方案
- 把多个业务域塞入一个 Python 文件
- 新增 UI 但没有用户流程
- 新增按钮但后端能力未闭环
- 只写 Happy Path

---

# 116. 每个 Tool 的 Definition of Done

必须：

- 明确用户/Agent用途
- ToolSpec
- Pydantic input
- ToolResult
- ownership check
- permission level
- timeout
- retry policy
- idempotency strategy
- cancel behavior
- unit test
- trace
- docs
- no hidden large side effects

---

# 117. 每个 Skill 的 Definition of Done

必须：

- skill.yaml
- SKILL.md
- allowed tools
- budget
- permissions
- when to use
- when not to use
- completion criteria
- failure strategy
- eval cases
- version

---

# 118. 每个页面的 Definition of Done

必须：

- 有明确用户任务
- empty state
- loading state
- error state
- success state
- keyboard basic accessibility
- no dead button
- no placeholder fake data
- API error handled
- responsive basic support
- analytics/trace hook optional

---

# 119. PR / AI Task 粒度

每次 Codex 任务应该类似：

正确：

```text
实现 AgentExecution 数据模型和 migration。
不要实现 Tool Runtime。
```

正确：

```text
拆分 literature_research.py 中的 external search 和 project search Tool。
保持行为兼容。
```

错误：

```text
把整个 Agent 系统重构好。
```

---

# 120. 推荐实施 PR 顺序

```text
PR-01  Baseline + Alembic
PR-02  Execution models
PR-03  Event persistence + SSE v2
PR-04  Tool contract/runtime
PR-05  Migrate read-only paper tools
PR-06  Migrate external literature tools
PR-07  Skill manifest/runtime
PR-08  Literature research skill migration
PR-09  Evidence model
PR-10  Memory/Notes model
PR-11  Frontend task store
PR-12  Project workspace routing split
PR-13  Discover UX
PR-14  Notes/Evidence UX
PR-15  Reading integration
PR-16  Writing document schema
PR-17  TipTap
PR-18  Citation/evidence integration
PR-19  AI writing diff
PR-20  CI + Playwright gate
```

---

# 121. 兼容策略

旧：

```text
/api/v1/chat/...
```

短期保留。

内部：

```text
chat request
→ ExecutionService
```

旧 ChatMessage 数据继续读取。

新 Execution 不强行塞进 ChatMessage。

---

# 122. 数据迁移策略

ResearchProject.memory：

```text
Old JSON
```

迁移：

```text
migration script
→ memory_items
```

在迁移完成前：

读取：

```text
new memory_items + fallback legacy JSON
```

写入：

```text
only new memory_items
```

---

# 123. Writing 兼容

旧 WritingArtifact：

保留展示和下载。

新正式 manuscript：

使用 WritingDocument。

不要自动把所有旧 artifact 转 document。

只有明确类型是 manuscript/draft 时提供人工迁移。

---

# 124. Chroma 策略

第一阶段不替换。

新增 metadata：

```text
user_id
paper_id
embedding_version
chunk_version
```

如果历史 collection 缺字段：

采用兼容 filter / reindex script。

---

# 125. 外部论文去重

导入 Project 前至少比较：

```text
DOI
arXiv ID
normalized title
```

不要只按 title raw string。

---

# 126. 外部论文可信度

外部 provider 返回的：

- citation count
- venue
- year
- author

只能作为 metadata。

Agent 不允许根据“citation count 高”自动声明：

```text
最权威
```

---

# 127. Research Artifact

保留 generic artifact：

适合：

- research brief
- reading plan
- comparison matrix
- literature review report
- research gap report

Artifact 必须记录：

```text
source_execution_id
skill_id
skill_version
created_at
```

---

# 128. Agent 输出标准

长任务完成后最终用户结果：

```text
Result

Key findings

Evidence

What changed in project

Recommended next actions
```

例如：

```text
完成了 Agent Memory 初步文献调研。

Key findings
1. ...
2. ...

Evidence
12 core papers
8 saved findings

Project changes
Added 6 papers
Saved 8 research notes

Next
1. Compare adaptive retrieval methods
2. Read paper X
```

---

# 129. 禁止无效 Agent 输出

禁止：

```text
我已经为你分析了相关内容。
```

禁止：

```text
以下是一些可能的建议……
```

却没有真实检索或 Evidence。

禁止：

```text
我调用了多个工具……
```

用户不关心。

---

# 130. Topic Exploration 完成标准

只有同时满足：

- 至少有实际论文搜索
- 至少 3 个方向
- 每个方向有 representative papers
- 每个方向有明确 problem
- 有 feasibility
- 有 risk
- 有 gap evidence

才标记 completed。

否则：

```text
partial
```

并说明缺什么。

---

# 131. Literature Review 完成标准

必须：

- search scope
- representative paper set
- theme cluster
- consensus
- conflict
- limitation
- open question
- evidence

否则不要生成“完整综述”标签。

---

# 132. Writing 完成标准

AI 写作建议必须：

- 使用 project context
- 标出引用依据
- 不虚构 citation
- 无 evidence 时明确指出
- 默认不覆盖用户正文

---

# 133. 用户价值优先级

P0：

- 不破坏现有功能
- Agent task 稳定
- Evidence 可追踪
- Notes 可沉淀

P1：

- Topic
- Literature Review
- Deep Reading
- Writing Evidence

P2：

- Advanced comparison
- automated research map
- critique
- parallel reading

不要 P2 抢在 P0 前面。

---

# 134. 第一版不做的功能

- 复杂知识图谱 UI
- 自动整篇论文“一键生成”
- 通用浏览器 Agent
- Shell Tool
- Code execution Tool
- 通用 MCP 市场
- 10 个 SubAgent
- 实时多人协同
- 复杂 citation manager 替代 Zotero
- 学术社交

---

# 135. 性能目标

第一版建议：

普通 Paper QA：

```text
first useful response < 3~5s（取决于模型）
```

复杂 Research Task：

用户 1 秒内看到：

```text
Task started
```

5 秒内看到第一条有意义 Activity。

长任务允许几分钟，但必须：

- 可离开页面
- 可恢复
- 可取消
- 有进度
- 不丢结果

---

# 136. 安全与权限

任何 Tool 执行前必须绑定：

```text
user_id
project_id
execution_id
```

Tool 不允许根据模型传入 user_id。

user_id 来自 runtime context。

---

# 137. 防越权

例如：

```python
paper.get_metadata(paper_id)
```

ToolRuntime：

1. 获取当前 user_id
2. Repository 验证 ownership / project access
3. 再执行

不能只相信 LLM 提供的 ID。

---

# 138. Prompt Injection 基本规则

外部论文、PDF、网页内容全部视为：

```text
untrusted content
```

论文文本中的：

```text
Ignore previous instructions
```

不能成为 Agent 指令。

Tool result 与 system/skill 指令必须逻辑隔离。

---

# 139. 研究内容完整性

Agent 不允许：

- 伪造论文
- 伪造 DOI
- 伪造引用
- 把模型知识假装成检索结果

任何“来自论文”的结论必须能关联 source。

---

# 140. 开发完成后的验收场景

必须实际跑以下端到端。

---

## Scenario 1

```text
创建项目：
Agent Memory
```

Agent：

- 提出必要 clarification 或使用已有 brief
- 搜索论文
- 返回方向
- 可以保存方向

---

## Scenario 2

用户：

```text
帮我系统调研这个方向
```

Agent：

- search
- shortlist
- import
- read
- evidence
- notes
- report

用户离开页面再回来：

task 仍存在。

---

## Scenario 3

打开核心论文。

问：

```text
作者为什么认为当前方法存在局限？
```

答案：

- 有 page
- 有 section
- 点击 source 定位 PDF

---

## Scenario 4

用户将回答保存为 Evidence。

Writing 页面：

Evidence panel 可找到。

---

## Scenario 5

用户写：

```text
Current memory systems have fully solved long-term consistency.
```

Citation Audit：

如果证据不支持：

显示：

```text
Unsupported claim
```

---

## Scenario 6

用户选择段落：

```text
Improve academic style
```

AI：

显示 Diff。

用户 Reject：

原文不能变化。

---

# 141. 开发中断点

如果实现过程中发现：

- 现有模型和本文冲突
- 数据迁移可能丢失
- API compatibility 无法保持
- Tool side effect 无法保证
- 现有测试与设计严重冲突

Codex 不要自行“取舍”。

必须在实现报告中写：

```text
BLOCKER
Current behavior:
Target behavior:
Conflict:
Recommended options:
```

停止扩大修改范围。

---

# 142. Codex 每次任务的输出格式

完成后必须输出：

```text
Implemented

Files changed

Database migrations

API changes

Tests added

Tests run

Backward compatibility

Known limitations

Docs updated
```

不要只说：

```text
已完成。
```

---

# 143. 架构决策原则

遇到两种实现时按以下优先级：

```text
用户价值
>
数据正确性
>
可维护性
>
可测试性
>
可观测性
>
开发速度
>
“技术看起来高级”
```

---

# 144. 最终目标架构

```text
                       Vue Research Workspace
                                 │
                                 │ REST / SSE
                                 ▼
                           FastAPI API
                                 │
                   ┌─────────────┼─────────────┐
                   ▼             ▼             ▼
             Application     Conversation   Execution
               Services        Service       Service
                   │                             │
                   │                             ▼
                   │                      Agent Runtime
                   │                    ┌───────┼────────┐
                   │                    ▼       ▼        ▼
                   │                 Context   Skill    Policy
                   │                    │       │
                   │                    └───┬───┘
                   │                        ▼
                   │                    Tool Runtime
                   │                        │
                   ├────────────────────────┤
                   ▼                        ▼
             Research Domain          Workflows
        Project / Evidence / Memory    QA / Parse / Audit
             / Writing                     │
                   │                        │
                   └────────────┬───────────┘
                                ▼
                         Infrastructure
                 PostgreSQL / Redis / Chroma
                 Files / arXiv / Semantic Scholar
```

---

# 145. 最重要的产品判断

PaperAI 最终不应该成为：

```text
一个拥有很多 AI 按钮的论文网站
```

也不应该成为：

```text
一个把所有操作都交给 Agent 的自动化系统
```

正确形态是：

> **用户拥有 Research Workspace，Agent 在需要不确定决策、跨论文调研、证据组织和写作辅助时介入；确定性工作仍由稳定 Workflow 完成。**

---

# 146. 对 Codex 的最终执行要求

不要一次执行本文全部内容。

从 Phase 0 开始。

每个 Phase：

1. 阅读对应文档。
2. 检查现有代码。
3. 生成最小变更计划。
4. 只实施当前 Phase。
5. 跑测试。
6. 输出变更报告。
7. 等待下一任务。

未经明确要求，不要自行进入下一 Phase。

---

# 147. 第一条建议执行指令

本文进入仓库后，第一条给 Codex 的任务应该是：

```text
阅读：
- AGENTS.md
- docs/PROJECT_AGENT_IMPLEMENTATION_SPEC.md
- docs/PROJECT_AGENT_UPGRADE_CONTEXT.md

当前只执行 Phase 0 和 Phase 1 的准备分析。

不要修改 Agent Runtime、Tool、Skill 或前端业务。

任务：
1. 检查当前 Git 工作区和未提交 Agent 代码。
2. 给出安全 WIP baseline 方案。
3. 检查现有 SQLAlchemy schema 和数据库初始化方式。
4. 设计 Alembic baseline 迁移方案。
5. 列出可能影响现有 PostgreSQL 数据的风险。
6. 给出具体文件级修改计划。
7. 暂时不要执行数据库破坏性修改。

输出：
docs/migrations/ALEMBIC_BASELINE_PLAN.md
```

先让 Codex 设计 migration baseline，再开始第一批代码变更。

---

# 148. 文档维护规则

本文是顶层实施规范。

如果实际实现与本文发生变化：

必须：

1. 创建 ADR。
2. 写明原因。
3. 更新相关 specification。
4. 再修改代码。

禁止代码长期偏离文档。

---

# 149. 成功标准

这次升级成功不是：

```text
Agent 有更多 Tool
```

而是用户可以真正完成：

```text
模糊想法
↓
找到研究方向
↓
找到论文
↓
理解领域
↓
形成研究问题
↓
积累 Evidence / Notes
↓
阅读核心论文
↓
形成论文结构
↓
带证据写作
↓
检查引用和论点
```

同时系统具备：

```text
可恢复
可追踪
可测试
可迁移
可回滚
可理解
```

这才是 PaperAI Research Agent v1 的完成标准。
