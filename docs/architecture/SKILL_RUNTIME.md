# Skill Runtime V1

Skill 是声明式研究方法，不是一个大函数。每个已迁移 Skill 同时包含 `SKILL.md` 和
`skill.yaml`；YAML 固定描述语义版本、标准 Tool 白名单、权限、预算、完成条件及完成元数据。

`SkillRuntime` 使用严格 Pydantic schema 和安全 YAML 解析，加载时检查目录与 ID 一致、
SemVer、重复工具、工具是否注册，以及 network/destructive 权限是否覆盖 Tool 的副作用。
运行时只允许白名单中的 Tool，并在调用前检查预算。当前声明式 Skill 包括
`paper_internal`、`external_literature`、`literature_research`、
`writing_evidence_generation`；其中
`literature_research` 只编排原子 Tool，并遵守
`docs/spec-v2/features/LITERATURE_DISCOVERY.md`。兼容 `project_*` 工具不得绕过
当前 Evidence、Memory、Writing、权限和审计边界。

`SkillRuntime.evaluate_completion` 对声明的全部 criteria 和 required metadata 生成版本化、
可解释的 `SkillCompletionReport`。Writing durable execution 必须先激活
`writing_evidence_generation`，Reviewer 通过或完成最多一次 repair 后执行 completion eval；
只有 completion report 通过，Completion Gate 才允许执行进入 `completed`。

Goal-driven Task 还声明 `supported_task_types`、`required_inputs`、`produced_artifacts`、
`allowed_tools`、`completion_criteria`、`max_tool_calls` 和 `max_model_calls`。Task executor
在执行前校验 Task 类型与输入，Lead Agent 每次 ToolCall 再执行 task scope、Project/Paper
ownership 与预算校验；越界调用拒绝并写入 execution trace。Skill 只约束当前 Task，不拥有整个
ResearchExecution 的生命周期。
