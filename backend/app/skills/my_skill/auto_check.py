"""自动合规检查装饰器 - 确保每次响应前都执行检查"""
from functools import wraps
from typing import Callable, Any, Dict
import inspect
from .checker import ComplianceChecker


# 全局检查器实例
_global_checker = ComplianceChecker()


def enforce_compliance(func: Callable) -> Callable:
    """
    装饰器：在函数执行前强制进行合规检查
    
    使用方法：
    @enforce_compliance
    async def respond(user_message: str) -> str:
        return "回复内容"
    
    特性：
    - 自动检测用户语言（中文输入强制中文回复）
    - 检查权限边界
    - 代码生成前检查技术栈
    - 违规时阻止执行并返回警告
    """
    @wraps(func)
    async def async_wrapper(*args, **kwargs) -> Any:
        # 构建上下文
        context = _build_context(args, kwargs)
        
        # 执行合规检查
        result = _global_checker.check_all(context)
        
        # 如果检查失败且被阻止
        if result["blocked"]:
            # 生成违规提示
            warning_msg = _generate_warning(result)
            return warning_msg
        
        # 检查通过，执行原函数
        return await func(*args, **kwargs)
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs) -> Any:
        # 构建上下文
        context = _build_context(args, kwargs)
        
        # 执行合规检查
        result = _global_checker.check_all(context)
        
        # 如果检查失败且被阻止
        if result["blocked"]:
            # 生成违规提示
            warning_msg = _generate_warning(result)
            return warning_msg
        
        # 检查通过，执行原函数
        return func(*args, **kwargs)
    
    # 根据原函数是同步还是异步，返回对应的包装器
    if inspect.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper


def _build_context(args: tuple, kwargs: dict) -> Dict[str, Any]:
    """从函数参数构建检查上下文"""
    context = {}
    
    # 尝试从参数中提取关键信息
    for arg in args:
        if isinstance(arg, str):
            # 假设第一个字符串参数是用户消息
            if "user_message" not in context:
                context["user_message"] = arg
            elif "ai_response" not in context:
                context["ai_response"] = arg
    
    # 从 kwargs 中提取
    if "user_message" in kwargs:
        context["user_message"] = kwargs["user_message"]
    if "response" in kwargs:
        context["ai_response"] = kwargs["response"]
    if "action" in kwargs:
        context["action"] = kwargs["action"]
    if "command" in kwargs:
        context["command"] = kwargs["command"]
    if "file_path" in kwargs:
        context["file_path"] = kwargs["file_path"]
    
    return context


def _generate_warning(result: Dict[str, Any]) -> str:
    """生成违规警告消息"""
    lines = ["⚠️ **合规检查未通过**\n"]
    
    for violation in result["violations"]:
        lines.append(f"\n**{violation['rule_id']}** ({violation['severity']})")
        lines.append(f"- {violation['message']}")
        lines.append(f"- 建议: {violation['suggestion']}")
    
    lines.append("\n请修正以上问题后重新操作。")
    
    return "\n".join(lines)


def auto_check_before_response(user_message: str, planned_response: str = "", 
                               action: str = "", command: str = "", 
                               file_path: str = "") -> Dict[str, Any]:
    """
    便捷函数：手动触发合规检查
    
    Args:
        user_message: 用户消息
        planned_response: 计划的回复内容
        action: 计划执行的操作
        command: 计划执行的命令
        file_path: 涉及的文件路径
    
    Returns:
        检查结果，包含 passed、blocked、violations、messages
    """
    context = {
        "user_message": user_message,
        "ai_response": planned_response,
        "action": action,
        "command": command,
        "file_path": file_path,
        "is_code_generation": "代码" in action or "生成" in action or "write" in action.lower()
    }
    
    return _global_checker.check_all(context)


# 导出
__all__ = ["enforce_compliance", "auto_check_before_response"]
