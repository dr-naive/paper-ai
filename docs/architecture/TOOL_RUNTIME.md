# Tool Runtime V1

`app.harness.runtime` 是 Agent 调用原子能力的标准边界。运行时上下文固定携带
`user_id / project_id / execution_id`，这些身份字段不能来自模型参数。

首批标准工具：`paper.get_metadata`、`paper.get_outline`、
`paper.search_content`、`project.list_papers`、`project.search_content`、
`literature.search_external`。

每次调用先验证 execution 和资源所有权，再验证 Pydantic 输入；执行受超时与取消控制，
结果统一为 `ToolResult`，调用参数、状态、摘要及错误会写入 `tool_calls`。Redis 控制键只用于
快速取消，PostgreSQL trace 是审计事实来源。现有 LangChain tools 暂时保留兼容，由标准工具
适配器复用其底层检索实现；Skill Runtime 迁移完成前不删除旧入口。
