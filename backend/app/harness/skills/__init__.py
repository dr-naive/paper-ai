"""Harness Skills —— 能力发现与按需加载机制。

每个 skill 是一个目录,包含:
- SKILL.md: Markdown 格式的能力说明,LLM 可读,运行时注入 system prompt
- (可选) tools.py: 该 skill 绑定的 tool 工厂

skill 不绑定固定 tool,而是通过 manifest 字段声明它提供哪些 tool。
SkillRegistry 负责扫描发现、按需加载,并把 SKILL.md 内容拼进 agent prompt。

当前阶段(期 2):
- paper_internal: 已实现(期 1 完成 6 个 tool)
- external_literature / reading_assistant: SKILL.md 先建,tool 留到期 3
"""
