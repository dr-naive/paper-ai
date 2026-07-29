"""个人助手约束规则 - 合规检查器"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import json
import re
from pathlib import Path

DEFAULT_WORKSPACE = str(Path(__file__).resolve().parents[4])


@dataclass
class Violation:
    """违规记录"""
    rule_id: str
    severity: str  # CRITICAL, HIGH, MEDIUM
    message: str
    suggestion: str
    blocked: bool


class ComplianceChecker:
    """
    合规检查器 - 在每次回答前自动执行
    
    检查规则:
    1. 语言规范 - 中文输入/输出
    2. 降级禁令 - 禁止自行降级方案
    3. 权限边界 - 只能在项目目录操作
    4. 需求澄清 - 禁止模糊操作
    5. 信息诚实 - 如实回答
    6. 技术栈确认 - 生成代码前确认技术栈
    7. 代码风格一致性 - 遵循项目代码风格
    8. 依赖预检 - 检查依赖需求
    9. 类型安全检查 - 强类型检查
    10. 命名规范检测 - 保持命名一致
    11. 分步执行策略 - 复杂任务拆分
    12. 增量修改原则 - 优先Edit
    13. 代码复用优先 - 引用现有代码
    14. Token优化 - 精简输出
    """
    
    def __init__(self, workspace: Optional[str] = None):
        self.workspace = workspace or DEFAULT_WORKSPACE
        self.violations: List[Violation] = []
        self.user_language = "zh"  # 默认中文
        self.last_context = {}
    
    def check_all(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行所有检查
        
        Args:
            context: 上下文，包含:
                - user_message: 用户消息
                - ai_response: AI 响应（如果已有）
                - action: 计划执行的操作
                - command: 计划执行的命令
                - file_path: 涉及的文件路径
                - is_code_generation: 是否生成代码
                - tech_stack_confirmed: 技术栈是否已确认
        
        Returns:
            检查结果
        """
        self.violations = []
        self.last_context = context
        
        # 基础行为规则
        self._check_language(context)
        self._check_downgrade(context)
        self._check_permissions(context)
        self._check_clarity(context)
        self._check_honesty(context)
        
        # 代码生成优化规则
        if context.get("is_code_generation", False):
            self._check_tech_stack(context)
            self._check_code_style(context)
            self._check_dependencies(context)
            self._check_type_safety(context)
            self._check_naming(context)
            self._check_step_by_step(context)
            self._check_incremental(context)
            self._check_code_reuse(context)
            self._check_token_optimization(context)
        
        # 判断是否阻塞
        has_critical = any(v.severity == "CRITICAL" for v in self.violations)
        
        return {
            "passed": len(self.violations) == 0,
            "violations": [self._violation_to_dict(v) for v in self.violations],
            "blocked": has_critical,
            "messages": self._generate_messages()
        }
    
    def _check_language(self, context: Dict[str, Any]):
        """检查语言规范 - 统一使用中文回复"""
        user_message = context.get("user_message", "")
        ai_response = context.get("ai_response", "")
        
        if ai_response:
            # 提取纯文本内容（排除代码块）
            text_without_code = self._remove_code_blocks(ai_response)
            
            # 检查回复中是否包含中文
            has_chinese = bool(re.search(r'[\u4e00-\u9fff]', text_without_code))
            
            # 判断是否为纯技术信息（错误日志、堆栈跟踪等）
            is_pure_tech_info = self._is_pure_technical_info(ai_response)
            
            # 如果不是纯技术信息且没有中文 → 违规
            if not is_pure_tech_info and not has_chinese:
                self.violations.append(Violation(
                    rule_id="LANGUAGE_POLICY",
                    severity="CRITICAL",
                    message="回复未使用中文",
                    suggestion="请使用中文回复用户（代码和专有名词可保持英文）",
                    blocked=True
                ))
    
    def _remove_code_blocks(self, text: str) -> str:
        """移除代码块，只保留纯文本"""
        # 移除 ```code``` 格式的代码块
        text = re.sub(r'```[\s\S]*?```', '', text)
        # 移除 `code` 格式的行内代码
        text = re.sub(r'`[^`]+`', '', text)
        return text
    
    def _is_pure_technical_info(self, text: str) -> bool:
        """判断是否为纯技术信息（错误日志、堆栈跟踪等）"""
        tech_keywords = [
            'Error', 'Exception', 'Traceback', 'File "/', 'ModuleNotFound',
            'SyntaxError', 'TypeError', 'AttributeError', 'ValueError',
            'ImportError', 'PermissionError', 'ConnectionError',
            'HTTPError', '500 Internal Server Error', '404 Not Found',
            'Traceback (most recent call last):', 'line ', 'in <module>'
        ]
        
        # 如果包含多个技术关键字，认为是纯技术信息
        tech_count = sum(1 for kw in tech_keywords if kw in text)
        return tech_count >= 2
    
    def _check_downgrade(self, context: Dict[str, Any]):
        """检查降级禁令"""
        action = context.get("action", "")
        user_approved = context.get("user_approved", False)
        
        downgrade_keywords = ["降级", "fallback", "降级方案", "简化", "使用备选", "使用替代", "使用简化版"]
        is_downgrade = any(kw in str(action).lower() for kw in downgrade_keywords)
        
        if is_downgrade and not user_approved:
            self.violations.append(Violation(
                rule_id="NO_UNAUTHORIZED_DOWNGRADE",
                severity="CRITICAL",
                message="检测到未经授权的降级行为",
                suggestion="请先向用户介绍方案 A 和 B（含优劣势），等待用户选择",
                blocked=True
            ))
    
    def _check_permissions(self, context: Dict[str, Any]):
        """检查权限边界"""
        command = context.get("command", "")
        file_path = context.get("file_path", "")
        
        restricted_commands = ["sudo", "chmod", "chown", "rm -rf /", "apt-get", "yum", "dnf", "apt install",
                               "npm install -g", "pip install --global", "systemctl", "service "]
        system_paths = ["/root", "/etc", "/usr", "/var", "/boot", "/sys"]
        
        if command:
            cmd_str = str(command).lower()
            for restricted in restricted_commands:
                if restricted in cmd_str:
                    self.violations.append(Violation(
                        rule_id="PERMISSION_BOUNDARY",
                        severity="CRITICAL",
                        message=f"命令 '{command}' 需要管理员权限或被禁止",
                        suggestion="该命令需要管理员权限或不在允许范围内，请提供手动执行步骤",
                        blocked=True
                    ))
                    return
        
        if file_path:
            for sys_path in system_paths:
                if file_path.startswith(sys_path):
                    self.violations.append(Violation(
                        rule_id="PERMISSION_BOUNDARY",
                        severity="CRITICAL",
                        message=f"路径 '{file_path}' 超出工作目录范围",
                        suggestion=f"只能在项目目录 {self.workspace} 内操作",
                        blocked=True
                    ))
                    return
            
            if not file_path.startswith(self.workspace):
                self.violations.append(Violation(
                    rule_id="PERMISSION_BOUNDARY",
                    severity="HIGH",
                    message=f"路径 '{file_path}' 不在工作目录内",
                    suggestion=f"建议将操作限制在 {self.workspace} 目录内",
                    blocked=False
                ))
    
    def _check_clarity(self, context: Dict[str, Any]):
        """检查需求清晰度"""
        user_message = context.get("user_message", "")
        vague_keywords = ["这个", "那个", "它", "它们", "这个文件", "那个函数"]
        has_vague = any(kw in user_message for kw in vague_keywords)
        
        if has_vague:
            has_context = context.get("has_context", False)
            if not has_context:
                self.violations.append(Violation(
                    rule_id="CLARIFY_BEFORE_ACTION",
                    severity="HIGH",
                    message="需求描述不够清晰",
                    suggestion="请先向用户确认具体指什么（如：文件名、函数名、具体需求）再执行操作",
                    blocked=True
                ))
    
    def _check_honesty(self, context: Dict[str, Any]):
        """检查信息诚实"""
        response = context.get("ai_response", "")
        
        if response:
            uncertainty_phrases = ["应该是", "大概", "可能", "也许", "应该可以"]
            has_uncertainty = any(phrase in response for phrase in uncertainty_phrases)
            
            if has_uncertainty and not self._has_qualifier(response):
                self.violations.append(Violation(
                    rule_id="HONEST_INFORMATION",
                    severity="MEDIUM",
                    message="回复包含不确定表述",
                    suggestion="请明确说明是基于现有信息的推测，还是确定的事实",
                    blocked=False
                ))
    
    def _has_qualifier(self, text: str) -> bool:
        """检查文本是否包含不确定性修饰词"""
        qualifiers = ["根据现有信息", "推测", "可能", "不确定", "我的理解是", "基于代码分析"]
        return any(q in text for q in qualifiers)
    
    def _check_tech_stack(self, context: Dict[str, Any]):
        """检查技术栈确认"""
        tech_stack_confirmed = context.get("tech_stack_confirmed", False)
        
        if not tech_stack_confirmed:
            self.violations.append(Violation(
                rule_id="TECH_STACK_CONFIRMATION",
                severity="CRITICAL",
                message="代码生成前未确认技术栈",
                suggestion="请先确认：1)编程语言 2)框架和版本 3)代码风格偏好 4)依赖管理工具",
                blocked=True
            ))
    
    def _check_code_style(self, context: Dict[str, Any]):
        """检查代码风格一致性"""
        code = context.get("code", "")
        
        if code:
            # 检查混合缩进（空格和制表符）
            has_spaces = '    ' in code
            has_tabs = '\t' in code
            
            if has_spaces and has_tabs:
                self.violations.append(Violation(
                    rule_id="CODE_STYLE_CONSISTENCY",
                    severity="HIGH",
                    message="代码中混合使用空格和制表符缩进",
                    suggestion="请统一使用空格或制表符缩进",
                    blocked=False
                ))
    
    def _check_dependencies(self, context: Dict[str, Any]):
        """检查依赖预检"""
        code = context.get("code", "")
        new_dependencies = context.get("new_dependencies", [])
        
        if new_dependencies:
            self.violations.append(Violation(
                rule_id="DEPENDENCY_CHECK",
                severity="HIGH",
                message=f"代码需要新依赖: {', '.join(new_dependencies)}",
                suggestion="请列出依赖清单并等待用户确认是否安装",
                blocked=False
            ))
    
    def _check_type_safety(self, context: Dict[str, Any]):
        """检查类型安全"""
        code = context.get("code", "")
        language = context.get("language", "")
        
        if code and language in ["python", "typescript", "go", "java"]:
            # 简单检查是否有类型注解
            if language == "python":
                # 检查函数定义是否有类型注解
                func_pattern = r'def\s+\w+\s*\([^)]*\)\s*(->\s*\w+)?:'
                matches = re.findall(func_pattern, code)
                for match in matches:
                    if not match:  # 没有返回类型注解
                        self.violations.append(Violation(
                            rule_id="TYPE_SAFETY",
                            severity="HIGH",
                            message="Python函数缺少类型注解",
                            suggestion="请为函数参数和返回值添加类型注解",
                            blocked=False
                        ))
                        break
    
    def _check_naming(self, context: Dict[str, Any]):
        """检查命名规范"""
        code = context.get("code", "")
        
        if code:
            # 检查变量命名是否一致
            snake_case_vars = re.findall(r'\b[a-z_][a-z0-9_]*\b', code)
            camel_case_vars = re.findall(r'\b[a-z][a-zA-Z0-9]*\b', code)
            
            has_snake_case = len(snake_case_vars) > 3
            has_camel_case = len(camel_case_vars) > 3
            
            if has_snake_case and has_camel_case:
                self.violations.append(Violation(
                    rule_id="NAMING_CONVENTION",
                    severity="HIGH",
                    message="代码中混合使用下划线命名和驼峰命名",
                    suggestion="请统一命名风格（下划线式或驼峰式）",
                    blocked=False
                ))
    
    def _check_step_by_step(self, context: Dict[str, Any]):
        """检查分步执行策略"""
        file_count = context.get("file_count", 0)
        code_lines = context.get("code_lines", 0)
        
        if file_count > 3 or code_lines > 50:
            step_by_step = context.get("step_by_step", False)
            
            if not step_by_step:
                self.violations.append(Violation(
                    rule_id="STEP_BY_STEP",
                    severity="HIGH",
                    message=f"任务涉及 {file_count} 个文件或 {code_lines} 行代码，建议分步执行",
                    suggestion="请将任务拆分为多个步骤，每步完成后确认再继续",
                    blocked=False
                ))
    
    def _check_incremental(self, context: Dict[str, Any]):
        """检查增量修改原则"""
        action = context.get("action", "")
        
        if "write" in action.lower() and "edit" not in action.lower():
            file_exists = context.get("file_exists", False)
            
            if file_exists:
                self.violations.append(Violation(
                    rule_id="INCREMENTAL_MODIFICATION",
                    severity="HIGH",
                    message=f"计划重写已存在的文件",
                    suggestion="请优先使用 Edit 修改而非 Write 重写，保留现有代码结构",
                    blocked=False
                ))
    
    def _check_code_reuse(self, context: Dict[str, Any]):
        """检查代码复用"""
        code = context.get("code", "")
        existing_functions = context.get("existing_functions", [])
        
        if code and existing_functions:
            # 检查是否实现了已存在的功能
            for func in existing_functions:
                if func.lower() in code.lower():
                    self.violations.append(Violation(
                        rule_id="CODE_REUSE",
                        severity="HIGH",
                        message=f"代码中实现了可能已存在的功能: {func}",
                        suggestion="请检查项目中是否已有类似功能，优先复用现有代码",
                        blocked=False
                    ))
                    break
    
    def _check_token_optimization(self, context: Dict[str, Any]):
        """检查Token优化"""
        response_length = context.get("response_length", 0)
        code_ratio = context.get("code_ratio", 0)
        
        if response_length > 2000 and code_ratio < 0.5:
            self.violations.append(Violation(
                rule_id="TOKEN_OPTIMIZATION",
                severity="MEDIUM",
                message="回复过于冗长，代码占比不足",
                suggestion="请精简文字描述，代码块优先，使用行内注释",
                blocked=False
            ))
    
    def _violation_to_dict(self, v: Violation) -> Dict[str, Any]:
        """转换违规对象为字典"""
        return {
            "rule_id": v.rule_id,
            "severity": v.severity,
            "message": v.message,
            "suggestion": v.suggestion,
            "blocked": v.blocked
        }
    
    def _generate_messages(self) -> List[str]:
        """生成违规消息列表"""
        messages = []
        
        critical = [v for v in self.violations if v.severity == "CRITICAL"]
        high = [v for v in self.violations if v.severity == "HIGH"]
        medium = [v for v in self.violations if v.severity == "MEDIUM"]
        
        if critical:
            messages.append(f"⚠️ 严重违规 ({len(critical)} 项):")
            for v in critical:
                messages.append(f"  - {v.rule_id}: {v.message}")
                messages.append(f"    → {v.suggestion}")
        
        if high:
            messages.append(f"⚡ 高优先级 ({len(high)} 项):")
            for v in high:
                messages.append(f"  - {v.rule_id}: {v.message}")
        
        if medium:
            messages.append(f"💡 建议 ({len(medium)} 项):")
            for v in medium:
                messages.append(f"  - {v.message}")
        
        return messages


# 全局实例
_checker = ComplianceChecker()


def check_compliance(context: Dict[str, Any]) -> Dict[str, Any]:
    """便捷函数：执行合规检查"""
    return _checker.check_all(context)


def generate_downgrade_options(original: str, alternatives: List[Dict[str, str]]) -> str:
    """生成降级方案介绍"""
    lines = ["\n📋 提供以下方案供选择：\n"]
    
    for i, alt in enumerate(alternatives, 1):
        lines.append(f"**方案 {chr(66+i-1)}**: {alt['name']}")
        lines.append(f"- ✅ 优势: {alt.get('pros', '无')}")
        lines.append(f"- ❌ 劣势: {alt.get('cons', '无')}")
        lines.append(f"- 📊 成功率: {alt.get('success', '未知')}")
        lines.append(f"- 🎯 预计难度: {alt.get('difficulty', '未知')}")
        lines.append("")
    
    lines.append("请选择: A / B")
    return "\n".join(lines)


def ask_tech_stack() -> str:
    """生成技术栈确认询问"""
    return """
为了确保代码适配，请确认以下信息：

1. 项目使用的编程语言是什么？（如：Python、Node.js、Go、Java）
2. 使用的主要框架和版本？（如：FastAPI 0.100、React 18）
3. 代码风格偏好？（缩进：空格/制表符，引号：单/双/反引号，分号：需要/不需要）
4. 是否有现有的代码规范文档？

请提供这些信息，我会确保生成的代码完全适配您的项目！
"""
