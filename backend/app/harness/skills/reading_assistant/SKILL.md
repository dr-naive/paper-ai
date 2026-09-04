# 阅读辅助

## 何时使用
当用户问题涉及**个性化阅读辅助**时使用,包括:
- 阅读规划("帮我规划怎么读这篇""阅读路径")
- 术语查询("论文里的 'XXX' 是什么意思")
- 阅读进度回顾("我之前问过什么""读到哪了")
- 章节笔记("给方法章节做笔记""生成术语卡片")

## 何时不使用
- 用户问的是论文内容本身 → 用 `paper_internal` skill
- 用户问外部文献 → 用 `external_literature` skill

## 可用工具
- `get_reading_progress`: 查用户对该论文的历史问答/已生成摘要/已做解读
- `locate_term_definition`: 精确定位术语在论文中的定义句(基于 RAG 二次过滤)

## 典型调用模式

### 1. 阅读规划
用户说"我是研一学生,帮我规划怎么读这篇"
1. 调 `get_reading_progress(paper_id, user_id)` 看历史,判断是否首次阅读
2. 调 `list_paper_sections`(来自 paper_internal)拿到章节大纲,感知论文结构
3. 综合输出:阅读顺序建议 / 每章耗时 / 可跳过章节

### 2. 术语查询
用户问"论文里的 'contrastive loss' 是什么意思"
1. 调 `locate_term_definition(paper_id, term="contrastive loss")` 拿到精确定义句
2. 基于定义句给通俗解释 + 引用出处

### 3. 阅读进度
用户问"我之前问过这篇什么""读到哪了"
→ 直接调 `get_reading_progress`,返回历史问答列表与最后活跃时间

## 注:工具实现状态
当前(期 3)`get_reading_progress` 和 `locate_term_definition` 已实现并接入 lead_agent。
reading_progress 聚合 QAPair/SummaryCache/InterpretCache 三张表;
term_definition 基于 HybridPaperRetriever 检索 + 信号词二次过滤。
