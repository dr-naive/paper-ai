# TODO / Risks

> 状态：ACTIVE  
> 本文档只记录**当前真实存在、尚未完全解决**的问题和风险。  
> 已经解决的问题应删除或移入 Git 历史，不要长期保留为“TODO”。  
> 当前 V1 实施状态以 `docs/spec-v2/08_IMPLEMENTATION_PROGRESS.md` 为准。

---

## 使用规则

风险条目使用：

```text
Status: OPEN / MITIGATED / CLOSED
Priority: P0 / P1 / P2
Owner Phase: Phase X
```

- 当前 Phase 内正在处理的具体施工问题：记录到 `08_IMPLEMENTATION_PROGRESS.md`。
- 跨 Phase、可能长期存在的技术债或产品风险：记录到本文。
- 不确定是否仍存在的问题，必须先检查当前代码和测试，不能因为旧文档写过就继续保留。

---

## RISK-001 — `lead_agent.py` 职责过重

Status: OPEN  
Priority: P0  
Owner Phase: Phase 4–6

当前 `backend/app/harness/agents/lead_agent.py` 同时承担 Agent 主循环、上下文拼接、执行控制、checkpoint / streaming 等多类职责。

风险：

- Discover、Writing、Citation 等新能力继续叠加后会形成更严重的 God Object。
- 业务逻辑和通用 Runtime 难以独立测试。
- Prompt / Context / retry 逻辑容易互相污染。

处理方向：

- 保留通用 model tool-calling loop。
- Project Context 构建迁出。
- Literature Discovery workflow 迁出。
- Writing workflow 迁出。
- Citation Verification 迁出。
- 不允许新增大量 `if mode == ...` 业务分支。

对应规范：

- `docs/spec-v2/01_CODEBASE_MIGRATION_MAP.md`
- `docs/spec-v2/02_TARGET_ARCHITECTURE.md`

---

## RISK-002 — `literature_research.py` 混合 Tool 与 Workflow 职责

Status: OPEN  
Priority: P0  
Owner Phase: Phase 2

当前外部文献相关实现已经存在，但工具文件体量和职责过大。

风险：

- Provider-specific HTTP、查询策略、结果筛选、研究工作流容易混在同一层。
- 无法稳定支持多个 Academic Search Provider。
- Agent 可能通过一个“大工具”绕过确定性过滤、预算和错误边界。

处理方向：

```text
Academic Search Provider
→ Normalize
→ Literature Discovery Workflow
→ bounded Agent decisions
```

Tool 保持原子，不允许一个 Tool 同时完成理解需求、搜索、筛选、导入、报告生成和写作。

---

## RISK-003 — 当前 Project Workspace 产品面过载

Status: OPEN  
Priority: P0  
Owner Phase: Phase 1 / Phase 9

当前 `ProjectWorkspace.vue` 暴露了大量研究地图、证据矩阵、实验设计、写作产物、Agent 活动等功能。

风险：

- 用户主线不清楚。
- 新功能继续以 Tab 形式堆积。
- 前端复杂度持续集中在单页面。

V1 目标只保留：

```text
Overview
Discover
Papers
Writing
```

旧功能底层代码可暂时保留，但不再作为一级产品入口继续扩展。

---

## RISK-004 — Academic Search Provider 尚未最终选型

Status: OPEN  
Priority: P0  
Owner Phase: Phase 2

当前已有 arXiv 与 Semantic Scholar 相关能力，但尚未形成稳定的 V1 主搜索 Provider 策略。

需要在 Phase 2 开始时明确：

- Primary Provider
- Secondary / enrichment Provider
- rate limit
- API key / auth
- abstract coverage
- year / language / field / publication-type filter support
- open-access / PDF metadata support

候选包括：

- Semantic Scholar
- OpenAlex
- arXiv
- Crossref

不要求 V1 同时接入全部 Provider。

最终决策记录到：

`docs/spec-v2/08_IMPLEMENTATION_PROGRESS.md`

---

## RISK-005 — Citation Audit 不能等同于语义 Citation Verification

Status: OPEN  
Priority: P0  
Owner Phase: Phase 5

当前已有 citation audit / lexical 检查基础，但仅依靠字符或关键词重叠不足以判断：

> Evidence 是否真正支持 Generated Claim。

风险：

- 相关但不支持的 Evidence 被误判为可引用。
- 相关性被夸大为因果关系。
- 引用存在但 claim strength 超出来源。

处理方向：

```text
Referential Integrity
→ lexical / retrieval gate
→ semantic support verifier
→ verified / weak / unsupported
```

Lexical audit 保留为基础层，不推倒重写。

---

## RISK-006 — Project Context 仍有退化为“大 Prompt”的风险

Status: OPEN  
Priority: P0  
Owner Phase: Phase 4

V1 Context 必须明确分层：

```text
Project Profile
Literature Memory
Paper Profile
Evidence
Writing Context
```

风险：

- 全部 Project memory、论文、聊天、写作文档一次性塞给模型。
- 普通对话污染长期研究 Context。
- Writing 每次重新读取全部论文，成本和稳定性不可控。

处理方向：

- 引入 Context Manager。
- Paper Profile 用于候选论文筛选。
- Evidence 按需从真实全文检索。
- ordinary chat history 默认不作为长期 Writing Memory。

---

## RISK-007 — Paper Profile 与现有 `analysis_card` 可能形成重复模型

Status: OPEN  
Priority: P1  
Owner Phase: Phase 4

当前 `ProjectPaper.analysis_card` 已经具备结构化论文分析基础。

风险：

如果新建：

```text
PaperMemory
PaperProfileV2
PaperContextCard
```

会形成重复数据源。

处理方向：

优先将 `analysis_card` 演化为稳定 Paper Profile schema，并加入：

- schema version
- generation status
- provenance
- regeneration support

只有确认现有字段无法扩展后，才考虑新表。

---

## RISK-008 — Writing Agent 改造可能破坏现有编辑能力

Status: OPEN  
Priority: P0  
Owner Phase: Phase 6–8

当前分支已经有：

- Tiptap
- WritingDocument
- Revision
- Citation Node
- citation audit
- export

风险：

为了实现新的右侧 Writing Agent 而重造编辑器或修改持久化模型，可能破坏：

- revision
- undo
- citation node
- export
- existing document data

处理方向：

- 现有编辑器核心 KEEP。
- 只重构布局和 Agent interaction。
- Writing backend 新能力优先通过 Application Service 接入。
- Phase 6–8 必须有 revision/export regression tests。

---

## RISK-009 — 新 Project 主线可能破坏现有 Reader / RAG

Status: OPEN  
Priority: P0  
Owner Phase: Phase 1 / 4 / 8

用户已明确 V1 不重做 Reader。

风险：

- Project route 重构破坏 Reader 入口。
- Project Context 改造侵入旧 QA。
- 新 retrieval 逻辑替换旧 Hybrid Retrieval。

处理方向：

- `PaperReader.vue` 作为 V1 protected asset。
- Writing Evidence Retrieval 复用现有 Hybrid Retrieval。
- 不建立第二套向量库。
- Phase 1、4、8 做 Reader regression。

---

## RISK-010 — Search Provider 与 PDF Import 安全边界可能被混淆

Status: OPEN  
Priority: P0  
Owner Phase: Phase 2

搜索 API 可以返回任意论文页面和链接，但这不代表这些 URL 都可以被后端安全下载。

风险：

- 为了支持更多 Provider，把 `remote_paper_import.py` 变成 arbitrary URL downloader。
- SSRF / 非 PDF / 超大文件风险。
- 绕过 publisher access controls。

处理方向：

- Search Provider 与 Import Provider 分离。
- 保留 host allowlist、size limit、PDF magic bytes、temporary file cleanup。
- 无可批准全文来源时：
  - Download disabled
  - Import disabled

---

## RISK-011 — 旧文档与 `spec-v2` 权威冲突

Status: OPEN until Phase 0 completes  
Priority: P0  
Owner Phase: Phase 0

当前根 `AGENTS.md` 仍指向旧 `PROJECT_AGENT_IMPLEMENTATION_SPEC.md` 和 `PROJECT_AGENT_UPGRADE_CONTEXT.md` 作为主要施工依据。

风险：

Codex 在不同会话读取到互相冲突的产品与架构要求。

处理方向：

- 旧两份文档移动到 `docs/archive/`
- archive 文件加明确历史状态
- `AGENTS.md` 改为 `docs/spec-v2/` 优先
- 新施工状态只写入 `08_IMPLEMENTATION_PROGRESS.md`

Phase 0 完成后本风险应改为 CLOSED 或从本文删除。

---

## RISK-012 — 根 `AGENTS.md` 引用了当前不存在的前端规则文件

Status: OPEN  
Priority: P1  
Owner Phase: Phase 0

当前根 `AGENTS.md` 要求前端开发前读取：

```text
frontend/AGENTS.md
frontend/DESIGN_SYSTEM.md
```

但当前分支无法确认这两个文件存在。

风险：

- Codex 被要求读取不存在的路径。
- 前端规则来源不唯一。

处理方向：

- Phase 0 重写根 `AGENTS.md` 时删除硬编码的不存在路径。
- 前端设计权威改为：
  `docs/spec-v2/06_FRONTEND_DESIGN_SYSTEM_AND_PAGES.md`
- 若未来重新建立局部 `AGENTS.md`，必须确保真实存在且不与根规则冲突。

---

## RISK-013 — 当前 `ARCHITECTURE.md` 已落后于代码事实

Status: OPEN  
Priority: P1  
Owner Phase: Phase 0 / Phase 9

当前 `ARCHITECTURE.md` 仍主要描述早期 Reader / RAG 系统，虽然包含部分 Harness 和 Pinia 内容，但没有完整描述现有：

- application layer
- execution service
- Project models
- research/evidence models
- WritingDocument / revision
- Agent runtime evolution
- V1 migration boundary

处理方向：

- Phase 0 用“Current Architecture + V1 Migration Status”版本替换。
- Phase 9 再根据最终代码同步为稳定长期架构文档。

---

## RISK-014 — `API.md` 不完整，但不能提前写未来 API

Status: OPEN  
Priority: P1  
Owner Phase: Phase 1–9

当前 `API.md` 只覆盖部分认证、论文和聊天接口。

风险：

- Project / execution / writing 等当前真实 API 未完整记录。
- 如果现在直接写入未来 discovery/writing endpoint，会让文档再次失真。

处理方向：

- Phase 0 只增加文档状态与维护规则。
- 每个 Phase 在真实 API + tests 完成后同步 `API.md`。
- `API.md` 只记录已存在并经过测试的接口。

---

## Existing legacy risks requiring re-verification

旧文档中曾记录以下问题：

- auth path mismatch
- logout route mismatch
- reading-status route mismatch
- CORS overly broad
- noisy config logging
- parser section loss
- table extraction variable ordering
- local-vs-Docker storage differences
- dependency directories being committed

这些问题是否仍存在，必须在对应代码修改触及它们时重新检查。

不要在未重新验证当前分支的情况下把旧结论继续当作事实。

如果确认仍存在，再以新的 `RISK-XXX` 条目加入本文。

---

## Resolved / outdated entries removed from previous version

旧版本中的：

```text
“后端测试覆盖不足，当前只保留最小应用导入测试”
```

不再作为当前事实保留。

当前分支已经存在多类 Agent runtime、project、retrieval、evidence、remote import、writing 等测试基础。新的风险应针对**缺哪些关键路径测试**，而不是继续描述为“几乎没有测试”。

---

# Current V1 risk priorities

## P0

- lead_agent God Object
- literature_research God Object
- Project Workspace overload
- search provider selection
- citation verification quality
- context architecture
- Writing regression
- Reader/RAG regression
- remote import boundary
- documentation authority

## P1

- Paper Profile schema reuse
- ARCHITECTURE sync
- API documentation completeness
- missing frontend local-rule path

## P2

V1 主链稳定后再处理：

- old artifact enum cleanup
- dead Research Map / Experiment code cleanup
- legacy CSS cleanup
- non-core UX optimization
