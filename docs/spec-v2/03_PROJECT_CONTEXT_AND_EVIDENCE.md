# PaperAI V1 Project Context and Evidence Specification

> 文档状态：ACTIVE / AUTHORITATIVE  
> 版本：v2.0-draft  
> 适用对象：Codex、AI Coding Agent、PaperAI 开发者  
> 本文定义 PaperAI V1 的 Project Context、Memory、Paper Profile、Evidence、Retrieval 与 Citation Verification 的具体实现规则。  
> 产品范围见 `00_PRODUCT_SCOPE.md`，总体分层见 `02_TARGET_ARCHITECTURE.md`。

---

# 0. 核心目标

V1 的 Context 系统必须解决三个问题：

1. Agent 能长期理解“这个 Project 在研究什么”。
2. Agent 能快速知道“用户已经导入并读过哪些论文，这些论文大致讲什么”。
3. Writing Agent 能从真实论文正文中找到可追溯证据，并用它生成可验证引用。

Context 系统不是聊天历史存储系统。

---

# 1. 核心概念

V1 将上下文分为五类：

```text
Project Context
├── Project Profile
├── Literature Memory
├── Paper Profiles
├── Evidence
└── Writing Context
```

这些概念必须保持语义分离。

---

# 2. Project Profile

## 2.1 用途

Project Profile 回答：

> 当前 Project 到底在研究什么？

它应该是所有 Project 级 Agent 最稳定、最常用的一层上下文。

## 2.2 建议字段

```text
project_id
title
research_topic
field
research_subject
research_question
research_goal
keywords
method_direction
user_notes
updated_at
```

只有：

- `title`
- `research_topic`

是创建时必填。

其余均可选。

## 2.3 更新规则

Project Profile 核心字段不可由 Agent 静默自动修改。

允许 Agent：

- 发现研究范围发生明显聚焦
- 生成更新建议
- 提示用户确认

用户确认后再持久化。

V1 不要求主动建议更新，但架构不得阻止未来加入。

---

# 3. Literature Memory

## 3.1 用途

Literature Memory 记录“文献发现阶段具有长期价值的信息”。

不是搜索日志仓库。

## 3.2 可以保存

建议保存：

```text
search_intent_summary
important_keywords
preferred_directions
excluded_directions
important_search_notes
favorite paper ids
imported paper ids
```

## 3.3 不保存

不长期保存：

- 每一轮所有搜索结果 JSON
- 每一个 provider 原始 response
- 每一次临时 ranking score
- Agent 的 raw reasoning
- 每一轮 query 的完整中间过程

这些可进入 execution log / transient cache。

## 3.4 触发写入

建议触发：

- 一次 Discover session 最终确认 Search Intent
- 用户明确收藏论文
- 用户明确导入论文
- 用户明确排除某个方向

V1 第一版不需要每轮对话自动抽取 Literature Memory。

---

# 4. Paper Profile

## 4.1 定义

Paper Profile 是已导入论文的轻量结构化学术摘要。

它回答：

> 这篇论文是什么、研究了什么、什么时候值得被检索？

Paper Profile 不是引用证据。

## 4.2 来源

只对：

> 已正式导入并成功解析的 Project Paper

生成 Paper Profile。

Discover 搜索结果和单纯收藏论文不生成。

## 4.3 建议字段

```text
paper_id
project_id

topic
research_questions[]
research_subjects[]
methods[]
datasets_or_samples[]
main_results[]
conclusions[]
contributions[]
limitations[]
keywords[]
project_relevance

source_model
profile_version
generated_at
```

## 4.4 与现有代码的关系

优先演化：

```text
ProjectPaper.analysis_card
```

不新建重复的 PaperMemory / PaperProfileV2 表，除非现有 JSON 结构无法满足：

- version
- status
- provenance
- regeneration

若使用 `analysis_card`，必须定义稳定 schema。

---

# 5. Paper Profile 自动生成

## 5.1 是否自动生成

V1：自动生成。

原因：

- 提高 Writing Retrieval 稳定性
- 避免每次写作都重新读全文
- 降低 LLM 成本
- 便于先筛候选论文再检索 chunk

## 5.2 触发时机

```text
PDF import
  ↓
parse completed
  ↓
chunk/index completed
  ↓
PaperProfileGenerationWorkflow
```

## 5.3 异步规则

Paper Profile 生成失败不得阻塞：

- Reader
- Project Papers
- 原有 QA

失败状态必须可重试。

建议状态：

```text
pending
generating
ready
failed
stale
```

## 5.4 生成输入

优先使用：

- title / abstract
- section headings
- introduction
- methods
- results
- conclusion
- representative chunks

不得为了 Profile 默认把超长全文全部塞给一个模型。

## 5.5 Profile 质量

Prompt 必须要求：

- 不推断论文没有明确说明的内容
- 缺失字段为空
- 结果结构化
- 研究结果与作者结论区分
- 不生成虚构 DOI / dataset / sample

---

# 6. Ordinary Conversation History

## 6.1 与 Project Memory 分离

普通对话历史可以继续持久化用于：

- 会话恢复
- UI 展示
- 当前对话连续性

但：

```text
conversation_history != project_memory
```

## 6.2 V1 默认不自动长期吸收

例如：

```text
“SEM 是什么意思？”
```

不应进入长期 Project Context。

V1 不实现每轮聊天后再调用一个“memory extractor”自动决定是否永久记忆。

这样可减少：

- 成本
- 错误记忆
- 噪声
- 难以删除的模型误判

---

# 7. 用户笔记 / 高亮

用户已明确要求 V1 不改 Reader。

因此：

- 不新增复杂高亮系统
- 不新增必做“保存为 Evidence”按钮
- 不以此阻塞 V1

如果现有 Reader / QA 已有可靠用户笔记或证据数据：

- 可以进入 Context Retrieval
- 用户主动保存内容权重高于 AI 自动摘要

---

# 8. Evidence

## 8.1 定义

Evidence 表示：

> 来自真实已导入论文、可追溯到原始位置、可以支持某个学术主张的证据对象。

## 8.2 必须关联

至少：

```text
evidence_id
project_id
paper_id
chunk_id
snippet
normalized_claim
```

可用时：

```text
section_id
page_number
bbox
doi
```

## 8.3 建议扩展字段

在现有 `EvidenceItem` 基础上考虑增加：

```text
source_type
status
created_by
verification_status
verification_reason
verification_model
verification_version
created_at
updated_at
```

建议：

```text
source_type:
- retrieval_generated
- user_saved
- imported_existing

status:
- active
- stale
- invalid

verification_status:
- unverified
- verified
- weak
- unsupported
```

具体 migration 在 implementation plan 定义。

---

# 9. Evidence 不做全量预生成

V1 不在论文导入时对整篇论文生成几十 / 几百条 Evidence。

原因：

- 成本高
- 大量证据永远用不到
- claim 依赖实际写作需求
- 很容易生成低价值 Evidence

V1 采用：

> Paper Profile 预生成 + Evidence 按需检索 / 生成。

---

# 10. Writing 时的 Evidence Retrieval

标准流程：

```text
Writing Instruction
    ↓
Build Retrieval Need
    ↓
Select Candidate Papers
    ↓
Search Chunks within Candidate Papers
    ↓
Create Evidence Candidates
    ↓
Validate Provenance
    ↓
Use for Generation
```

---

# 11. Candidate Paper Selection

Writing Agent 不应先对当前项目所有论文全文做一次全局大检索。

优先：

```text
Project Profile
+
Writing Instruction
+
Current Section
    ↓
Paper Profile Retrieval
    ↓
Top Candidate Papers
```

建议 V1 默认候选：

```text
3–5 papers
```

实际数量可根据结果动态收缩，但不宜默认拉取所有 Project Papers。

---

# 12. Paper Profile Retrieval

可组合：

- keyword match
- lexical search
- embedding on serialized profile
- current section semantic query

不要单纯依赖 LLM“看所有 profile 后选”。

如果 Project 论文很少，V1 可以先采用：

```text
deterministic shortlist + model rerank
```

---

# 13. Chunk Retrieval

对 Candidate Papers 使用现有 Hybrid Retrieval。

必须支持 filter：

```text
project_id
paper_id IN candidate_paper_ids
```

输入 query 可由 Writing Need 生成。

返回至少：

```text
paper_id
chunk_id
section_id
page_number
text
retrieval_score
```

---

# 14. Evidence Candidate

Chunk 不等于最终 Evidence。

需要形成：

```text
claim
source_chunk
paper
support_relation
```

建议内部 DTO：

```python
class EvidenceCandidate:
    paper_id: str
    chunk_id: str
    snippet: str
    page_number: int | None
    normalized_claim: str | None
    retrieval_score: float | None
```

---

# 15. Evidence Persistence

不是每个 Retrieval Chunk 都必须持久化为 `EvidenceItem`。

建议：

- 仅实际参与生成的 Evidence 持久化
- 通过 Citation Verification 的优先持久化
- 未使用候选可保持 transient

这样数据库不会堆积大量无用证据。

---

# 16. Writing Context

Writing Context 是一次 Writing Agent 请求的临时上下文组合。

它不是独立长期记忆表。

建议结构：

```text
project_profile
document_id
current_section_title
current_section_path
selection
nearby_text
instruction
candidate_paper_profiles
evidence
citation_style
```

---

# 17. Context Manager

## 17.1 职责

`ProjectContextManager` 负责：

- 根据 use case 获取合适 Context
- 控制上下文规模
- 构造稳定 DTO
- 不生成最终用户文本

## 17.2 API 形态建议

```python
async def build_discovery_context(
    project_id: str,
) -> DiscoveryContext:
    ...

async def build_writing_context(
    project_id: str,
    document_id: str,
    section_context: SectionContext,
    instruction: str,
    selection: str | None,
) -> WritingContext:
    ...
```

## 17.3 禁止

禁止：

```python
project.memory + str(project.papers) + all_messages
```

这种粗暴字符串拼接。

---

# 18. Token Budget

Context Manager 必须控制 token budget。

优先级建议：

## Writing

1. 用户 instruction
2. selection
3. current section title / path
4. nearby text
5. Project Profile
6. verified Evidence
7. candidate Paper Profiles
8. lower-priority memory

超预算时先丢低优先级内容。

不得截断用户 instruction 或 Evidence source identity。

---

# 19. Literature Memory Retrieval

Discover 时最多读取：

- 当前 Project Profile
- 最近确认的搜索意图
- 重要排除方向
- 重要关键词

不把整个历史 Discover 对话塞入 Agent。

---

# 20. Citation Mapping

Writing generation 输出必须结构化。

建议：

```python
class WritingProposal:
    content: str
    citations: list[GeneratedCitation]
    warnings: list[str]
```

```python
class GeneratedCitation:
    citation_key: str
    paper_id: str
    evidence_id: str
    claim_text: str
```

禁止仅返回：

```text
xxxx [1][2]
```

然后让前端猜论文。

---

# 21. Citation Node

继续复用现有 Tiptap Citation Node。

Node 中至少保持：

```text
paper_id
citation_key
evidence_id
```

如果现有 node 已兼容，则不改 schema。

---

# 22. Citation Verification Workflow

V1 固定步骤：

```text
Generated Claim + Citation
      ↓
Referential Integrity
      ↓
Evidence Validation
      ↓
Support Check
      ↓
verified / weak / unsupported
```

Agent 不能选择跳过。

---

# 23. Referential Integrity Check

完全确定性。

检查：

```text
project exists
paper exists
paper belongs to current project
evidence exists
evidence belongs to current project
evidence.paper_id == citation.paper_id
chunk provenance still exists
```

任何失败：

```text
unsupported
```

无需 LLM。

---

# 24. Lexical / Retrieval Gate

保留现有 citation audit / lexical gate 作为快速异常检测。

用途：

- 完全不相关
- claim 中关键词与 evidence 毫无交集
- 错 paper
- source chunk 空

它只是一层 gate。

不能作为最终“学术事实成立”的唯一依据。

---

# 25. Semantic Support Verifier

## 25.1 任务

判断：

> 给定 Evidence，是否足以支持 Generated Claim？

## 25.2 输入

只给 verifier：

- claim
- source snippet
- 必要前后文
- paper metadata

不要给 verifier 整个 Project。

## 25.3 输出

严格结构化：

```json
{
  "status": "verified",
  "reason": "...",
  "confidence": 0.86
}
```

status：

```text
verified
weak
unsupported
```

## 25.4 Prompt 原则

Verifier 不是“帮作者辩护”。

必须偏保守：

- 支持强度不足 → weak
- Evidence 没说 → unsupported
- 相关但不能证明因果 → 不允许验证因果 claim
- correlation 不等于 causation
- abstract 中未报告的具体数字不得自动补充

---

# 26. Claim Strength Adjustment

如果 verifier 返回 `weak`，可选 workflow：

```text
claim too strong
  ↓
LLM rewrite claim more conservatively
  ↓
verify again
```

最大重试必须有限。

如果仍失败：

- 返回 warning
- 不标记 verified

---

# 27. Multiple Citations

一个 claim 可以由多个 Evidence 共同支持。

必须逐个 Citation 验证，并允许组合支持。

V1 不要求复杂逻辑证明系统。

但至少：

- 不能有一个 unsupported citation 混入 verified bundle 而不提示
- 用户可查看每个 citation 的验证状态

---

# 28. Evidence Invalidation

以下变化可能使 Evidence stale：

- Paper 被移出 Project
- PDF 被重新解析且 chunk ids 重建
- source chunk 删除
- Paper metadata / document version变化
- Evidence verifier 版本重大变化（可选择重新验证）

最重要：

Paper 被移出 Project 后，其 Evidence 不得继续作为当前 Project Writing 的有效引用来源。

---

# 29. Paper Profile Invalidation

以下变化可标记 stale：

- PDF 重新解析
- profile schema version 变化
- profile generator major version 变化

stale profile：

- Reader 仍可用
- Writing 检索可以降权
- 后台允许重新生成

---

# 30. Context Provenance

所有长期自动生成信息建议记录：

```text
source
model
version
created_at
```

至少 Paper Profile 和 semantic verifier 需要。

目的是：

- 调试
- 重生成
- 版本迁移
- 质量追踪

---

# 31. 数据持久化建议

## 31.1 Project Profile

优先直接扩展 `ResearchProject` / structured preferences。

不要再建一个只有 1:1 的 ProjectProfile 表，除非 schema 演化确实需要。

## 31.2 Literature Memory

可继续使用 `MemoryItem`，但必须增加稳定 type / schema。

例如：

```text
literature_search_intent
literature_preference
literature_exclusion
```

普通聊天禁止全部写入。

## 31.3 Paper Profile

优先使用 `ProjectPaper.analysis_card`。

## 31.4 Evidence

继续使用 `EvidenceItem`。

## 31.5 Writing Context

不持久化为长期 Memory。

---

# 32. MemoryItem 类型约束

如果继续使用现有 `MemoryItem`，V1 必须明确允许类型。

例如：

```text
project_decision
literature_intent
literature_preference
literature_exclusion
```

不允许：

```text
generic
conversation
random_note
agent_thought
```

无限扩散。

---

# 33. Project Context 查询优先级

Writing Retrieval 推荐权重：

```text
1. Verified Evidence
2. 用户明确保存的信息（如现有系统已有）
3. Paper Profile
4. Paper Full-text Retrieval
5. Literature Memory
6. Ordinary chat history
```

普通聊天默认最后，甚至 V1 可以完全不进入 Writing retrieval。

---

# 34. No Imported Papers

若 Writing Agent 需要真实引用，但 Project 没有已导入论文：

返回明确状态：

```text
NO_IMPORTED_PAPERS
```

用户提示：

> 当前项目还没有可用于引用的已导入论文。

不允许：

- 去模型记忆找引用
- 自动联网搜索并引用
- 虚构 paper metadata

---

# 35. No Relevant Evidence

如果有论文但没有 Evidence 支持：

返回：

```text
NO_SUPPORTING_EVIDENCE
```

可以：

- 生成无引用的普通写作建议（只有用户请求允许时）
- 提示“当前项目资料不足以可靠支持该表述”

不能假引用。

---

# 36. Rewrite 与 Citation

## 36.1 Selection 没 citation

普通润色：

- 不强制检索 Evidence
- 不强制添加引用

## 36.2 Selection 有 citation

Rewrite 必须保持 citation 语义。

如果改写导致 claim 发生实质变化：

- citation 需重新验证
- 如果无法支持，标记 warning

## 36.3 用户要求“添加引用”

强制进入 Evidence Retrieval + Citation Verification。

---

# 37. Citation Style

Citation style 只影响渲染。

支持：

- GB/T 7714
- APA
- IEEE

Context / Evidence 不存最终格式化字符串作为唯一真值。

底层关联：

```text
paper_id
citation_key
evidence_id
```

---

# 38. Reference Metadata

用于格式化参考文献的 Paper metadata 至少需要：

```text
title
authors
year
venue
doi
url
```

缺字段时格式器应优雅降级，不得让 Agent补造。

---

# 39. API Contracts

后续至少需要支持以下 Context / Evidence 类接口或内部 use case：

```text
GET Project Profile
UPDATE Project Profile

GET Paper Profile
REGENERATE Paper Profile

GET Evidence for citation
VERIFY Citation

Writing Agent proposal
```

不要求全部暴露给前端。

内部 service 可以先存在。

---

# 40. Background Jobs

Paper Profile 适合后台任务。

Evidence Retrieval 不适合默认异步后台慢任务，因为 Writing 用户等待生成结果。

建议：

```text
Paper Profile → worker/background
Writing Evidence Retrieval → request workflow
```

---

# 41. Performance

Writing 一次请求不应：

- 加载所有 Paper full text
- 对所有 Paper 做 LLM summarization
- 重新生成所有 Paper Profile
- 扫描所有 conversation

应控制：

```text
candidate papers: ~3–5
evidence chunks: limited top-k
verifier calls: only citations actually used
```

---

# 42. Observability

每次 Writing Generation 建议记录：

```text
project_id
document_id
candidate_paper_count
retrieved_chunk_count
used_evidence_count
verified_count
weak_count
unsupported_count
duration
```

不得记录 chain-of-thought。

---

# 43. Tests

## Paper Profile

必须测试：

- parse completed triggers profile
- failure does not break Reader
- empty fields allowed
- regeneration
- profile version

## Context Manager

必须测试：

- no project
- no papers
- token limit
- candidate restriction
- no chat dump

## Evidence

必须测试：

- cross-project evidence rejected
- wrong paper evidence rejected
- stale evidence rejected
- invalid chunk rejected

## Citation Verification

必须测试：

- valid mapping
- paper not in project
- evidence mismatch
- lexical fail
- semantic weak
- unsupported
- verifier timeout

## Writing

必须测试：

- no imported papers
- no evidence
- verified citation proposal
- rewrite preserves citations

---

# 44. Migration from Current Code

## `ResearchProject.memory`

如果当前仍有自由文本 / JSON memory：

- 不立即删除
- 新代码停止把所有 context 塞进去
- 建立 typed access
- 后续 migration 决定是否拆分

## `MemoryItem`

保留表，收紧 type。

## `ProjectPaper.analysis_card`

升级 schema 为 Paper Profile。

## `EvidenceItem`

保留，补 provenance / verification。

## `lead_agent.py` Project Context

旧的直接字符串拼接路径必须逐步停止使用。

新增 Context Manager 后，业务 workflow 不再自行拼接 memory + papers + artifacts。

---

# 45. Recommended Implementation Components

建议最终新增 / 调整：

```text
backend/app/research/context/
├── schemas.py
├── manager.py
├── paper_profile.py
├── paper_profile_generator.py
└── selectors.py

backend/app/research/evidence/
├── schemas.py
├── retrieval.py
├── service.py
└── verifier.py
```

如果现有目录结构更适合放入 `application/` / `services/`，可以调整。

核心是职责，不是目录名称。

---

# 46. Context DTO Example

```python
@dataclass
class WritingContext:
    project_id: str
    project_profile: ProjectProfileDTO
    document_id: str
    section_title: str | None
    section_path: list[str]
    selection: str | None
    nearby_text: str | None
    candidate_papers: list[PaperProfileDTO]
    evidence: list[EvidenceDTO]
    citation_style: str
```

不直接放 ORM model。

---

# 47. Evidence DTO Example

```python
@dataclass
class EvidenceDTO:
    evidence_id: str
    project_id: str
    paper_id: str
    chunk_id: str
    snippet: str
    page_number: int | None
    section_id: str | None
    normalized_claim: str | None
    verification_status: str
```

---

# 48. Citation Verification DTO

```python
@dataclass
class CitationVerificationResult:
    citation_key: str
    paper_id: str
    evidence_id: str
    status: Literal["verified", "weak", "unsupported"]
    reason: str
    confidence: float | None
```

---

# 49. 用户可见状态

内部 Context 复杂度不应暴露。

Writing UI 只需要类似：

```text
正在读取项目资料
正在查找相关论文
正在查找支持证据
正在生成内容
正在验证引用
```

失败：

```text
当前已导入论文中没有找到足够证据支持这项表述。
```

不要显示：

```text
embedding top_k=8
rerank score=0.83
MemoryItem type=...
```

---

# 50. 最终原则

必须长期遵守以下区分：

```text
Project Profile
= 用户在研究什么

Literature Memory
= 用户找论文时逐渐明确了什么

Paper Profile
= 这篇论文大致讲什么

Evidence
= 论文哪里真正支持某个主张

Writing Context
= 这一次写作请求真正需要什么
```

如果这五层重新混成一个 `memory` 字符串，V1 Context 架构即视为失败。

---

# 51. V1 验收场景

## Scenario 1

Project 有 8 篇已导入论文。

用户：

```text
根据我读过的论文写一段生成式 AI 对大学生自主学习积极影响的研究现状。
```

系统必须：

1. 获取 Project Profile。
2. 根据 Paper Profile 选择相关论文。
3. 只在候选论文范围检索全文 chunk。
4. 形成 Evidence。
5. 生成一段正文。
6. 生成结构化 Citation Mapping。
7. Verification。
8. 只将通过或带明确 warning 的结果返回。

## Scenario 2

Project 没有任何导入论文。

系统必须明确提示无法生成“基于当前项目真实论文引用”的内容。

## Scenario 3

模型生成了一个强因果表述，但 Evidence 只有相关性。

Verifier 必须返回 `weak` 或 `unsupported`，不得标记 verified。

## Scenario 4

Paper 被移出 Project。

它过去的 Evidence 不得继续作为当前 Project 的有效引用来源。

---

# 52. Definition of Done

本规格完成实施后，必须满足：

- Project Context 不再等于长 Prompt。
- Ordinary chat 不自动污染长期 Memory。
- 已导入论文自动具备可检索 Paper Profile。
- Writing 不需要每次重新读全部论文。
- Evidence 只来自真实 Project Paper。
- Citation 有 paper / evidence 结构化关联。
- Verification 是固定 workflow。
- unsupported citation 不会作为正常可信输出返回。
- Reader 不因 Context 系统改造而被破坏。
- Context / Evidence 有测试覆盖。
