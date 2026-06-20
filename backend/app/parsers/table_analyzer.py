"""表格语义分析器 - 使用LLM分析表格数据含义"""
import json
import logging
import sys
from typing import List, Dict, Any, Optional

# 添加项目库路径
sys.path.insert(0, '/home/ddd/project/myAgent/backend/lib')

try:
    from app.llm.client import get_llm_client
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    logging.warning("LLM客户端不可用，将使用规则引擎模式")

logger = logging.getLogger(__name__)


class TableSemanticAnalyzer:
    """
    表格语义分析器 - 将原始表格数据转换为结构化的语义信息
    
    分析能力：
    1. 识别表格目的和主题
    2. 找出最优/最差结果
    3. 分析数据趋势和差异
    4. 提取关键洞察
    5. 生成可用于问答的结构化信息
    
    优先使用 LLM 进行深度分析，LLM不可用时回退到规则引擎
    """
    
    def __init__(self, use_llm: bool = True):
        self.use_llm = use_llm and LLM_AVAILABLE
        self.llm = get_llm_client() if self.use_llm else None
        logger.info(f"表格分析器初始化: {'LLM模式' if self.use_llm else '规则引擎模式'}")
    
    async def analyze_table(self, table_data: List[List[str]], caption: str = "", context: str = "", table_markdown: str = "", table_csv: str = "") -> Dict[str, Any]:
        """
        分析表格语义
        
        Args:
            table_data: 表格数据（二维列表）
            caption: 表格标题（可选）
            context: 上下文信息（可选，如章节标题）
            table_markdown: Markdown 格式的表格（可选）
            table_csv: CSV 格式的表格（可选）
        
        Returns:
            包含语义分析结果的字典
        """
        if not table_data or len(table_data) < 2:
            return {
                "success": False,
                "error": "表格数据不足"
            }
        
        # 检测表格是否乱码或结构错乱
        is_corrupted = self._detect_table_corruption(table_data)
        
        if self.use_llm:
            # 优先使用文本模型分析 Markdown/CSV 格式
            if table_markdown or table_csv:
                return await self._analyze_with_text_llm(table_data, caption, context, table_markdown, table_csv)
            elif is_corrupted:
                # 如果乱码，使用多模态模型分析（需要截图）
                logger.warning(f"检测到表格乱码，建议使用多模态模型分析")
                return await self._analyze_with_rules(table_data, caption, context)
            else:
                return await self._analyze_with_llm(table_data, caption, context)
        else:
            return await self._analyze_with_rules(table_data, caption, context)
    
    def _detect_table_corruption(self, table_data: List[List[str]]) -> bool:
        """检测表格是否乱码或结构错乱"""
        if not table_data:
            return True
        
        # 检查空单元格比例
        total_cells = sum(len(row) for row in table_data)
        empty_cells = sum(1 for row in table_data for cell in row if not cell or not str(cell).strip())
        
        if total_cells > 0 and empty_cells / total_cells > 0.5:
            logger.warning(f"表格空单元格比例过高: {empty_cells}/{total_cells}")
            return True
        
        # 检查行长度一致性
        row_lengths = [len(row) for row in table_data]
        if len(set(row_lengths)) > 2:  # 允许最多2种不同长度
            logger.warning(f"表格行长度不一致: {row_lengths}")
            return True
        
        # 检查是否包含大量乱码字符
        import re
        for row in table_data:
            for cell in row:
                if cell:
                    # 检查是否包含大量非可打印字符
                    if len(re.sub(r'[\x20-\x7E\u4e00-\u9fff]', '', str(cell))) > len(str(cell)) * 0.3:
                        logger.warning(f"检测到乱码字符: {cell[:50]}")
                        return True
        
        return False
    
    async def _analyze_with_text_llm(self, table_data: List[List[str]], caption: str = "", context: str = "", table_markdown: str = "", table_csv: str = "") -> Dict[str, Any]:
        """使用文本 LLM 分析表格语义（基于 Markdown/CSV 格式）"""
        # 优先使用 Markdown 格式，其次 CSV
        table_text = table_markdown if table_markdown else table_csv
        if not table_text:
            # 回退到原始格式
            table_text = self._format_table(table_data)
        
        # 构建分析提示
        prompt = f"""
请分析以下表格数据的语义含义：

表格标题：{caption or '无标题'}
上下文：{context or '无'}

表格内容：
{table_text}

请按以下JSON格式输出分析结果：
{{
    "success": true,
    "purpose": "表格的目的和主题，用简洁的中文描述",
    "structure": {{
        "rows": 数据行数（不含表头）,
        "columns": 列数,
        "headers": ["列1", "列2", ...],
        "has_header": true/false,
        "data_type": "对比表/排名表/统计表/其他"
    }},
    "key_insights": [
        "洞察1：简明扼要的数据分析结论",
        "洞察2：..."
    ],
    "best_results": [
        {{"指标": "某列名", "最佳值": "值", "对应行": "行名"}}
    ],
    "worst_results": [
        {{"指标": "某列名", "最差值": "值", "对应行": "行名"}}
    ],
    "comparisons": [
        {{"对比项": "A vs B", "差异": "描述差异"}}
    ],
    "trends": [
        "趋势描述..."
    ],
    "data_summary": "表格数据的简要总结（不超过50字）"
}}

注意事项：
1. 如果没有数值数据，best_results 和 worst_results 可以为空数组
2. 分析时要考虑表格标题和上下文
3. JSON格式必须正确，不要包含任何额外文字
4. 所有内容使用中文
"""
        
        try:
            response = await self.llm.agenerate([prompt], json_mode=True, enable_thinking=False)
            text = response.generations[0][0].text.strip()
            
            # 清理响应
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1]
            
            result = json.loads(text.strip())
            result["raw_table"] = table_data
            result["caption"] = caption
            result["analysis_method"] = "text_llm"
            
            logger.info(f"✅ 文本LLM表格语义分析成功")
            return result
            
        except Exception as e:
            logger.error(f"❌ 文本LLM表格语义分析失败: {e}")
            # 回退到规则引擎
            return await self._analyze_with_rules(table_data, caption, context)
    
    async def _analyze_with_llm(self, table_data: List[List[str]], caption: str = "", context: str = "") -> Dict[str, Any]:
        """使用 LLM 分析表格语义"""
        # 构建表格文本表示
        table_text = self._format_table(table_data)
        
        # 构建分析提示
        prompt = f"""
请分析以下表格数据的语义含义：

表格标题：{caption or '无标题'}
上下文：{context or '无'}

表格内容：
{table_text}

请按以下JSON格式输出分析结果：
{{
    "success": true,
    "purpose": "表格的目的和主题，用简洁的中文描述",
    "structure": {{
        "rows": 数据行数（不含表头）,
        "columns": 列数,
        "headers": ["列1", "列2", ...],
        "has_header": true/false,
        "data_type": "对比表/排名表/统计表/其他"
    }},
    "key_insights": [
        "洞察1：简明扼要的数据分析结论",
        "洞察2：..."
    ],
    "best_results": [
        {{"指标": "某列名", "最佳值": "值", "对应行": "行名"}}
    ],
    "worst_results": [
        {{"指标": "某列名", "最差值": "值", "对应行": "行名"}}
    ],
    "comparisons": [
        {{"对比项": "A vs B", "差异": "描述差异"}}
    ],
    "trends": [
        "趋势描述..."
    ],
    "data_summary": "表格数据的简要总结（不超过50字）"
}}

注意事项：
1. 如果没有数值数据，best_results 和 worst_results 可以为空数组
2. 分析时要考虑表格标题和上下文
3. JSON格式必须正确，不要包含任何额外文字
4. 所有内容使用中文
"""
        
        try:
            response = await self.llm.agenerate([prompt], json_mode=True, enable_thinking=False)
            text = response.generations[0][0].text.strip()
            
            # 清理响应
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1]
            
            result = json.loads(text.strip())
            result["raw_table"] = table_data
            result["caption"] = caption
            result["analysis_method"] = "llm"
            
            logger.info(f"✅ LLM表格语义分析成功")
            return result
            
        except Exception as e:
            logger.error(f"❌ LLM表格语义分析失败: {e}")
            # 回退到规则引擎
            return await self._analyze_with_rules(table_data, caption, context)
    
    async def _analyze_with_rules(self, table_data: List[List[str]], caption: str = "", context: str = "") -> Dict[str, Any]:
        """使用规则引擎分析表格语义（LLM回退方案）"""
        try:
            # 提取表头
            headers = table_data[0]
            has_header = self._has_header(headers)
            
            # 提取数据行
            data_rows = table_data[1:] if has_header else table_data
            
            # 分析结构
            structure = {
                "rows": len(data_rows),
                "columns": len(headers),
                "headers": headers,
                "has_header": has_header,
                "data_type": self._infer_data_type(caption, headers)
            }
            
            # 分析最佳/最差结果
            best_results, worst_results = self._find_extremes(headers, data_rows)
            
            # 分析对比
            comparisons = self._generate_comparisons(headers, data_rows)
            
            # 分析趋势
            trends = self._detect_trends(headers, data_rows)
            
            # 生成关键洞察
            key_insights = self._generate_insights(
                caption, structure, best_results, worst_results, comparisons, trends
            )
            
            # 生成数据摘要
            data_summary = self._generate_summary(caption, structure, key_insights)
            
            result = {
                "success": True,
                "purpose": self._infer_purpose(caption, headers),
                "structure": structure,
                "key_insights": key_insights,
                "best_results": best_results,
                "worst_results": worst_results,
                "comparisons": comparisons,
                "trends": trends,
                "data_summary": data_summary,
                "raw_table": table_data,
                "caption": caption,
                "analysis_method": "rules"
            }
            
            logger.info(f"✅ 规则引擎表格语义分析成功")
            return result
            
        except Exception as e:
            logger.error(f"❌ 规则引擎表格语义分析失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "raw_table": table_data,
                "caption": caption
            }
    
    async def analyze_multiple_tables(self, tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量分析多个表格"""
        results = []
        for table in tables:
            data = table.get("content", [])
            caption = table.get("caption", "")
            analysis = await self.analyze_table(data, caption)
            analysis["table_number"] = table.get("table_number", len(results) + 1)
            analysis["page"] = table.get("page")
            results.append(analysis)
        return results
    
    def _format_table(self, table_data: List[List[str]]) -> str:
        """将二维列表转换为文本表格格式"""
        if not table_data:
            return ""
        
        lines = []
        for row in table_data:
            line = "| " + " | ".join(str(cell).strip() for cell in row if cell) + " |"
            lines.append(line)
        
        return "\n".join(lines)
    
    def _has_header(self, first_row: List[str]) -> bool:
        """判断第一行是否为表头"""
        if not first_row:
            return False
        
        header_indicators = ["方法", "模型", "指标", "参数", "类型", "类别", "名称",
                            "method", "model", "metric", "parameter", "type", "name",
                            "指标名称", "实验", "对比", "结果"]
        
        first_cell = str(first_row[0]).lower()
        return any(indicator.lower() in first_cell for indicator in header_indicators)
    
    def _infer_data_type(self, caption: str, headers: List[str]) -> str:
        """推断表格类型"""
        caption_lower = caption.lower() if caption else ""
        
        if any(word in caption_lower for word in ["对比", "比较", "comparison"]):
            return "对比表"
        elif any(word in caption_lower for word in ["排名", "排行", "rank"]):
            return "排名表"
        elif any(word in caption_lower for word in ["统计", "汇总", "summary"]):
            return "统计表"
        elif any(header.lower() in ["准确率", "精度", "f1", "acc", "accuracy"] for header in headers):
            return "对比表"
        else:
            return "其他"
    
    def _infer_purpose(self, caption: str, headers: List[str]) -> str:
        """推断表格目的"""
        if caption:
            return f"展示{caption}的相关数据"
        return f"展示{', '.join(headers[:3])}等指标的数据"
    
    def _find_extremes(self, headers: List[str], data_rows: List[List[str]]) -> tuple:
        """找出最佳和最差结果"""
        best_results = []
        worst_results = []
        
        for col_idx, header in enumerate(headers):
            values = []
            row_names = []
            
            for row in data_rows:
                if col_idx < len(row):
                    value = str(row[col_idx]).strip()
                    row_name = str(row[0]) if len(row) > 0 else ""
                    
                    num_value = self._parse_number(value)
                    if num_value is not None:
                        values.append((num_value, row_name, value))
            
            if len(values) >= 2:
                values.sort(key=lambda x: x[0])
                is_higher_better = self._is_higher_better(header)
                
                if is_higher_better:
                    best_val = values[-1]
                    worst_val = values[0]
                else:
                    best_val = values[0]
                    worst_val = values[-1]
                
                best_results.append({
                    "指标": header,
                    "最佳值": best_val[2],
                    "对应行": best_val[1]
                })
                
                worst_results.append({
                    "指标": header,
                    "最差值": worst_val[2],
                    "对应行": worst_val[1]
                })
        
        return best_results, worst_results
    
    def _parse_number(self, value: str) -> Optional[float]:
        """从字符串中解析数值"""
        try:
            value = value.replace("%", "").replace(",", "")
            return float(value)
        except ValueError:
            return None
    
    def _is_higher_better(self, header: str) -> bool:
        """判断指标是否越大越好"""
        header_lower = header.lower()
        
        higher_better = ["准确率", "精度", "召回率", "f1", "分数", "得分",
                        "accuracy", "precision", "recall", "f1-score", "score",
                        "效率", "性能", "speed", "efficiency", "throughput"]
        
        lower_better = ["误差", "错误率", "损失", "时间",
                       "error", "loss", "time", "latency", "cost"]
        
        if any(word in header_lower for word in higher_better):
            return True
        elif any(word in header_lower for word in lower_better):
            return False
        return True
    
    def _generate_comparisons(self, headers: List[str], data_rows: List[List[str]]) -> List[Dict]:
        """生成对比信息"""
        comparisons = []
        
        if len(data_rows) < 2:
            return comparisons
        
        for col_idx, header in enumerate(headers[1:], start=1):
            values = []
            row_names = []
            
            for row in data_rows:
                if col_idx < len(row):
                    num_value = self._parse_number(str(row[col_idx]))
                    if num_value is not None:
                        values.append(num_value)
                        row_names.append(str(row[0]) if len(row) > 0 else "")
            
            if len(values) >= 2:
                max_val = max(values)
                min_val = min(values)
                diff = max_val - min_val
                
                if diff > 0:
                    max_idx = values.index(max_val)
                    min_idx = values.index(min_val)
                    
                    comparisons.append({
                        "对比项": f"{row_names[max_idx]} vs {row_names[min_idx]}",
                        "差异": f"{header}相差 {diff:.2f}"
                    })
        
        return comparisons[:3]
    
    def _detect_trends(self, headers: List[str], data_rows: List[List[str]]) -> List[str]:
        """检测数据趋势"""
        trends = []
        
        for col_idx, header in enumerate(headers[1:], start=1):
            values = []
            
            for row in data_rows:
                if col_idx < len(row):
                    num_value = self._parse_number(str(row[col_idx]))
                    if num_value is not None:
                        values.append(num_value)
            
            if len(values) >= 3:
                is_increasing = all(values[i] <= values[i+1] for i in range(len(values)-1))
                is_decreasing = all(values[i] >= values[i+1] for i in range(len(values)-1))
                
                if is_increasing:
                    trends.append(f"{header}呈上升趋势")
                elif is_decreasing:
                    trends.append(f"{header}呈下降趋势")
        
        return trends
    
    def _generate_insights(self, caption, structure, best_results, worst_results, comparisons, trends) -> List[str]:
        """生成关键洞察"""
        insights = []
        
        if caption:
            insights.append(f"表格展示了{caption}的对比数据")
        
        if structure.get("data_type") == "对比表":
            insights.append(f"这是一个{structure['data_type']}，共包含{structure['rows']}行{structure['columns']}列数据")
        
        if best_results:
            best_str = ", ".join([f"{r['对应行']}在{r['指标']}上表现最佳" for r in best_results[:2]])
            insights.append(best_str)
        
        if comparisons:
            insights.append(comparisons[0]["差异"])
        
        if trends:
            insights.extend(trends)
        
        return insights
    
    def _generate_summary(self, caption, structure, insights) -> str:
        """生成数据摘要"""
        parts = []
        
        if caption:
            parts.append(caption)
        
        if structure.get("rows") and structure.get("columns"):
            parts.append(f"包含{structure['rows']}行{structure['columns']}列数据")
        
        if insights:
            parts.append("主要发现：" + "; ".join(insights[:3]))
        
        return "。".join(parts)
    
    def get_qa_context(self, analysis_result: Dict[str, Any]) -> str:
        """将分析结果转换为适合问答的上下文文本"""
        if not analysis_result.get("success"):
            return ""
        
        parts = []
        
        if analysis_result.get("caption"):
            parts.append(f"【表格】{analysis_result['caption']}")
        
        if analysis_result.get("purpose"):
            parts.append(f"目的：{analysis_result['purpose']}")
        
        insights = analysis_result.get("key_insights", [])
        if insights:
            parts.append("关键洞察：")
            for i, insight in enumerate(insights[:5], 1):
                parts.append(f"  {i}. {insight}")
        
        best_results = analysis_result.get("best_results", [])
        if best_results:
            parts.append("最佳表现：")
            for result in best_results[:3]:
                parts.append(f"  - {result.get('指标')}: {result.get('对应行')} ({result.get('最佳值')})")
        
        if analysis_result.get("data_summary"):
            parts.append(f"摘要：{analysis_result['data_summary']}")
        
        return "\n".join(parts)


# 测试
if __name__ == "__main__":
    import asyncio
    
    async def test():
        analyzer = TableSemanticAnalyzer(use_llm=True)
        print(f"使用模式: {'LLM模式' if analyzer.use_llm else '规则引擎模式'}")
        
        test_table = [
            ["方法", "准确率", "召回率", "F1分数"],
            ["Transformer", "92.5%", "89.3%", "90.8%"],
            ["BERT", "88.7%", "91.2%", "89.9%"],
            ["CNN", "85.3%", "87.1%", "86.2%"]
        ]
        
        result = await analyzer.analyze_table(test_table, "表1: 不同模型性能对比", "实验结果章节")
        print("分析结果：")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
        qa_context = analyzer.get_qa_context(result)
        print("\n问答上下文：")
        print(qa_context)
    
    asyncio.run(test())
