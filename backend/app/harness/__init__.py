"""PaperAI Agent Harness —— agent 运行时与网关层解耦。

本包承载 agent 相关能力(tools / skills / agents / middlewares),与
`app/api/` 网关层解耦。harness 只依赖 SQLAlchemy 异步 session 抽象,
不依赖 FastAPI/HTTP 层,便于脱离 Web 单测与未来扩展 CLI/IM 接入。

当前阶段(期 1):只实现 tool 解耦,不引入 agent loop。
"""
