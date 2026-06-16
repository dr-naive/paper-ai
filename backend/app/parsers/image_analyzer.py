"""多模态图片分析器 - 使用 LLM 理解图片内容"""

import base64
import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)


class ImageAnalyzer:
    """使用多模态 LLM 分析图片内容"""

    def __init__(self, model: Optional[str] = None):
        self.model = model or settings.VISION_MODEL
        self.api_key = settings.OPENAI_API_KEY
        self.base_url = settings.VISION_BASE_URL
        self.client = None

    def _get_client(self):
        """延迟初始化客户端"""
        if self.client is None:
            try:
                from openai import AsyncOpenAI
                self.client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url
                )
                logger.info(f"✅ 视觉模型客户端初始化成功: {self.model}")
            except ImportError:
                logger.error("❌ 需要安装 openai 库: pip install openai")
                raise
        return self.client

    def _encode_image(self, image_path: str) -> str:
        """将图片转为 base64 编码"""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    async def analyze_image(
        self,
        image_path: str,
        prompt: str = None,
        context: str = ""
    ) -> Dict[str, Any]:
        """
        分析图片内容

        Args:
            image_path: 图片文件路径
            prompt: 分析提示词（可选，使用默认标准化 Prompt）
            context: 上下文信息（如章节标题）

        Returns:
            {
                "success": true,
                "image_type": "chart|architecture|experiment|other",
                "chart_type": "折线图|柱状图|饼图|散点图|热力图|其他",
                "key_data_points": ["关键数据点1", "关键数据点2"],
                "core_conclusion": "核心结论",
                "role_in_paper": "该图在论文中的作用",
                "description": "图片描述",
                "qa_context": "用于问答的上下文"
            }
        """
        try:
            client = self._get_client()
            base64_image = self._encode_image(image_path)

            # 使用标准化 Prompt
            if prompt is None:
                prompt = """你是一个学术图表分析专家。请分析这张图片，并按以下 JSON 格式输出：

{
    "success": true,
    "image_type": "图表类型（如：折线图、柱状图、饼图、散点图、热力图、架构图、流程图、实验结果图、其他）",
    "chart_type": "具体图表类型（如：折线图、柱状图、饼图、散点图、热力图、架构图、流程图、实验结果图、其他）",
    "key_data_points": [
        "关键数据点1（如：最高点、最低点、转折点等）",
        "关键数据点2"
    ],
    "core_conclusion": "从图片中得出的核心结论（1-2句话）",
    "role_in_paper": "该图在论文中的作用（如：展示实验结果、说明方法流程、对比不同方法等）",
    "description": "对图片的详细描述（包括坐标轴、图例、数据趋势等）"
}

注意事项：
1. 必须返回纯 JSON 格式，不要包含任何其他文字
2. 如果图片不是图表，image_type 和 chart_type 填 "其他"
3. key_data_points 提取图片中的关键数据或信息点
4. core_conclusion 要简洁明了，直接说明图片要表达的核心观点
5. role_in_paper 要说明这张图在论文中的学术意义"""

            # 构建完整提示词
            full_prompt = prompt
            if context:
                full_prompt = f"上下文：{context}\n\n{prompt}"

            logger.info(f"🔍 开始分析图片: {Path(image_path).name}")

            # 调用多模态 API
            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": full_prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=2000,
                temperature=0.3  # 降低温度以获得更稳定的输出
            )

            # 解析响应
            content = response.choices[0].message.content
            logger.info(f"✅ 图片分析完成: {Path(image_path).name}")

            # 清理响应
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1]
            content = content.strip()

            # 解析 JSON
            try:
                result = json.loads(content)
                result["raw_response"] = content
                result["model"] = self.model

                # 生成问答上下文
                result["qa_context"] = self._generate_qa_context(result)
                result["success"] = True

                return result
            except json.JSONDecodeError as e:
                logger.error(f"JSON 解析失败: {e}")
                # 如果 JSON 解析失败，返回原始文本
                return {
                    "success": False,
                    "error": f"JSON 解析失败: {str(e)}",
                    "raw_response": content,
                    "description": content,
                    "image_type": "unknown",
                    "qa_context": f"图片分析失败，原始内容：{content[:500]}"
                }

        except Exception as e:
            logger.error(f"❌ 图片分析失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "image_type": "unknown",
                "qa_context": "图片分析失败，无法提供语义信息"
            }

    def _generate_qa_context(self, analysis_result: Dict[str, Any]) -> str:
        """生成问答上下文"""
        parts = []

        image_type = analysis_result.get("image_type", "未知类型")
        chart_type = analysis_result.get("chart_type", "")
        core_conclusion = analysis_result.get("core_conclusion", "")
        role_in_paper = analysis_result.get("role_in_paper", "")
        key_data_points = analysis_result.get("key_data_points", [])

        parts.append(f"这是一张{image_type}类型的图片")
        if chart_type and chart_type != "其他":
            parts.append(f"（{chart_type}）")

        if core_conclusion:
            parts.append(f"核心结论：{core_conclusion}")

        if role_in_paper:
            parts.append(f"在论文中的作用：{role_in_paper}")

        if key_data_points:
            parts.append("关键数据点：")
            for i, point in enumerate(key_data_points, 1):
                parts.append(f"  {i}. {point}")

        return "。".join(parts)

    async def analyze_table_image(
        self,
        image_path: str,
        context: str = ""
    ) -> Dict[str, Any]:
        """
        使用多模态 LLM 分析表格图片，提取结构化数据

        Args:
            image_path: 图片文件路径
            context: 上下文信息（如章节标题）

        Returns:
            {
                "success": true,
                "is_table": true/false,
                "table_title": "表1：性能比较",
                "markdown_content": "| 方法 | ACC | F1 |\n|---|---|---|\n| A | 0.9 | 0.8 |",
                "csv_content": "方法,ACC,F1\nA,0.9,0.8",
                "key_data_points": ["关键数据点1", "关键数据点2"],
                "core_conclusion": "核心结论",
                "qa_context": "用于问答的上下文"
            }
        """
        try:
            client = self._get_client()
            base64_image = self._encode_image(image_path)

            prompt = """你是一个专业的学术文档解析专家。请分析这张图片。

任务：
1. 判断这张图片是否是一个数据表格或性能对比表。如果不是（如架构图、流程图、照片），请直接返回 JSON: {"is_table": false, "reason": "不是表格"}
2. 如果是表格，请将其精确转换为 Markdown 格式的表格。
3. 如果表格上方有标题（例如"表1：XXX"），请在 Markdown 表格上方以加粗文本输出，格式为：**表X：标题**。
4. 保持原始数据的准确性，不要捏造数字。如果单元格为空，请用 "-" 填充。

输出要求：
必须且只能返回合法的 JSON 格式，结构如下：
{
    "is_table": true,
    "table_title": "表1：性能比较",
    "markdown_content": "| 方法 | ACC | F1 |\\n|---|---|---|\\n| A | 0.9 | 0.8 |",
    "key_data_points": ["关键数据点1", "关键数据点2"],
    "core_conclusion": "从表格中得出的核心结论"
}

注意：
- 如果不是表格，is_table 设为 false，其他字段留空
- 必须返回纯 JSON，不要包含任何其他文字"""

            full_prompt = prompt
            if context:
                full_prompt = f"上下文：{context}\n\n{prompt}"

            logger.info(f"📊 开始分析表格图片: {Path(image_path).name}")

            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": full_prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=3000,
                temperature=0.2
            )

            content = response.choices[0].message.content
            logger.info(f"✅ 表格图片分析完成: {Path(image_path).name}")

            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1]
            content = content.strip()

            content = content.replace('\r\n', '\n').replace('\r', '\n')
            
            import re
            content = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', content)
            
            try:
                result = json.loads(content)
                result["raw_response"] = content
                result["model"] = self.model
                result["success"] = True

                if result.get("is_table"):
                    markdown = result.get("markdown_content", "")
                    result["csv_content"] = self._markdown_to_csv(markdown)
                    result["qa_context"] = self._generate_table_qa_context(result)

                return result
            except json.JSONDecodeError as e:
                logger.error(f"JSON 解析失败: {e}")
                return {
                    "success": False,
                    "is_table": False,
                    "error": f"JSON 解析失败: {str(e)}",
                    "raw_response": content
                }

        except Exception as e:
            logger.error(f"❌ 表格图片分析失败: {e}")
            return {
                "success": False,
                "is_table": False,
                "error": str(e)
            }

    def _markdown_to_csv(self, markdown: str) -> str:
        """将 Markdown 表格转换为 CSV（正确处理逗号和空单元格）"""
        if not markdown:
            return ""

        import csv
        import io
        
        lines = markdown.strip().split('\n')
        csv_rows = []

        for line in lines:
            if line.startswith('**表'):
                continue
            if line.startswith('|'):
                cells = [c.strip() for c in line.split('|')]
                cells = [c for c in cells if c]  # 移除首尾空元素
                if cells and not all(set(c) <= set('-') for c in cells):
                    csv_rows.append(cells)

        if not csv_rows:
            return ""

        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
        for row in csv_rows:
            writer.writerow(row)

        return output.getvalue()

    def _generate_table_qa_context(self, table_result: Dict[str, Any]) -> str:
        """生成表格问答上下文"""
        parts = []

        table_title = table_result.get("table_title", "")
        markdown = table_result.get("markdown_content", "")
        core_conclusion = table_result.get("core_conclusion", "")
        key_data_points = table_result.get("key_data_points", [])

        if table_title:
            parts.append(table_title)

        parts.append("表格内容：")
        parts.append(markdown)

        if core_conclusion:
            parts.append(f"核心结论：{core_conclusion}")

        if key_data_points:
            parts.append("关键数据点：")
            for i, point in enumerate(key_data_points, 1):
                parts.append(f"  {i}. {point}")

        return "\n".join(parts)


# 全局分析器实例
_image_analyzer: Optional[ImageAnalyzer] = None


def get_image_analyzer() -> ImageAnalyzer:
    """获取图片分析器实例"""
    global _image_analyzer
    if _image_analyzer is None:
        _image_analyzer = ImageAnalyzer()
    return _image_analyzer
