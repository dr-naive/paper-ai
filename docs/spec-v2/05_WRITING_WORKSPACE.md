# PaperAI V1 Writing Workspace Specification

> 文档状态：ACTIVE / AUTHORITATIVE
> 版本：v2.0-draft
> 适用对象：Codex、AI Coding Agent、PaperAI 开发者
> 本文定义 PaperAI V1 Writing Workspace 的页面结构、编辑器行为、Writing Agent、选区改写、段落生成、Citation Node、Citation Verification、持久化与导出规则。
> 产品范围见 `00_PRODUCT_SCOPE.md`，Context / Evidence 规则见 `03_PROJECT_CONTEXT_AND_EVIDENCE.md`。

---

# 0. 目标

Writing Workspace 是 PaperAI V1 的核心成果页面之一。

目标不是做一个“AI 生成文本框”，而是提供一个真正可持续写论文的编辑工作区：

```text
论文结构
+
正式富文本编辑器
+
右侧 Writing Agent
+
真实项目论文引用
+
Citation Verification
```

V1 不要求完整复刻 Word，但必须让用户可以在 PaperAI 内持续写正文，而不是最终回到外部编辑器才开始真正写作。

---

# 1. 复用现有资产

当前分支已经具备：

- Tiptap
- WritingDocument
- Revision
- Document rail / Outline 雏形
- AI proposal / diff 雏形
- Citation Node
- citation audit
- Evidence sidebar / citation awareness 基础

V1 必须优先复用。

禁止重新建立：

```text
SecondRichTextEditor
NewDraftSystem
WritingV3Document
CitationTextParserV2
```

除非现有能力经测试无法满足本规格。

---

# 2. Route

建议：

```text
/projects/:projectId/writing
```

Project 内 Writing 只处理当前 Project 的正式文档。

独立 Reader 与此页面分离。

---

# 3. 页面总体布局

Desktop V1：

```text
┌───────────────┬──────────────────────────────────────┬─────────────────────┐
│ 论文结构      │ 正文编辑器                           │ AI 写作助手         │
│               │                                      │                     │
│ Outline       │ Current WritingDocument              │ Context             │
│ Document tree │                                      │ Conversation        │
│               │                                      │ Proposal            │
│               │                                      │                     │
└───────────────┴──────────────────────────────────────┴─────────────────────┘
```

建议：

```text
left: 220px
center: flexible
right: 340–380px
```

右侧 Agent 可折叠。

中心编辑区优先保证宽度。

---

# 4. Layout 原则

1. 不增加第四个常驻侧栏。
2. Citation / Evidence 详情通过 Drawer / Popover / inline detail 展示。
3. AI Agent 不占用编辑器顶部大面积空间。
4. 桌面优先。
5. UI 需要稳定，不因 Agent 状态频繁跳动布局。

---

# 5. 左侧论文结构

左侧负责：

- 当前 WritingDocument
- Outline
- Heading navigation
- 当前章节高亮

第一版不做复杂“论文流程状态”。

建议显示：

```text
摘要
1 绪论
  1.1 研究背景
  1.2 研究意义
2 国内外研究现状
  2.1 ...
3 方法
4 结果
5 结论
```

---

# 6. Outline 数据来源

Outline 应直接来自 Tiptap Document 中的 heading node。

不要维护另一套与正文容易不同步的章节数据库。

如果当前已有 outline extraction，继续复用。

---

# 7. 中间编辑器

继续使用 Tiptap。

正文容器建议：

```text
max-width: 760–860px
```

居中。

用户感觉应接近：

- Notion
- Medium
- Typora

而不是强行模拟分页 Word。

---

# 8. 基础编辑能力

V1 至少需要保留 / 支持：

```text
Paragraph
Heading 1 / 2 / 3
Bold
Italic
Underline（若现有支持）
Blockquote
Ordered list
Bullet list
Link
Undo
Redo
```

根据现有插件能力可保留：

```text
Image
Table
Code block
```

论文增强：

```text
Citation
Formula
Footnote（可后置小阶段）
Figure/Table Caption（可后置小阶段）
```

---

# 9. 工具栏

工具栏保持简洁。

不允许：

- 30+ 固定 AI 按钮
- “润色 / 扩写 / 缩写 / 学术化 / 翻译 / 改语气...” 全部堆在 toolbar

AI 行为统一由右侧 Writing Agent 承担。

---

# 10. 右侧 Writing Agent

定位：

> 根据当前编辑器上下文、Project Context 与用户指令提供写作帮助。

它不是普通独立 Chat。

必须能感知：

- project_id
- document_id
- current heading / section path
- selection
- nearby text
- citation style

---

# 11. Context Badge

右侧输入区上方显示轻量 Context。

无 selection：

```text
当前：2.1 国内外研究现状
```

有 selection：

```text
当前：2.1 国内外研究现状
已选中 126 字
```

这是用户对“AI 当前看到了什么”的最低可见反馈。

---

# 12. Selection State

Editor 需要稳定向 `writingStore` 暴露：

```text
selection_from
selection_to
selected_text
current_heading
section_path
```

Selection 变化时更新，但不要每次 selection change 都触发后端调用。

---

# 13. 两种主要 Agent 行为

V1 不要求显式“模式切换”。

系统根据是否存在 selection 自动进入：

```text
Rewrite Context
或
Generate Context
```

---

# 14. 有 Selection：Rewrite

示例：

用户选中一段正文。

输入：

```text
帮我润色得更学术，但不要改变原意。
```

后端接收：

```text
project
document
section
selection
nearby text
instruction
```

返回 Proposal。

---

# 15. Rewrite 默认行为

普通润色 / 改写：

- 不强制搜索新 Evidence
- 不强制添加引用
- 不自动改正文
- 不自动删除已有 Citation

如果 selected content 已有 Citation Node：

必须保持 citation mapping 或重新验证。

---

# 16. Rewrite 输出

建议：

```python
class WritingRewriteProposalDTO:
    proposal_id: str
    content: str
    citations: list[CitationMappingDTO]
    warnings: list[str]
```

前端固定动作：

```text
[替换选中内容] [复制]
```

---

# 17. 替换选中内容

必须由用户点击。

点击后：

1. 验证 selection anchor 是否仍然有效。
2. 若 selection 已变化，禁止直接替换。
3. 提示：
   `选中的内容已经变化，请重新选择后重试。`
4. 成功后生成 revision / dirty state。
5. 保留可撤销能力。

---

# 18. Copy

使用系统 clipboard。

复制内容时：

- 纯文本 copy 可作为默认
- 若需要包含 citation rich nodes，可提供富文本 copy（后续）
- V1 至少保证文字不会丢失

---

# 19. 无 Selection：Generate Paragraph

示例：

```text
根据我导入的论文，写一段生成式 AI 对大学生自主学习积极影响的研究现状。
```

系统必须基于：

```text
Project Profile
Current Section
Nearby Text
Paper Profiles
Evidence
```

生成。

---

# 20. Generate 默认粒度

V1 的目标粒度：

> 一段内容。

不默认生成：

- 整章
- 整篇
- 完整毕业论文

如果用户请求过大：

Agent 应拆小或提示一次生成范围过大。

---

# 21. Generate Workflow

固定：

```text
Receive instruction
    ↓
Build Writing Context
    ↓
Select Candidate Papers
    ↓
Retrieve Evidence
    ↓
Generate Paragraph
    ↓
Build Citation Mapping
    ↓
Citation Verification
    ↓
Return Proposal
```

Agent 不允许绕过 Verification。

---

# 22. Generate Result

建议 DTO：

```python
class WritingGenerationProposalDTO:
    proposal_id: str
    content: str
    citations: list[CitationMappingDTO]
    verification: list[CitationVerificationDTO]
    warnings: list[str]
```

前端至少：

```text
[复制]
```

V1 不强制“插入光标位置”。

---

# 23. 为什么第一版只复制

原因：

- 行为安全
- 用户保留最终控制
- 减少自动插入后 selection / cursor / citation node 错位
- 产品当前已明确此方案

未来可增加：

```text
[插入到光标]
```

但不是 V1 必需。

---

# 24. Citation Source

自动生成引用只允许来自：

```text
current Project
+
imported ProjectPaper
+
parse/index ready
+
retrievable Evidence
```

不得引用：

- Discover result 未导入论文
- Favorite metadata
- 模型记忆论文
- 网页
- 用户未导入文献

---

# 25. Citation Mapping

不得靠正文字符串中的：

```text
[1]
```

作为唯一结构。

每个 citation 必须返回：

```text
citation_key
paper_id
evidence_id
claim_text
verification_status
```

---

# 26. Tiptap Citation Node

继续复用现有 Citation Node。

建议最终 attribute：

```text
paper_id
citation_key
evidence_id
```

如现有 node 额外字段已稳定，可保留。

---

# 27. Citation Rendering

Citation style 第一版支持：

```text
GB/T 7714
APA
IEEE
```

显示与内部结构解耦。

例如内部：

```text
paper_id = p123
```

APA 显示可为：

```text
(Zhang et al., 2024)
```

IEEE 可为：

```text
[3]
```

切换 style 不重生成正文。

---

# 28. Citation Interaction

用户点击 Citation Node：

打开轻量 Popover / Drawer：

```text
论文标题
作者
年份
Evidence snippet
页码
验证状态
[查看论文]
```

不要默认占用右侧 Agent 常驻区域。

---

# 29. Citation Verification

前端必须显示状态。

建议：

```text
✓ 已验证
△ 证据较弱
! 不支持
```

不能只用颜色。

---

# 30. Verification Failed

如果某 citation unsupported：

Proposal 仍可显示，但必须：

- 明确 warning
- citation node 标记风险
- 不显示“已验证”

若生成流程能够自动修复，则修复后重新验证。

---

# 31. Claim Adjustment

可允许后端在 `weak` 时做一次保守改写。

例如：

```text
原：
研究证明生成式 AI 显著提升学习成绩。

Evidence：
只显示二者存在正相关。

改：
研究发现生成式 AI 使用与学习表现之间存在正向关联。
```

再次验证。

最大 retry 有限。

---

# 32. No Supporting Evidence

如果没有证据：

Writing Agent 应返回：

```text
当前项目已导入论文中没有找到足够证据支持这一表述。
```

可以提供：

- 一般写作建议
- 让用户调整要求

不允许自动联网搜新论文。

---

# 33. No Imported Papers

明确：

```text
当前项目还没有已导入且可用于引用的论文。
```

提供产品级建议：

```text
先到“文献发现”或“项目论文”导入论文。
```

---

# 34. Existing Citations in Rewrite

如果 selection 内有 Citation Node：

Rewrite 必须：

1. 将 citation 以结构化 placeholder 传给模型或在生成后重新映射；
2. 防止 citation 消失；
3. 防止 citation 随文本换序后错配；
4. 生成后执行 verification。

---

# 35. Nearby Text

无 selection 时，不要默认把整个 document 发给模型。

建议：

```text
current section heading
+
previous ~1–3 paragraphs
+
next paragraph if needed
```

具体 token budget 由 Context Manager 控制。

---

# 36. Current Section

Current Section 必须基于 cursor / heading hierarchy 计算。

Writing Agent 应知道：

```text
2 国内外研究现状
→ 2.1 生成式AI在高等教育中的应用
```

而不是只知道一个纯标题。

---

# 37. Writing Agent Conversation

右侧支持多轮。

但每轮 request 仍必须重新捕获：

- current section
- current selection
- current nearby text

不能只依赖 conversation 开始时的旧 editor context。

---

# 38. Conversation 与 Document 分离

Chat history 可以保存。

但：

- chat 不等于文档 revision
- AI proposal 不等于正文
- 用户点击 replace 后才修改正文

---

# 39. Proposal Card

右侧 AI 返回内容应使用 Proposal Card，而不是普通聊天 Markdown 一股脑输出。

建议：

```text
AI 建议

[生成文本...]

引用
[1] Paper A   ✓
[2] Paper B   △

[替换选中内容] [复制]
```

Generate 无 selection 时：

```text
[复制]
```

---

# 40. Proposal 状态

```text
generating
ready
partially_verified
verification_failed
applied
dismissed
```

---

# 41. Writing Store

建议：

```text
writingStore
├── projectId
├── documentId
├── activeRevisionId
├── currentSection
├── selection
├── nearbyText
├── agentConversationId
├── messages
├── activeProposal
├── verificationState
└── agentPanelCollapsed
```

---

# 42. Store 禁止

不把完整全文复制进 Pinia 长期 state，如果 Tiptap editor 本身已经是 source of truth。

Store 只保存：

- editor context
- UI state
- Agent request/result state

---

# 43. Writing API

建议：

```text
POST /projects/{project_id}/writing/agent/rewrite
POST /projects/{project_id}/writing/agent/generate
POST /projects/{project_id}/writing/verify-citations
```

Document / revision 继续使用现有 endpoint，如果稳定。

---

# 44. Rewrite Request

建议：

```python
class WritingRewriteRequest(BaseModel):
    document_id: str
    instruction: str
    selected_text: str
    selection_from: int
    selection_to: int
    section_path: list[str]
    nearby_text: str | None
```

注意：

selection position 只作为前端 apply 校验辅助，不作为服务器业务真值。

---

# 45. Generate Request

建议：

```python
class WritingGenerateRequest(BaseModel):
    document_id: str
    instruction: str
    section_path: list[str]
    nearby_text: str | None
    citation_style: str
```

---

# 46. Server-side Ownership

服务器必须重新检查：

- document belongs to project
- project belongs to user
- cited paper belongs to project
- evidence belongs to project

不信任前端传入 paper/evidence 关系。

---

# 47. Writing Service

`writing_service.py` V1 应承担 Application Use Case。

推荐：

```python
class WritingService:
    async def rewrite_selection(...)
    async def generate_paragraph(...)
    async def verify_proposal(...)
```

不直接访问 vendor-specific LLM payload。

---

# 48. Writing Workflow 组件

建议：

```text
WritingService
├── ContextManager
├── PaperSelector
├── EvidenceRetriever
├── WritingGenerator
├── CitationMapper
└── CitationVerifier
```

不一定每个都必须是 class，但职责必须拆开。

---

# 49. Prompt Contract - Rewrite

Prompt 必须说明：

- 只按用户要求修改
- 保持原意（用户要求时）
- 不添加无法支持的新事实
- 保留 citation placeholder
- 不输出说明文字
- 输出结构化结果

---

# 50. Prompt Contract - Generate

必须说明：

- 当前章节是什么
- 用户要求是什么
- Evidence 是唯一可用于学术事实引用的来源
- 不得发明 paper
- 不得发明 citation
- claim strength 必须匹配 evidence
- 输出 content + citation mapping

---

# 51. Model Output

使用 structured output / schema validation。

失败：

- retry once with repair
- 仍失败则返回可理解错误

不要在前端正则解析自然语言引用。

---

# 52. Revision

用户修改正文后，继续使用现有 revision 机制。

建议保存策略：

```text
manual save
+
debounced autosave（若当前已有）
+
AI replace creates dirty/revision
```

具体不破坏现有行为。

---

# 53. AI Replace 与 Revision

点击“替换选中内容”后：

- 先写 editor transaction
- 标记 document dirty
- 按现有机制保存
- revision metadata 可标记 source=`ai_replace`

如现有 revision schema不支持 source，可作为可选扩展。

---

# 54. Undo

AI replace 必须可通过 Tiptap history Undo。

不能直接绕过 editor transaction 修改 raw DB。

---

# 55. Export

V1 导出优先：

```text
DOCX
```

其次保留现有稳定：

```text
PDF
Markdown
LaTeX
```

若当前已有 export 能力，不得因 Writing Workspace 重构删除。

---

# 56. Export 与 Citation Style

导出前：

- 根据当前 Project citation style 渲染正文 citation
- 生成 references section（如当前 export 支持）

如果 V1 暂无独立参考文献面板，也不影响导出自动生成 bibliography。

---

# 57. Reference Bibliography

用户已明确：

> 写作面板暂时不需要独立参考文献面板。

因此 V1：

- 不增加常驻 References Sidebar
- Citation detail 用 Popover / Drawer
- 最终 bibliography 可在导出或文档尾部自动生成

---

# 58. Citation Insertion Manual

编辑器可保留“插入引用”能力。

允许用户在当前 Project 已导入论文中搜索并插入 citation。

但不作为 Writing Agent 必需路径。

---

# 59. Formula

如果现有 Tiptap 已有 formula / math plugin，继续保留。

如果没有：

- 可作为 V1.1 小阶段
- 不阻塞核心 Writing Agent 主链

---

# 60. Table / Figure

同理：

- 基础表格 / 图片已有则保留
- 复杂论文图表管理不作为主线阻塞项

---

# 61. AI Loading UX

用户点击发送：

右侧：

```text
正在读取项目资料
↓
正在查找相关论文
↓
正在查找支持证据
↓
正在生成内容
↓
正在验证引用
```

不是显示 spinner 60 秒无反馈。

---

# 62. Streaming

可以 stream：

- 状态
- 普通文本生成（如果与 structured citation output兼容）

但不要为了 streaming 破坏最终 citation mapping。

可采用：

```text
progress stream
+
final structured proposal
```

---

# 63. Agent Failure

错误分类：

```text
CONTEXT_ERROR
NO_IMPORTED_PAPERS
NO_RELEVANT_PAPERS
NO_SUPPORTING_EVIDENCE
GENERATION_ERROR
VERIFICATION_ERROR
DOCUMENT_CONFLICT
```

前端映射成用户文案。

---

# 64. Document Conflict

如果 Agent 请求发送后，用户继续大量修改正文：

Proposal 仍可显示。

但“替换”时必须检查 selection / document version。

若冲突：

```text
正文已发生变化，请重新选择后再次应用。
```

---

# 65. Concurrency

V1 不做多人协同编辑。

只需处理：

- 同一用户多 tab
- autosave 与 AI replace 的基本冲突

使用 revision / updated_at 做轻量 optimistic concurrency。

---

# 66. Empty Writing State

Project 尚无 WritingDocument：

```text
开始撰写你的论文
[新建论文]
```

可以：

- 空白文档
- 基础论文结构模板（可选）

不要一上来生成整篇 AI 大纲作为默认。

---

# 67. Project Metadata in Writing

顶部轻量显示：

```text
Project Name
Document Title
Save State
Export
```

不要放：

- Agent Tools count
- Evidence count KPI
- Execution id

---

# 68. Writing Toolbar Visual

保持固定、紧凑。

推荐：

```text
Undo Redo | Style | B I U | List | Quote | Link | Citation | Formula
```

AI 不在 toolbar 堆动作。

---

# 69. Right Panel Width

默认：

```text
360px
```

可拖动或折叠属于优化。

第一版至少允许：

```text
collapse / reopen
```

---

# 70. Left Panel

默认：

```text
220px
```

可折叠属于次优先。

---

# 71. Responsive

Writing Desktop First。

建议：

```text
>= 1200px: 3 columns
900–1199px: left collapsible, right panel overlay/resize
< 900px: basic edit/read only, Agent drawer
```

手机不作为 V1 主写作场景。

---

# 72. Accessibility

- Agent input 有 label
- Proposal action 可键盘操作
- Citation status 不只靠颜色
- Tooltip 有 accessible description
- disabled buttons 真实 disabled

---

# 73. Existing `WritingDocumentEditor.vue` Migration

## KEEP

- Tiptap
- Document persistence
- outline
- revision
- citation node
- editor commands
- citation audit infrastructure

## REFACTOR

- 页面布局
- Evidence 常驻展示方式
- AI proposal interaction
- selection context
- right agent panel

## EXTEND

- generate paragraph
- Project Context
- Evidence Retrieval
- structured citation verification
- copy / replace behavior

---

# 74. Existing Fixed AI Actions

如果当前已有：

```text
improve_style
make_concise
clarify_argument
...
```

处理：

- 可保留作为 quick prompt chips
- 不作为核心 API action enum 的唯一入口

右侧 Agent 主接口应接受：

```text
free-form instruction
```

---

# 75. Quick Prompt Chips

可以在 selection 状态下显示轻量快捷项：

```text
学术化
精简
增强逻辑
```

但只是填充 instruction。

不新增平行 workflow。

这属于可选 UI 优化，不阻塞 V1。

---

# 76. Citation Audit Existing Feature

继续保留。

但新的 Citation Verification 是更强层。

关系：

```text
existing audit
→ deterministic / lexical foundation

new verifier
→ semantic support validation
```

不要删掉 existing audit 后重写全部。

---

# 77. Evidence Detail

点击 citation 后：

```text
来源论文
页码
原文 snippet
normalized claim
verification status
```

这是用户建立信任的重要 UI。

---

# 78. Hallucination Guard

Writing Generator Prompt 和 Workflow 必须固定：

- 不能创造 citation
- 不能引用 project 外 paper
- 没证据就少写
- 不为满足用户要求而夸大证据

---

# 79. Citation Count

一次段落不要默认塞过多引用。

建议：

- 1 个主要 claim → 1–3 个引用
- 由 evidence coverage 决定

不要为了“像论文”每句话都塞 citation。

---

# 80. Generated Text Style

V1 不自动承诺：

- 某学校模板语气
- 所有学科专用写作规范

Agent 根据：

- 项目主题
- 当前上下文
- 用户指令

生成正式、客观、学术化文本。

---

# 81. Plagiarism / Copying

生成器不得直接长段复制 Evidence snippet。

Evidence 用于支撑事实。

生成文本应：

- paraphrase
- synthesize
- citation

必要直接引语必须明显标记，且不作为默认行为。

---

# 82. Writing Context Safety

不要将：

- Provider API key
- internal system prompt
- execution trace
- unrelated project data

混入 model context。

---

# 83. Tests - Editor

必须覆盖：

- selection extraction
- section detection
- replace valid selection
- replace stale selection rejected
- undo after replace
- citation node survives rewrite

---

# 84. Tests - Writing Service

必须覆盖：

- rewrite plain text
- rewrite with citations
- generate with evidence
- no imported papers
- no relevant evidence
- structured output repair
- verification failed

---

# 85. Tests - Citation

必须覆盖：

- citation belongs to project
- evidence mismatch
- weak
- unsupported
- style rendering
- citation node persistence
- export citation

---

# 86. Tests - Frontend

至少：

- 3-column layout
- agent panel collapse
- selection badge
- no-selection context
- proposal card
- replace
- copy
- citation status
- failure states
- loading stages

---

# 87. API Backward Compatibility

现有 Writing API 如果已有前端调用：

- 不要一次性删除
- 新 endpoint 可并行一阶段
- Frontend 切换完成后再 deprecate

在 implementation progress 记录 deprecation。

---

# 88. Performance

一次 Generate Paragraph 建议控制：

```text
candidate papers <= 5
retrieved evidence chunks limited
verification only used citations
```

避免：

- 全 Project 全文读入
- 全 Evidence 表扫描
- 所有 Paper Profile LLM rerank

---

# 89. Timeouts

Writing Workflow 必须有阶段 timeout。

例如：

```text
context retrieval
generation
verification
```

超时可返回部分状态，但不把未验证引用标记成功。

---

# 90. Observability

一次 Writing request 至少记录：

```text
request type
project_id
document_id
has_selection
candidate_paper_count
evidence_count
citation_count
verified_count
weak_count
unsupported_count
duration
```

不记录 chain-of-thought。

---

# 91. Analytics

V1 不要求产品 analytics 平台。

如已有日志，可记录：

- rewrite apply rate
- generation copy rate
- citation failure rate

仅用于后续 UX 优化。

---

# 92. Security

所有 Writing API：

- auth
- project ownership
- document ownership
- evidence ownership
- paper ownership

必须 server-side 验证。

---

# 93. Document Save State

顶部应至少有：

```text
已保存
保存中…
保存失败
```

不让用户猜正文是否持久化。

---

# 94. Export State

导出：

```text
生成中
完成
失败
```

不要阻塞编辑器状态。

---

# 95. User Journey - Rewrite

```text
进入 Writing
→ 选择 120 字
→ 右侧显示 selection badge
→ 输入“润色得更学术”
→ Agent 返回 proposal
→ 用户点击替换
→ Tiptap transaction
→ revision/save
→ undo 可用
```

---

# 96. User Journey - Generate

```text
进入 2.1 章节
→ 不选择文字
→ 输入“根据已导入论文写一段...”
→ 系统读取 Project Context
→ 选相关论文
→ 找 Evidence
→ 生成
→ Citation Verify
→ 显示 proposal
→ 用户点击复制
```

---

# 97. User Journey - Unsupported Citation

```text
生成 proposal
→ citation verifier unsupported
→ 卡片明确 warning
→ 系统不显示 ✓
→ 用户可以修改要求或重试
```

---

# 98. User Journey - No Papers

```text
用户要求“根据项目论文写”
→ 发现 Project 没有 imported paper
→ 不调用模型胡编引用
→ 提示先导入论文
```

---

# 99. Definition of Done

Writing Workspace V1 完成必须满足：

1. 正式 Tiptap 编辑器可持续写作。
2. 有清晰论文 Outline。
3. 右侧 Agent 能感知当前章节。
4. Selection 时能感知已选文本。
5. 用户可以用自由语言要求改写。
6. AI 不自动覆盖正文。
7. 有 `[替换选中内容]` 与 `[复制]`。
8. 无 Selection 时可以生成一段。
9. Generate 使用当前 Project 已导入论文。
10. 通过 Paper Profile 缩小候选。
11. 通过真实 chunk 检索 Evidence。
12. Citation 是结构化 Node / mapping。
13. Citation Verification 固定执行。
14. Unsupported citation 明确提示。
15. 引用只来自当前 Project 已导入论文。
16. 不自动联网搜索新论文。
17. Revision / save 继续正常。
18. Undo 正常。
19. DOCX 导出优先保持 / 完成。
20. Existing Reader 不受影响。
