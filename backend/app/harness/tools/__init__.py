"""Harness 工具集合。

设计模式:**工厂函数 + 闭包注入 db**。

每个 tool 工厂接受 `AsyncSession`,返回绑定 db 的 LangChain tool 实例列表。
- LLM 看到的 schema 干净(只有业务参数,无 db)
- db 通过闭包注入,生命周期由调用方(API/agent)管理
- 每次请求创建一组 tool 实例(轻量)

使用示例:
    from app.harness.tools.paper_internal import make_paper_internal_tools
    tools = make_paper_internal_tools(db)
    # tools 可传给 LangChain agent / ToolNode / 直接 .ainvoke()
"""
