"""结构化摘要 Agent 工作流模块"""
from langgraph.graph import StateGraph, END
from app.agent.state import SummarizerState
from app.llm.client import get_llm_client
import json
import logging
from loguru import logger

logger = logging.getLogger(__name__)


async def extract_overview(state: SummarizerState) -> SummarizerState:
    """提取论文概述（一句话总结、研究领域、核心问题）"""
    logger.info(f"[结构化摘要 Agent] 提取论文概述")
    
    llm = get_llm_client()
    sections = state.get('sections', [])
    text = "\n\n".join([f"## {s.get('title', '')}\n{s.get('content', '')}" for s in sections[:5]])
    
    prompt = f"""
    请分析以下论文内容，提取概述信息，返回 JSON 格式：
    
    {{
        "one_sentence_summary": "用一句话概括这篇论文的核心内容（50字以内）",
        "research_field": "研究领域",
        "core_problem": "论文要解决的核心问题是什么",
        "paper_type": "论文类型（综述/方法/实验/理论/应用）"
    }}
    
    论文内容：
    {text[:8000]}
    """
    
    try:
        response = await llm.agenerate([prompt])
        text_result = response.generations[0][0].text.strip()
        if "```json" in text_result:
            text_result = text_result.split("```json")[1].split("```")[0]
        result = json.loads(text_result.strip())
        state['summary'] = json.dumps(result, ensure_ascii=False)
        logger.info(f"✅ 概述提取成功")
    except Exception as e:
        logger.error(f"❌ 概述提取失败：{e}")
        state['summary'] = json.dumps({
            "one_sentence_summary": "提取失败",
            "research_field": "未知",
            "core_problem": "未知",
            "paper_type": "未知"
        }, ensure_ascii=False)
    
    return state


async def extract_methodology(state: SummarizerState) -> SummarizerState:
    """提取方法论"""
    logger.info(f"[结构化摘要 Agent] 提取方法论")
    
    llm = get_llm_client()
    sections = state.get('sections', [])
    text = "\n\n".join([f"## {s.get('title', '')}\n{s.get('content', '')}" for s in sections])
    
    prompt = f"""
    请分析以下论文内容，提取方法论信息，返回 JSON 格式：
    
    {{
        "method_name": "方法/模型名称",
        "method_description": "方法的核心思想（100字以内）",
        "key_techniques": ["关键技术1", "关键技术2", "关键技术3"],
        "architecture": "整体架构描述（如果有）",
        "input_output": "输入和输出是什么"
    }}
    
    论文内容：
    {text[:10000]}
    """
    
    try:
        response = await llm.agenerate([prompt])
        text_result = response.generations[0][0].text.strip()
        if "```json" in text_result:
            text_result = text_result.split("```json")[1].split("```")[0]
        result = json.loads(text_result.strip())
        state['key_findings'] = json.dumps(result, ensure_ascii=False)
        logger.info(f"✅ 方法论提取成功")
    except Exception as e:
        logger.error(f"❌ 方法论提取失败：{e}")
        state['key_findings'] = json.dumps({
            "method_name": "提取失败",
            "method_description": "",
            "key_techniques": [],
            "architecture": "",
            "input_output": ""
        }, ensure_ascii=False)
    
    return state


async def extract_experiments(state: SummarizerState) -> SummarizerState:
    """提取实验信息"""
    logger.info(f"[结构化摘要 Agent] 提取实验信息")
    
    llm = get_llm_client()
    sections = state.get('sections', [])
    text = "\n\n".join([f"## {s.get('title', '')}\n{s.get('content', '')}" for s in sections])
    
    prompt = f"""
    请分析以下论文内容，提取实验信息，返回 JSON 格式：
    
    {{
        "datasets": ["使用的数据集1", "数据集2"],
        "baselines": ["对比的基线方法1", "基线方法2"],
        "metrics": ["评估指标1", "指标2"],
        "main_results": "主要实验结果概述（100字以内）",
        "best_performance": "最佳性能/结果"
    }}
    
    论文内容：
    {text[:10000]}
    """
    
    try:
        response = await llm.agenerate([prompt])
        text_result = response.generations[0][0].text.strip()
        if "```json" in text_result:
            text_result = text_result.split("```json")[1].split("```")[0]
        result = json.loads(text_result.strip())
        # Store in contributions temporarily, will reorganize later
        state['contributions'] = json.dumps(result, ensure_ascii=False)
        logger.info(f"✅ 实验信息提取成功")
    except Exception as e:
        logger.error(f"❌ 实验信息提取失败：{e}")
        state['contributions'] = json.dumps({
            "datasets": [],
            "baselines": [],
            "metrics": [],
            "main_results": "",
            "best_performance": ""
        }, ensure_ascii=False)
    
    return state


async def extract_contributions(state: SummarizerState) -> SummarizerState:
    """提取贡献和创新点"""
    logger.info(f"[结构化摘要 Agent] 提取贡献和创新点")
    
    llm = get_llm_client()
    sections = state.get('sections', [])
    text = "\n\n".join([f"## {s.get('title', '')}\n{s.get('content', '')}" for s in sections])
    
    prompt = f"""
    请分析以下论文内容，提取贡献、创新点和局限性，返回 JSON 格式：
    
    {{
        "contributions": ["贡献1", "贡献2", "贡献3"],
        "innovations": ["创新点1", "创新点2"],
        "limitations": ["局限性1", "局限性2"],
        "future_work": "未来工作方向"
    }}
    
    论文内容：
    {text[:10000]}
    """
    
    try:
        response = await llm.agenerate([prompt])
        text_result = response.generations[0][0].text.strip()
        if "```json" in text_result:
            text_result = text_result.split("```json")[1].split("```")[0]
        result = json.loads(text_result.strip())
        state['limitations'] = json.dumps(result, ensure_ascii=False)
        logger.info(f"✅ 贡献和创新点提取成功")
    except Exception as e:
        logger.error(f"❌ 贡献和创新点提取失败：{e}")
        state['limitations'] = json.dumps({
            "contributions": [],
            "innovations": [],
            "limitations": [],
            "future_work": ""
        }, ensure_ascii=False)
    
    return state


def create_summarizer_agent_graph():
    """创建结构化摘要 Agent 图"""
    graph = StateGraph(SummarizerState)
    
    graph.add_node("extract_overview", extract_overview)
    graph.add_node("extract_methodology", extract_methodology)
    graph.add_node("extract_experiments", extract_experiments)
    graph.add_node("extract_contributions", extract_contributions)
    
    graph.set_entry_point("extract_overview")
    graph.add_edge("extract_overview", "extract_methodology")
    graph.add_edge("extract_methodology", "extract_experiments")
    graph.add_edge("extract_experiments", "extract_contributions")
    graph.add_edge("extract_contributions", END)
    
    return graph.compile()


_summarizer_agent = None


def get_summarizer_agent():
    global _summarizer_agent
    if _summarizer_agent is None:
        _summarizer_agent = create_summarizer_agent_graph()
    return _summarizer_agent


async def run_summarizer_agent(paper_id: str, sections: list) -> dict:
    """运行结构化摘要 Agent"""
    logger.info(f"[结构化摘要 Agent] 开始处理论文：{paper_id}")
    
    initial_state = SummarizerState(
        paper_id=paper_id,
        summary_type="full",
        sections=sections,
        summary=None,
        key_findings=None,
        contributions=None,
        limitations=None,
        error=None
    )
    
    agent = get_summarizer_agent()
    result = await agent.ainvoke(initial_state)
    
    logger.info(f"✅ [结构化摘要 Agent] 处理完成")
    
    return {
        "overview": json.loads(result.get("summary", "{}")),
        "methodology": json.loads(result.get("key_findings", "{}")),
        "experiments": json.loads(result.get("contributions", "{}")),
        "contributions": json.loads(result.get("limitations", "{}"))
    }
