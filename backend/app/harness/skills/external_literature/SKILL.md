# 外部文献检索

## 何时使用
当用户问题涉及**论文边界之外**的信息时使用,包括:
- 论文里提到的 baseline / 相关工作,用户想知道原论文是哪篇
- 查论文的引用关系(引用了谁 / 被谁引用)
- 查相关论文 / 类似方法 / follow-up 工作
- 查论文的被引次数 / 影响力

## 何时不使用
- 用户问的是**当前论文自身**内容 → 用 `paper_internal` skill
- 用户要引用格式导出(BibTeX)→ 用 `paper_internal.export_citation_format`

## 可用工具
- `search_arxiv`: 按 title/作者/关键词查 arXiv 论文,返回标题/作者/摘要/arxiv_id/PDF链接
- `search_semantic_scholar`: 查引用关系(references/citations/related),返回引用图谱

## 候选论文输出规范

返回外部候选论文时，必须让用户能判断“这篇论文是什么、为什么相关、下一步能做什么”：

- 论文标题必须是可点击链接：`[Title](https://arxiv.org/abs/<arxiv_id>)`，并在标题旁保留 arXiv ID。
- 每篇至少展示作者（工具返回时）、年份、与当前研究问题的匹配点、摘要能够支持的判断、筛选决定与理由。
- 明确区分 `include`、`maybe`、`exclude`，不要只用星级；摘要只能用于相关性初筛，不能写成全文已经证实的结论。
- 候选超过 5 篇时，先给紧凑的筛选总览，再按 `include`、`maybe`、`exclude` 分组说明，避免重复两遍相同长文。
- 结尾给出明确操作：继续补充检索，或将哪些 arXiv ID 导入项目。不要声称前端存在尚未实现的“一键导入”按钮。

## 典型调用模式

### 1. 查 baseline 原论文
用户问"论文里提到的 baseline 'IFDL' 是什么方法,原论文是哪篇"
1. 先调 `search_paper_content(query="IFDL")` 在本文定位相关段落,拿到作者/年份/关键词线索
2. 再调 `search_arxiv(query="...")` 用线索搜外部
3. 汇总返回:方法说明 + 原论文信息 + PDF 链接

### 2. 查 follow-up 工作
用户问"这篇论文有哪些 follow-up"
1. 调 `get_paper_metadata` 拿本文 title
2. 调 `search_semantic_scholar(paper_title=..., field="citations")` 查引用本文的后续论文
3. 返回 follow-up 列表(标题/作者/年份/被引)

### 3. 查相关工作
用户问"最近有没有类似方法的论文"
1. 调 `search_arxiv(query="方法关键词")` 检索
2. 可选再调 `search_semantic_scholar` 补充引用关系

## 降级策略
- 外部 API(arXiv/Semantic Scholar)可能限流或不可用
- tool 失败时,告知用户"外部服务暂不可用",并基于论文本身能查到的信息回答
- 不要因外部 API 失败而完全拒绝回答

## 注:工具实现状态
当前(期 3)`search_arxiv` 和 `search_semantic_scholar` 已实现并接入 lead_agent。
arXiv API 稳定可用;Semantic Scholar 有 rate limit(~100 req/5min),失败时优雅降级。
