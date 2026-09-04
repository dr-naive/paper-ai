# 论文内部信息查询

## 何时使用
当用户问题涉及**当前论文自身**的内容时使用,包括:
- 元数据(标题/作者/摘要/年份/DOI/venue/关键词)
- 章节结构与大纲(标题/起始页/包含的图表)
- 正文检索(方法/实验/结果/讨论等)
- 表格数据查询("表3中方法A的F1")
- 基于表格的数值计算(最高/最低/平均)
- 引用格式导出(BibTeX/GB-T 7714/EndNote/RIS)

## 何时不使用
- 用户问的是论文**外部**信息(基线原论文、相关工作、被引、follow-up)→ 用 `external_literature` skill
- 用户要"规划阅读路径""做笔记""术语卡片""读到哪了"→ 用 `reading_assistant` skill
- 用户要"写审稿意见""critique""评估创新性""多步证据整合"→ 调用 `task` 工具委派 critique subagent

## 可用工具
- `get_paper_metadata`: 获取论文元数据(标题/作者/摘要/年份/DOI/venue)
- `list_paper_sections`: 列出章节大纲(标题/起始页/图表数量/字数)
- `search_paper_content`: 语义+精确混合检索正文(支持多轮调用)
- `lookup_table_data`: 精确查指定编号表格(如 表3)
- `compute_over_tables`: 基于表格做确定性算术(最高/最低/平均)
- `export_citation_format`: 导出引用格式(BibTeX/GB-T 7714/EndNote/RIS)

## 典型调用模式

### 1. 元数据类问题
用户问"作者是谁""标题是什么""发表在哪""DOI"→ 直接调 `get_paper_metadata`

### 2. 表格数值问题
用户问"表3里哪个方法F1最高"→ 先调 `lookup_table_data(table_number=3)`,再调 `compute_over_tables(question="表3里哪个方法F1最高")`
注:`compute_over_tables` 会自动从 question 解析表号,所以两步可以合并成一步调 `compute_over_tables`。

### 3. 方法/实验/结果等正文问题
用户问"用了什么损失函数""实验用了哪些数据集""主要贡献"→ 调 `search_paper_content(query=...)`
若一次检索不够,可多次调用,每次聚焦不同子问题。

### 4. 章节结构问题
用户问"论文有哪些章节""方法在第几页""哪章有图表"→ 调 `list_paper_sections`

### 5. 引用导出
用户问"给我 BibTeX""导出引用"→ 调 `export_citation_format(format="bibtex")`

## 引用规范
回答正文问题时,每个关键结论后标注来源编号 `[S1]`、`[S2]`,编号来自 `search_paper_content` 返回的 `source_id` 字段。这些编号会被后端解析成 PDF 定位信息。
