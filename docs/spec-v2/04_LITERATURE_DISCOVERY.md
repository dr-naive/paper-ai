# PaperAI V1 Literature Discovery Specification

> 文档状态：ACTIVE / AUTHORITATIVE
> 版本：v2.0-draft
> 适用对象：Codex、AI Coding Agent、PaperAI 开发者
> 本文定义 PaperAI V1 的 Literature Discovery 产品流程、后端 Workflow、Academic Search Provider、API Contract、前端状态与卡片交互。
> 产品范围见 `00_PRODUCT_SCOPE.md`，总体架构见 `02_TARGET_ARCHITECTURE.md`。

---

# 0. 目标

Literature Discovery 解决：

> 用户大致知道自己想研究什么，但不知道应该读哪些真实论文。

V1 必须把：

```text
模糊需求
→ 明确 Search Intent
→ 用户可编辑固定筛选条件
→ Agent 制定有限搜索策略
→ 调用真实学术 API
→ 检查结果质量
→ 必要时有限补搜
→ 返回结构化真实论文
→ 收藏 / 下载 / 导入
```

做成一条完整可用链路。

---

# 1. 页面入口

Route 建议：

```text
/projects/:projectId/discover
```

必须属于某个 Project。

V1 不提供脱离 Project 的独立“AI 文献发现”模式。

原因：

- Search Intent 需要 Project Profile
- 收藏与导入需要 current project
- 后续 Writing Context 依赖项目内论文

---

# 2. 页面总体结构

Desktop V1 采用上下结构，而不是永久左右分栏。

```text
Literature Discovery
──────────────────────────────────────

A. Requirement Clarification

B. Search Conditions

C. Search Results
```

搜索完成后 A 区应可折叠，给结果腾出空间。

---

# 3. Stage A：Requirement Clarification

## 3.1 目标

将用户模糊研究想法整理为明确 Search Intent。

## 3.2 输入 Context

至少读取：

```text
Project Profile
+
当前 Discover session 对话
+
必要 Literature Memory
```

不读取：

- 整篇 Writing Document
- 全部 Paper Full Text
- 所有历史聊天

## 3.3 Agent 行为

允许：

- 提问
- 识别研究主题过宽
- 询问研究对象 / 场景 / 方法 / 关注问题
- 总结当前需求
- 生成关键词建议
- 标记排除方向

禁止：

- 在需求还明显模糊时静默开始大量搜索
- 自己修改 Project 核心字段
- 生成虚假的“已找到论文”

---

# 4. Search Intent Schema

必须结构化。

建议：

```python
class SearchIntentDTO(BaseModel):
    topic: str
    research_question: str | None = None
    detailed_need: str | None = None
    keywords: list[str] = []
    preferred_methods: list[str] = []
    exclusion_notes: list[str] = []
```

其中 `topic` 必须存在。

---

# 5. Clarification Completion

当 Agent 判断需求足够明确时，应输出：

```text
status = ready_for_search
```

同时返回结构化 `SearchIntentDTO`。

前端将其自动填入 Search Conditions 区。

用户必须可以修改。

---

# 6. Stage B：Search Conditions

搜索条件由两部分组成：

```text
Natural-language Search Intent
+
Structured Filters
```

---

# 7. Structured Filters

V1 第一版固定支持：

```text
年份
语言
学科领域
文献类型
```

建议 DTO：

```python
class SearchFiltersDTO(BaseModel):
    year_from: int | None = None
    year_to: int | None = None
    language: str | None = None
    field: str | None = None
    publication_types: list[str] = []
```

---

# 8. 年份

UI：

```text
[2020] — [2026]
```

允许：

- 两边都空
- 只有起始年
- 只有结束年

Validation：

```text
year_from <= year_to
```

错误时前端直接提示，不进入 Agent。

---

# 9. 语言

V1 UI 可选：

```text
不限
中文
英文
```

实际 Provider 对语言 filter 的支持能力可能不同。

因此 Provider 必须声明 capability。

如果主 Provider 不支持可靠 language filter：

- 可以做结果级 deterministic filter（如果 metadata 可得）
- 不得假装 API 已严格过滤

---

# 10. 学科领域

UI 使用固定下拉 / 可搜索 Select。

第一版不要建立巨大专业学科树。

建议采用适中一级分类，例如：

```text
不限
计算机科学
工程
教育学
医学与健康
生命科学
物理
化学
数学
经济与管理
社会科学
人文学科
其他
```

具体映射必须由 Provider adapter 完成。

不能把 UI 字符串原样假定成 Provider field value。

---

# 11. 文献类型

第一版建议：

```text
不限
期刊论文
会议论文
综述
预印本
```

如果某 Provider 无法准确支持：

- 进行 capability-aware mapping
- 不能过滤的条件作为 result post-filter / soft preference

---

# 12. Search Form

建议结构：

```text
搜索需求
[完整可编辑文本区域]

年份
[____] - [____]

语言
[不限 ▼]

领域
[教育学 ▼]

文献类型
[不限 ▼]

                         [搜索论文]
```

搜索描述来源于 Search Intent，但允许用户修改。

修改后：

- Search Intent 原结构不需要全部重新对话
- 后端可以接收最终 `query_description + structured intent`

---

# 13. Search Request

建议：

```python
class LiteratureSearchRequest(BaseModel):
    project_id: str
    intent: SearchIntentDTO
    filters: SearchFiltersDTO
    max_results: int = 10
```

V1 后端强制：

```text
max_results <= 10
```

即使前端传更大，也应限制。

---

# 14. Search Workflow

固定主流程：

```text
Validate Request
    ↓
Load Project Context
    ↓
Build Search Plan
    ↓
Round 1 Search
    ↓
Normalize
    ↓
Deduplicate
    ↓
Evaluate Coverage / Relevance
    ↓
Enough?
├── yes → Finalize
└── no
     ↓
Adjust Queries
     ↓
Round 2 / 3
     ↓
Merge
     ↓
Finalize
```

---

# 15. Search Budget

V1 固定建议：

```text
max search rounds = 3
max final results = 10
```

每轮可生成多个 Query，但总 Provider requests 必须有限。

建议：

```text
max queries per round = 3
```

实际可在实施时根据 rate limit 调整，但必须写入配置。

---

# 16. Search Planner

Search Planner 的输入：

```text
SearchIntent
SearchFilters
ProjectProfile summary
Previous round summary
```

输出结构化：

```python
class SearchPlanDTO(BaseModel):
    queries: list[str]
    rationale_summary: str | None = None
```

`rationale_summary` 只用于调试 / execution summary，不展示 raw reasoning。

---

# 17. Query 生成规则

Agent 应生成互补 Query，而不是简单同义改写。

例如：

```text
Topic:
generative AI + self-regulated learning + higher education
```

可以：

```text
Query A:
"generative AI" "self-regulated learning" higher education

Query B:
ChatGPT university students autonomous learning empirical study

Query C:
large language models self-regulated learning higher education review
```

---

# 18. Search Provider Interface

建议：

```python
class AcademicSearchProvider(Protocol):
    name: str

    def capabilities(self) -> ProviderCapabilities:
        ...

    async def search(
        self,
        query: str,
        filters: SearchFiltersDTO,
        limit: int,
    ) -> list[ProviderPaperDTO]:
        ...
```

---

# 19. Provider Capabilities

建议：

```python
class ProviderCapabilities(BaseModel):
    supports_year: bool
    supports_language: bool
    supports_field: bool
    supports_publication_type: bool
    returns_abstract: bool
    returns_pdf_url: bool
    returns_citation_count: bool
```

Workflow 必须按 capability 映射，而不是假设所有 Provider 一样。

---

# 20. V1 Provider Strategy

第一版不要接太多数据源。

V1 产品策略固定为：

```text
Primary literature discovery:
Semantic Scholar Academic Graph API, unauthenticated-first

Supplement / metadata enrichment:
Crossref REST API

Preprint / downloadable full-text source:
arXiv

Optional future enhancement:
SEMANTIC_SCHOLAR_API_KEY
```

实现时应优先评估：

- Semantic Scholar
- OpenAlex
- arXiv
- Crossref

但不要为了“支持所有”延误主线。

选型标准：

1. API 稳定
2. 免费或低成本
3. Abstract 覆盖
4. DOI / metadata 质量
5. rate limit 可接受
6. field / type filter 支持
7. open access / PDF link 信息
8. 个人项目可维护性

最终主 Provider 选择需在实施 Phase 之前写进 `08_IMPLEMENTATION_PROGRESS.md` 的 Architecture Decision。

Provider exploration must be bounded.

For V1 selection:

1. compare only the candidates already justified by this spec / current code;
2. record one Primary Provider decision;
3. do not repeatedly switch providers only because a credential is missing;
4. if a selected endpoint requires user-controlled credentials or account setup, execute the External Dependency Gate in `AGENTS.md` for that endpoint;
5. continue credential-independent adapter / contract-test work where possible;
6. accept the credential-free public path through a real-provider smoke when it is the selected V1 path;
7. do not treat an optional Semantic Scholar API key as a Literature Discovery blocker or repeatedly switch providers because it is unavailable.

---

# 21. Provider Result

Provider-specific DTO：

```python
class ProviderPaperDTO(BaseModel):
    source_paper_id: str
    title: str
    authors: list[str]
    year: int | None
    venue: str | None
    abstract: str | None
    doi: str | None
    paper_url: str | None
    pdf_url: str | None
    language: str | None
    publication_type: str | None
    fields: list[str]
    citation_count: int | None
    open_access: bool | None
```

---

# 22. Normalized Result

统一返回：

```python
class PaperSearchResultDTO(BaseModel):
    result_id: str
    source: str
    source_paper_id: str

    title: str
    authors: list[str]
    year: int | None
    venue: str | None
    abstract: str | None
    doi: str | None

    paper_url: str | None
    pdf_url: str | None

    language: str | None
    publication_type: str | None
    fields: list[str]
    citation_count: int | None
    open_access: bool | None

    recommendation_reason: str | None

    is_favorite: bool
    download_available: bool
    import_available: bool
```

---

# 23. Abstract Rule

必须返回 Provider 能提供的完整 Abstract。

禁止后端：

```python
abstract[:500]
```

或其它 UI 目的截断。

前端负责：

```text
默认 4 行
展开
收起
```

---

# 24. Deduplication

同一论文可能来自多个 Query / Provider。

去重优先级：

```text
1. DOI
2. stable source paper id + provider
3. normalized title + year
```

合并时优先保留：

- 更完整 abstract
- DOI
- PDF URL
- paper URL
- venue
- citation count

不得简单保留第一条并丢弃更完整 metadata。

---

# 25. Result Quality Check

Agent 判断：

- 是否明显偏离用户主题
- 是否全部集中在错误子领域
- 是否缺少用户明确要求的方法 / 场景
- 是否结果数量过少
- 是否 Query 太宽 / 太窄

不要求 V1 做复杂权威性评分。

---

# 26. Retry Decision

如果结果不足或偏题：

Agent 可：

- 改关键词
- 加同义词
- 拆不同子 Query
- 放宽自然语言细节

Agent 不可静默修改：

- 用户明确年份
- 用户明确语言
- 用户明确领域
- 用户明确文献类型

结构化 filter 是强约束。

若强约束导致结果过少，最终如实返回，并提示可放宽。

---

# 27. Final Selection

V1 最终返回最多 10 篇。

若候选 > 10：

第一版可采用：

```text
relevance
+
coverage
+
basic metadata completeness
```

简单选取。

复杂：

- authority score
- citation age normalization
- journal impact
- SOTA scoring

全部后置。

---

# 28. Recommendation Reason

如果生成：

必须短、具体、用户可理解。

例如：

```text
与当前研究问题高度相关，直接研究大学生在使用生成式 AI 后的自主调节学习行为。
```

不要：

```text
relevance score: 0.917
```

V1 如果该步骤导致延迟过大，可以先仅对最终 10 篇批量生成。

---

# 29. Search Response

建议：

```python
class LiteratureSearchResponse(BaseModel):
    execution_id: str
    papers: list[PaperSearchResultDTO]
    result_count: int
    search_rounds: int
    warnings: list[str]
```

warnings 示例：

```text
仅找到 6 篇满足当前强筛选条件的论文。
```

---

# 30. Execution Progress

用户可见阶段：

```text
preparing
searching
screening
retrying
finalizing
completed
failed
```

前端文案：

```text
正在准备检索条件
正在搜索相关论文
正在筛选结果
正在补充检索
正在整理最终结果
```

禁止展示：

- Tool name
- Provider raw payload
- raw model reasoning
- internal retry stack

---

# 31. Result Cards Layout

Desktop：

```text
2 columns
```

建议 CSS Grid：

```css
grid-template-columns: repeat(2, minmax(0, 1fr));
```

卡片默认统一视觉高度策略。

---

# 32. Paper Card Information Order

视觉优先级：

1. Title
2. Authors / Year / Venue
3. Abstract
4. Recommendation reason
5. Basic metadata
6. Actions

---

# 33. Abstract UI

默认：

```text
4 lines
```

提供：

```text
展开
```

展开后显示完整 Abstract。

再提供：

```text
收起
```

只有用户主动展开时允许单卡高度不同。

---

# 34. Card Actions

固定顺序：

```text
详情 | 收藏 | 下载 | 导入
```

按钮必须固定位置。

---

# 35. 详情

点击打开右侧 Drawer。

Drawer 至少：

```text
Title
Authors
Year
Venue
DOI
Full Abstract
Basic metadata
Recommendation reason
Original page
收藏 / 下载 / 导入
```

不要默认新标签跳外站。

---

# 36. 收藏

收藏只做筛选。

含义：

```text
“这篇我觉得可能有用，先留下”
```

收藏：

- 不下载 PDF
- 不解析
- 不进入 Project Papers
- 不生成 Paper Profile

保存 metadata + links 即可。

---

# 37. Favorite Model

可以建立轻量 Project Favorite / Discovery Saved Result。

如果当前模型可使用 JSON / relation 扩展，优先复用。

必须关联：

```text
project_id
source
source_paper_id
normalized metadata
saved_at
```

不要把收藏结果错误存成 `ProjectPaper`。

---

# 38. 收藏 Filter

结果区第一版支持：

```text
全部
已收藏
```

不需要复杂收藏夹。

---

# 39. 下载

含义：

> 把可用 PDF 下载到用户本地。

它与“导入”独立。

如果：

```text
pdf_url == None
```

则：

```text
download_available = false
```

按钮：

- 保持位置
- disabled
- 置灰
- Tooltip：`暂无可用下载链接`

---

# 40. 下载安全

Frontend 不应盲目直接信任任意 Provider URL。

优先策略：

- 如果 Provider 提供明确公开 PDF link，可直接跳转下载（根据安全评估）
- 或通过受控后端 endpoint 获取 / redirect

不得因此放开 `remote_paper_import.py` 的 arbitrary URL 限制。

---

# 41. 导入

含义：

> 获取论文全文并正式进入当前 Project。

成功链：

```text
search result
    ↓
approved import source
    ↓
remote_paper_import
    ↓
existing upload/paper record
    ↓
parse
    ↓
index
    ↓
ProjectPaper relation
    ↓
Paper Profile generation
```

---

# 42. Import Availability

只有系统知道如何合法安全获取全文时：

```text
import_available = true
```

否则：

- button disabled
- Tooltip：`暂无可导入的论文全文`

---

# 43. Search Source ≠ Import Source

如果 Search Provider 返回 DOI 但无 PDF：

```text
download = disabled
import = disabled
original page = available
收藏 = available
```

如果能从 arXiv / open access repository 映射到 PDF：

```text
download = enabled
import = enabled
```

---

# 44. Local PDF Upload

Project Papers 页面仍必须保留：

```text
上传本地 PDF
```

Literature Discovery 不替代本地上传。

---

# 45. Import State

卡片导入时：

```text
idle
importing
imported
failed
```

按钮布局保持。

导入中：

```text
[正在导入…]
```

成功：

```text
[已导入]
```

仍占相同区域。

---

# 46. Favorite State

```text
☆ 收藏
★ 已收藏
```

保持宽度和布局稳定。

---

# 47. Empty State

首次进入：

```text
告诉 PaperAI 你正在研究什么，
我会先帮助你明确需求，再查找适合阅读的论文。
```

还没搜索时不要显示假卡片。

---

# 48. Zero Results

真实 0 条：

```text
没有找到符合当前条件的论文。
```

给：

```text
修改搜索条件
重新讨论需求
```

可以建议：

- 放宽年份
- 改变关键词
- 放宽语言

但不能自动解除用户强筛选。

---

# 49. Partial Results

例如只找到 4 篇：

正常显示 4 篇。

顶部：

```text
找到 4 篇符合当前条件的论文
```

不是：

```text
10 篇结果
```

---

# 50. Provider Failure

如果主 Provider 失败：

- 如果已有另一个配置好的 Provider，可按 workflow fallback
- 若无，明确返回服务错误

不要让 LLM凭知识生成论文列表。

---

# 51. API Endpoint 建议

建议拆：

```text
POST /projects/{project_id}/discovery/clarify
POST /projects/{project_id}/discovery/search
GET  /projects/{project_id}/discovery/executions/{execution_id}
POST /projects/{project_id}/discovery/favorites
DELETE /projects/{project_id}/discovery/favorites/{favorite_id}
POST /projects/{project_id}/discovery/import
```

是否使用 SSE endpoint 由现有 execution infrastructure 决定。

---

# 52. Clarify API

Request：

```python
class ClarifyRequest(BaseModel):
    message: str
    conversation_id: str | None
```

Response：

```python
class ClarifyResponse(BaseModel):
    message: str
    status: Literal["clarifying", "ready_for_search"]
    intent: SearchIntentDTO | None
```

---

# 53. Search API

Request：

```json
{
  "intent": {
    "topic": "...",
    "research_question": "...",
    "detailed_need": "...",
    "keywords": ["..."],
    "preferred_methods": [],
    "exclusion_notes": []
  },
  "filters": {
    "year_from": 2020,
    "year_to": 2026,
    "language": "en",
    "field": "education",
    "publication_types": ["journal", "review"]
  }
}
```

---

# 54. Favorite API

不得依赖前端把整张对象随意塞数据库。

后端要：

- validate source
- normalize schema
- reject oversized raw payload

---

# 55. Import API

至少输入：

```text
project_id
source
source_paper_id
approved_pdf_locator / normalized result id
```

不要让前端提交任意 `url` 让后端下载。

---

# 56. Frontend Component 建议

```text
components/discover/
├── RequirementChat.vue
├── SearchIntentSummary.vue
├── SearchFilterForm.vue
├── SearchExecutionStatus.vue
├── PaperResultGrid.vue
├── PaperResultCard.vue
└── PaperDetailDrawer.vue
```

---

# 57. Store

`discoverStore` 建议：

```text
projectId
conversationId
messages

searchIntent
filters

searchStatus
executionId
progressStage

results[]
favoriteIds

activePaper
detailDrawerOpen
```

---

# 58. Store 禁止

不要持久化：

- raw Provider response
- raw Tool output
- full execution trace
- model reasoning

---

# 59. Requirement Chat Collapse

搜索成功后，Requirement Chat 应可收起为：

```text
当前检索需求：
生成式 AI 对大学生自主学习的影响……

[重新讨论]
```

点击“重新讨论”展开。

---

# 60. Re-search

用户修改：

- Search Intent 文本
- 固定 Filter

后点击重新搜索即可。

不强制重新走完整 Clarification Chat。

---

# 61. Search Result Persistence

当前搜索结果本身可：

- 前端状态保存
- Redis /短期 cache
- execution snapshot

不要求所有结果 durable 入库。

只有：

- favorite
- imported

需要长期业务持久化。

---

# 62. Literature Memory Write

一次搜索 session 完成后，可保存：

```text
final search intent
important keywords
explicit exclusions
```

不要自动保存所有 query。

---

# 63. Project Profile Interaction

Discover 不自动改 Project Profile。

如果未来发现方向聚焦，可提示用户。

V1 不做也可以。

---

# 64. Testing - Provider

Test layers:

- unit / contract tests may mock provider HTTP responses;
- rate-limit / malformed / timeout cases should normally be deterministic mocked tests;
- at least one real-provider smoke test is required before provider integration acceptance;
- an optional missing Semantic Scholar key is not a reason to mark the public-path smoke as blocked or to fabricate a successful response;
- if the selected endpoint genuinely requires a missing credential, record `BLOCKED_BY_USER` for that endpoint only.

必须测试：

- filter mapping
- empty abstract
- missing DOI
- missing PDF
- timeout
- rate limit
- malformed response
- complete abstract preserved

---

# 65. Testing - Normalize

必须测试：

- DOI dedup
- title dedup
- metadata merge
- same paper from multiple Query
- Unicode author names
- missing year
- missing venue

---

# 66. Testing - Workflow

必须测试：

- round 1 sufficient
- round 1 too broad → retry
- max round stop
- fewer than 10
- zero result
- provider error
- strong filters preserved
- no fabricated papers

---

# 67. Testing - Favorite

必须测试：

- favorite
- unfavorite
- same paper duplicate favorite
- cross-project isolation

---

# 68. Testing - Import

必须测试：

- import available
- unavailable source
- invalid source
- remote importer validation
- parse triggered
- ProjectPaper created
- duplicate import
- import failure cleanup

---

# 69. Testing - Frontend

至少：

- two-column grid
- abstract four-line clamp
- expand / collapse
- disabled download
- tooltip
- disabled import
- favorite state
- import progress
- detail drawer
- zero results
- partial results
- chat collapse

---

# 70. Migration from Existing arXiv Search

当前：

```text
arXiv all:{query}
max_results
abstract truncated
```

迁移目标：

1. 保留 arXiv adapter。
2. 移除 UI 目的 Abstract truncation。
3. 接入统一 Provider schema。
4. 不再让 Project API endpoint 直接承担全部 search logic。
5. arXiv 可作为：
   - provider
   - import source
   - fallback
6. 不要求 arXiv 能满足所有 field / language filter。

---

# 71. Migration from Semantic Scholar Existing Use

当前 Semantic Scholar 主要用于：

- citations
- references

V1 可评估升级为：

- main search provider
- enrichment provider

但必须先确认：

- rate limit
- API key requirements
- filter coverage
- abstract coverage

最终决定写进进度文档。

---

# 72. Provider Configuration

配置必须集中，例如：

```text
ACADEMIC_SEARCH_PRIMARY_PROVIDER
SEMANTIC_SCHOLAR_API_KEY
CROSSREF_MAILTO
SEARCH_MAX_ROUNDS
SEARCH_MAX_QUERIES_PER_ROUND
SEARCH_RESULT_LIMIT
```

不要散落在 workflow 代码。

---

## External Credential Boundary

The implementation must distinguish:

```text
code/config support
vs
real provider availability
```

If a required credential is not configured:

```text
adapter implementation
+ mocked unit/contract tests
= allowed

real integration accepted
= not allowed
```

For the V1 public Semantic Scholar path, the API key is optional. Anonymous 429 responses remain typed, bounded provider states; they do not turn the whole Literature Discovery phase into `BLOCKED_BY_USER`.

Codex must record any genuinely required missing credential in `08_IMPLEMENTATION_PROGRESS.md` and ask the user for the exact required action instead of repeatedly trying unrelated providers.

A Provider Block may be described as:

```text
IMPLEMENTATION_COMPLETE_EXTERNAL_VALIDATION_BLOCKED
```

but Literature Discovery V1 is not fully complete until the chosen real provider has passed a real integration smoke test.

---

# 73. Rate Limit

Provider 调用必须处理：

- 429
- Retry-After
- timeout
- bounded retry

不得无限重试。

---

# 74. Cache

可对 provider query 做短期缓存。

例如 TTL：

```text
30 min – 24 h
```

具体可根据 API 限制。

Cache 仅作为优化，不改变业务数据。

---

# 75. Search Ranking V1

V1 暂时不做复杂权威评分。

可使用：

```text
provider relevance
+
query coverage
+
Agent relevance judgment
```

基本足够。

不要第一版实现：

- journal impact factor crawler
- normalized citation percentile
- author h-index weighting
- graph authority model

---

# 76. Result Explanation

用户不需要看到搜索内部计划。

可看到：

```text
为什么推荐：
与当前研究问题高度相关，并直接研究了大学生自主学习行为。
```

---

# 77. UI Visual Rules

Paper Card：

- 浅边框
- 小圆角
- 轻 Hover
- 不大面积彩色
- Title 2–3 行以内
- Abstract 四行
- Actions 固定底部

双列间距一致。

---

# 78. Responsive

Desktop First。

建议：

```text
>= 1200px: 2 columns
< 900–1000px: 1 column
```

具体 breakpoint 统一在 design spec 定义。

---

# 79. Accessibility

Disabled 按钮必须：

- `disabled`
- Tooltip / accessible label
- 不只靠颜色表达

展开摘要按钮可键盘访问。

---

# 80. 用户可见错误文案

不要：

```text
Tool execution failed: SemanticScholarSearch timeout
```

使用：

```text
论文搜索服务暂时没有响应，请稍后重新搜索。
```

同时内部保留技术错误日志。

---

# 81. Security / Copyright Boundary

PaperAI 只提供：

- metadata
- 合法可访问链接
- 合法开放 PDF 获取 / import

不尝试绕过：

- paywall
- institutional authentication
- publisher access control

没有公开全文时：

```text
download/import disabled
```

---

# 82. Definition of Done

Literature Discovery V1 完成必须满足：

1. Project 内存在 Discover page。
2. 用户可与 Agent 对话明确搜索需求。
3. Agent 可生成结构化 Search Intent。
4. 搜索表单自动填入且用户可编辑。
5. 年份 / 语言 / 领域 / 文献类型独立结构化。
6. 后端使用真实 Academic Search Provider。
7. Agent 可有限多轮修改 Query。
8. 最大轮次受控。
9. 最终最多返回 10 篇真实论文。
10. Abstract 后端完整保留。
11. 前端双列卡片。
12. Abstract 默认四行，可展开。
13. 卡片固定：详情 / 收藏 / 下载 / 导入。
14. 无 PDF 时下载 / 导入固定置灰。
15. 收藏只保存 metadata，不创建 ProjectPaper。
16. 导入走安全 Remote Import + Existing Parse Pipeline。
17. 搜索结果不足 10 篇时如实显示。
18. 搜索失败时不让 LLM 伪造结果。
19. 所有核心路径有测试。
20. UI 不显示 Tool / raw Agent execution。
