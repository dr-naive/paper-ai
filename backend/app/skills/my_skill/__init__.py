"""个人助手约束规则 Skill - v2.0"""
from .checker import (
    ComplianceChecker,
    check_compliance,
    generate_downgrade_options,
    ask_tech_stack
)
from .auto_check import (
    enforce_compliance,
    auto_check_before_response
)

__version__ = "2.0.0"
__all__ = [
    # 检查器类和函数
    "ComplianceChecker",
    "check_compliance",
    "generate_downgrade_options",
    "ask_tech_stack",
    
    # 自动检查功能
    "enforce_compliance",
    "auto_check_before_response"
]

# 自动执行检查（模块导入时）
print("✅ 个人助手约束规则已加载 - 版本 2.0.0")
print("   规则数量: 15 条")
print("   自动检查: 已启用")
