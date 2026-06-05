"""问答 Agent 工作流模块"""
from langgraph.graph import StateGraph, END
from app.agent.state import QAAgentState
from app.llm.client import get_llm_client
import json
import logging
from loguru import logger

logger = logging.getLogger(__name__)


async def recognize_intent(state: QAAgentState) -> QAAgentState:
    """识别问题意图"""
    logger.info(f"[问答 Agent] 识别问题意图")
    
    llm = get_llm_client()
    question = state['question']
    
    prompt = f"""
    请分析以下关于论文的问题意图：
    问题：{question}
    
    请判断问题属于以下哪个类别，并返回 JSON 格式：
    {{"intent": "类别", "confidence": 0.9, "reason": "判断理由"}}
    
    可选类别：
    - general: 通用问题
    - method: 方法论相关问题
    - experiment: 实验相关问题
    - contribution: 贡献和创新点
    - comparison: 与其他工作对比
    """
    
    try:
        logger.info(f"📤 调用 LLM agenerate...")
        response = await llm.agenerate([prompt])
        logger.info(f"LLM 原始响应类型: {type(response)}")
        logger.info(f"LLM 原始响应: {response}")
        
        # agenerate returns LLMResult with generations: List[List[ChatGeneration]]
        text = response.generations[0][0].text.strip()
        logger.info(f"LLM 解析文本: {text[:200]}...")
        
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        result = json.loads(text.strip())
        state['intent'] = result.get('intent', 'general')
        state['confidence'] = result.get('confidence', 0.5)
        logger.info(f"✅ 意图识别成功：{state['intent']}")
    except Exception as e:
        import traceback
        logger.error(f"❌ 意图识别失败：{e}")
        logger.error(f"详细堆栈：{traceback.format_exc()}")
        state['intent'] = 'general'
        state['confidence'] = 0.5
    
    return state


async def generate_answer(state: QAAgentState) -> QAAgentState:
    """生成回答"""
    logger.info(f"[问答 Agent] 生成回答")
    
    llm = get_llm_client()
    question = state['question']
    chunks = state.get('relevant_chunks', [])
    
    context = "\n".join([f"[{i+1}] {c.get('content', '')}" for i, c in enumerate(chunks)]) if chunks else "未找到相关内容"
    
    prompt = f"""
    请根据以下论文内容回答问题：
    
    问题：{question}
    
    相关内容：
    {context}
    
    请给出准确、完整的回答，并注明引用来源。
    
    回答格式：
    {{"answer": "回答内容", "sources": ["引用来源 1", "引用来源 2"]}}
    """
    
    try:
        response = await llm.agenerate([prompt])
        text = response.generations[0][0].text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        result = json.loads(text.strip())
        state['answer'] = result.get('answer', '暂无回答')
        state['sources'] = [f"来源[{i+1}]" for i in range(len(chunks))] if chunks else []
        logger.info(f"✅ 回答生成成功，长度：{len(state['answer'])}")
    except Exception as e:
        logger.error(f"❌ 回答生成失败：{e}")
        state['answer'] = "抱歉，无法生成回答，请尝试重新提问。"
        state['sources'] = []
    
    return state


def create_qa_agent_graph():
    """创建问答 Agent 图"""
    graph = StateGraph(QAAgentState)
    
    graph.add_node("recognize_intent", recognize_intent)
    graph.add_node("generate_answer", generate_answer)
    
    graph.set_entry_point("recognize_intent")
    graph.add_edge("recognize_intent", "generate_answer")
    graph.add_edge("generate_answer", END)
    
    return graph.compile()


_qa_agent = None


def get_qa_agent():
    global _qa_agent
    if _qa_agent is None:
        _qa_agent = create_qa_agent_graph()
    return _qa_agent


async def run_qa_agent(paper_id: str, question: str, relevant_chunks: list) -> dict:
    """运行问答 Agent"""
    logger.info(f"[问答 Agent] 处理问题：{question[:50]}...")
    
    initial_state = QAAgentState(
        paper_id=paper_id,
        question=question,
        intent=None,
        relevant_chunks=relevant_chunks,
        answer=None,
        sources=[],
        confidence=0.0,
        error=None
    )
    
    agent = get_qa_agent()
    result = await agent.ainvoke(initial_state)
    
    logger.info(f"✅ [问答 Agent] 处理完成")
    
    return {
        "answer": result.get("answer", ""),
        "intent": result.get("intent", ""),
        "sources": result.get("sources", []),
        "confidence": result.get("confidence", 0.0)
    }
