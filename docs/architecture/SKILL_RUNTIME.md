# Skill Runtime V1

Skill 是声明式研究方法，不是一个大函数。每个已迁移 Skill 同时包含 `SKILL.md` 和
`skill.yaml`；YAML 固定描述语义版本、标准 Tool 白名单、权限、预算、完成条件及完成元数据。

`SkillRuntime` 使用严格 Pydantic schema 和安全 YAML 解析，加载时检查目录与 ID 一致、
SemVer、重复工具、工具是否注册，以及 network/destructive 权限是否覆盖 Tool 的副作用。
运行时只允许白名单中的 Tool，并在调用前检查预算。首批迁移：`paper_internal`、
`external_literature`、`literature_research`。其中
首批迁移包括 `paper_internal`、`external_literature`、`literature_research`。其中
`literature_research` 应只编排原子 Tool；后续 Literature Discovery 重构以
`docs/spec-v2/04_LITERATURE_DISCOVERY.md` 为准。
原子 Tool；原有 `project_*` 大工具暂留兼容入口，后续按 Evidence/Memory/Writing 阶段逐项替换。
