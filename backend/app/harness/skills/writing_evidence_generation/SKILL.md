# Evidence-backed Writing Generation

内部 Writing Skill。它从当前 Project 已导入、完成解析且可检索的论文中收窄上下文，生成一个
段落，并保留结构化 Evidence/Citation 映射。

执行顺序固定为：Project Context → draft → Writing Reviewer → 最多一次 repair → Evidence
持久化 → Citation Verification → Skill completion eval → Completion Gate。

不得搜索外部网络、引用 Discover-only 结果、静默覆盖编辑器正文或进行第二次 repair。
