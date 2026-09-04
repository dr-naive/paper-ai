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

## RISK-005 — Citation Audit 不能等同于语义 Citation Verification

Status: MITIGATED
Priority: P0
Owner Phase: Phase 5

Phase 5 已在既有 citation audit / lexical gate 后接入结构化 semantic support verifier，
并持久化 `verified / weak / unsupported`。残余风险是外部模型对复杂 claim、因果关系和证据
强度的判断仍需持续抽样评估：

> Evidence 是否真正支持 Generated Claim。

风险：

- 相关但不支持的 Evidence 被误判为可引用。
- 相关性被夸大为因果关系。
- 引用存在但 claim strength 超出来源。

当前保护：

```text
Referential Integrity
→ lexical / retrieval gate
→ semantic support verifier
→ verified / weak / unsupported
```

Lexical audit 保留为基础层；超时、无效响应、鉴权失败和限流不得标记为 verified。

---

## RISK-006 — Project Context 仍有退化为“大 Prompt”的风险

Status: MITIGATED
Priority: P0
Owner Phase: Phase 4

Phase 4 已落地并通过回归验证的 Context 分层：

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

当前保护：

- `ContextManager` 先构造 Project Profile / Literature Memory，再由 Paper Profile 缩小候选。
- Evidence 只按需从真实全文检索，不把全文或所有项目论文塞进单次 prompt。
- ordinary chat history 默认不作为长期 Writing Memory。
- 残余风险是后续新用例绕过这些边界；新增 Writing/Discovery 代码必须继续使用 typed services。

---

## RISK-008 — Writing Agent 改造可能破坏现有编辑能力

Status: MITIGATED
Priority: P0
Owner Phase: Phase 6–8

当前分支已经有并通过 Phase 6–8 回归验证：

- Tiptap
- WritingDocument
- Revision
- Citation Node
- citation audit
- export

仍需持续监控的残余风险：

为了实现新的右侧 Writing Agent 而重造编辑器或修改持久化模型，可能破坏：

- revision
- undo
- citation node
- export
- existing document data

当前保护：

- 现有编辑器核心 KEEP。
- 只重构布局和 Agent interaction。
- Writing backend 新能力优先通过 Application Service 接入。
- Phase 6–8 的 revision/export regression tests 已通过；Proposal 仍不会自动写入正文。

---

## RISK-009 — 新 Project 主线可能破坏现有 Reader / RAG

Status: MITIGATED
Priority: P0
Owner Phase: Phase 1 / 4 / 8

用户已明确 V1 不重做 Reader。

残余风险：后续 Project 路由或 Context 变更仍可能侵入 Reader/RAG。

- Project route 重构破坏 Reader 入口。
- Project Context 改造侵入旧 QA。
- 新 retrieval 逻辑替换旧 Hybrid Retrieval。

处理方向：

- `PaperReader.vue` 作为 V1 protected asset。
- Writing Evidence Retrieval 复用现有 Hybrid Retrieval。
- 不建立第二套向量库。
- Phase 1、4、8 的 Reader/RAG regression 已通过；后续改动仍必须复用同一套检索和 Reader 资产。

---

## RISK-010 — Search Provider 与 PDF Import 安全边界可能被混淆

Status: MITIGATED
Priority: P0
Owner Phase: Phase 2

搜索 API 可以返回任意论文页面和链接，但这不代表这些 URL 都可以被后端安全下载。

残余风险：新增 Provider 或 approved source 时仍可能错误扩大下载边界。

- 为了支持更多 Provider，把 `remote_paper_import.py` 变成 arbitrary URL downloader。
- SSRF / 非 PDF / 超大文件风险。
- 绕过 publisher access controls。

处理方向：

- Search Provider 与 Import Provider 分离。
- 保留 host allowlist、size limit、PDF magic bytes、temporary file cleanup。
- 无可批准全文来源时仍必须：
  - Download disabled
  - Import disabled

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

Phase 0 还消除了以下旧风险，因此不再保留为当前 OPEN 条目：

- 根 `AGENTS.md` 与旧 Agent 文档之间的权威冲突；
- 根 `AGENTS.md` 对不存在的前端局部规则文件的引用。

---

# Current V1 risk priorities

## P0

- lead_agent God Object
- literature_research God Object
- citation verification quality
- context architecture
- Writing regression
- Reader/RAG regression
- remote import boundary

## P1

- optional container egress still depends on host proxy listener binding if the enhancement is reopened; direct egress is the accepted V1 path (see `BLOCKER-004`)
- continued boundary regression checks for mitigated Reader/Writing/import risks

## P2

V1 主链稳定后再处理：

- old artifact enum cleanup
- dead Research Map / Experiment code cleanup
- legacy CSS cleanup
- non-core UX optimization
