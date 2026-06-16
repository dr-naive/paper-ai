"""增强版问答 Agent 工作流模块 - 支持引用溯源和智能追问"""
from langgraph.graph import StateGraph, END
from app.agent.state import QAAgentState
from app.llm.client import get_llm_client
import json
import logging
from loguru import logger

logger = logging.getLogger(__name__)


async def recognize_intent(state: QAAgentState) -> QAAgentState:
    """识别问题意图"""
    logger.info(f"[增强问答 Agent] 识别问题意图")
    
    llm = get_llm_client()
    question = state['question']
    
    prompt = f"""
    请分析以下关于论文的问题意图：
    问题：{question}
    
    请判断问题属于以下哪个类别，并返回 JSON 格式：
    {{"intent": "类别", "confidence": 0.9, "reason": "判断理由"}}
    
    可选类别：
    - metadata: 论文元数据（作者、标题、发表年份等）
    - general: 通用问题
    - method: 方法论相关问题
    - experiment: 实验相关问题
    - contribution: 贡献和创新点
    - comparison: 与其他工作对比
    - concept: 概念解释
    - detail: 细节查询
    """
    
    try:
        response = await llm.agenerate([prompt])
        text = response.generations[0][0].text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        result = json.loads(text.strip())
        state['intent'] = result.get('intent', 'general')
        state['confidence'] = result.get('confidence', 0.5)
        logger.info(f"✅ 意图识别成功：{state['intent']}")
    except Exception as e:
        logger.error(f"❌ 意图识别失败：{e}")
        state['intent'] = 'general'
        state['confidence'] = 0.5
    
    return state


async def answer_metadata(state: QAAgentState) -> QAAgentState:
    """回答元数据类问题（作者、标题等）"""
    logger.info(f"[增强问答 Agent] 回答元数据问题")
    
    metadata = state.get('paper_metadata', {})
    question = state['question']
    
    # 构建元数据上下文
    meta_info = []
    if metadata.get('title'):
        meta_info.append(f"标题：{metadata['title']}")
    if metadata.get('authors'):
        meta_info.append(f"作者：{metadata['authors']}")
    if metadata.get('abstract'):
        meta_info.append(f"摘要：{metadata['abstract'][:500]}")
    if metadata.get('keywords'):
        meta_info.append(f"关键词：{', '.join(metadata['keywords'])}")
    if metadata.get('venue'):
        meta_info.append(f"发表 venue：{metadata['venue']}")
    if metadata.get('publication_year'):
        meta_info.append(f"发表年份：{metadata['publication_year']}")
    if metadata.get('doi'):
        meta_info.append(f"DOI：{metadata['doi']}")
    
    context = "\n".join(meta_info) if meta_info else "无元数据信息"
    
    prompt = f"""
    请根据以下论文元数据回答问题。如果元数据中没有相关信息，请明确说明"论文信息中未提供"。
    
    问题：{question}
    
    论文元数据：
    {context}
    
    请返回 JSON 格式：
    {{
        "answer": "回答内容",
        "citations": [
            {{"section": "论文元数据", "text": "相关原文", "position": "metadata"}}
        ]
    }}
    """
    
    try:
        llm = get_llm_client()
        response = await llm.agenerate([prompt])
        text = response.generations[0][0].text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        
        # 健壮地解析 JSON
        result = None
        try:
            result = json.loads(text.strip())
        except json.JSONDecodeError:
            import re
            answer_match = re.search(r'"answer"\s*:\s*"(.*?)"\s*,', text, re.DOTALL)
            if answer_match:
                result = {"answer": answer_match.group(1).replace('\\"', '"'), "citations": []}
            else:
                result = {"answer": text, "citations": []}
        
        state['answer'] = result.get('answer', '暂无回答')
        state['citations'] = result.get('citations', [])
        state['sources'] = [c.get('section', '') for c in state['citations']]
        logger.info(f"✅ 元数据回答生成成功")
    except Exception as e:
        logger.error(f"❌ 元数据回答失败：{e}")
        state['answer'] = "抱歉，无法获取论文信息。"
        state['citations'] = []
        state['sources'] = []
    
    return state


async def generate_answer(state: QAAgentState) -> QAAgentState:
    """生成带引用溯源的回答"""
    logger.info(f"[增强问答 Agent] 生成回答")
    
    llm = get_llm_client()
    question = state['question']
    chunks = state.get('relevant_chunks', [])
    history_context = state.get('history_context', '')
    
    if not chunks:
        state['answer'] = "未在论文中找到相关内容，请尝试其他问题。"
        state['citations'] = []
        state['sources'] = []
        return state
    
    # 构建带章节信息的上下文，保留更多原文
    context_parts = []
    for i, c in enumerate(chunks):
        section = c.get('section', '未知章节')
        content = c.get('content', '')
        # 保留更长的原文片段
        context_parts.append(f"[章节: {section}]\n{content}")
    
    context = "\n\n---\n\n".join(context_parts)
    
    # 提取所有可用的章节名，让 AI 只能从这些中选择
    available_sections = [c.get('section', '未知章节') for c in chunks]
    sections_list = "、".join(set(available_sections))
    
    # 构建历史对话提示
    history_prompt = ""
    if history_context:
        history_prompt = f"""
        
        【历史对话参考】
        以下是之前的对话记录，请结合上下文理解用户当前问题的意图：
        {history_context}
        
        注意：回答当前问题时可以参考历史信息，但要以论文内容为准。
        """
    
    prompt = f"""
    请根据以下论文内容回答问题。要求：
    1. 回答准确、完整、专业
    2. 在回答中用 [章节名] 标注引用来源
    3. 如果内容不足以回答问题，请明确说明"论文中未提及"
    4. 回答要有条理，使用分点或分段
    5. **重要**：citations 中的 section 字段必须严格使用以下章节名之一：{sections_list}
    {history_prompt}
    问题：{question}
    
    相关内容：
    {context}
    
    请返回 JSON 格式：
    {{
        "answer": "回答内容，在关键信息后标注 [章节名]",
        "citations": [
            {{"section": "必须从可用章节名中选择", "text": "原文关键句（至少30字，完整保留关键信息）", "position": "章节中的位置描述"}}
        ]
    }}
    """
    
    try:
        response = await llm.agenerate([prompt])
        text = response.generations[0][0].text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        
        # 健壮地解析 JSON
        result = None
        try:
            result = json.loads(text.strip())
        except json.JSONDecodeError as json_err:
            logger.warning(f"⚠️ JSON 解析失败，尝试修复: {json_err}")
            # 尝试提取 answer 字段
            import re
            answer_match = re.search(r'"answer"\s*:\s*"(.*?)"\s*,\s*"citations"', text, re.DOTALL)
            if answer_match:
                answer_text = answer_match.group(1)
                # 处理转义的引号
                answer_text = answer_text.replace('\\"', '"')
                result = {"answer": answer_text, "citations": []}
            else:
                # 如果无法提取，直接使用原始文本作为回答
                logger.warning("⚠️ 无法提取 JSON，直接使用原始文本")
                result = {"answer": text, "citations": []}
        
        state['answer'] = result.get('answer', '暂无回答')
        state['citations'] = result.get('citations', [])
        state['sources'] = [c.get('section', '') for c in state['citations']]
        logger.info(f"✅ 回答生成成功，长度：{len(state['answer'])}")
    except Exception as e:
        logger.error(f"❌ 回答生成失败：{e}")
        state['answer'] = "抱歉，无法生成回答，请尝试重新提问。"
        state['citations'] = []
        state['sources'] = []
    
    return state


async def generate_follow_up(state: QAAgentState) -> QAAgentState:
    """生成智能追问"""
    logger.info(f"[增强问答 Agent] 生成智能追问")
    
    llm = get_llm_client()
    question = state['question']
    answer = state.get('answer', '')
    intent = state.get('intent', 'general')
    
    prompt = f"""
    基于以下问答内容，生成 3 个相关的追问问题，帮助用户深入理解论文。
    
    用户问题：{question}
    问题类型：{intent}
    回答摘要：{answer[:300]}
    
    要求：
    1. 问题要有深度，能引导用户探索论文的关键内容
    2. 问题类型要多样化（方法细节、实验结果、局限性等）
    3. 每个问题不超过 30 字
    
    返回 JSON 格式：
    {{"follow_up_questions": ["问题1", "问题2", "问题3"]}}
    """
    
    try:
        response = await llm.agenerate([prompt])
        text = response.generations[0][0].text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        result = json.loads(text.strip())
        state['follow_up_questions'] = result.get('follow_up_questions', [])
        logger.info(f"✅ 追问生成成功：{len(state['follow_up_questions'])} 个")
    except Exception as e:
        logger.error(f"❌ 追问生成失败：{e}")
        state['follow_up_questions'] = []
    
    return state


def create_enhanced_qa_agent_graph():
    """创建增强版问答 Agent 图"""
    graph = StateGraph(QAAgentState)
    
    graph.add_node("recognize_intent", recognize_intent)
    graph.add_node("answer_metadata", answer_metadata)
    graph.add_node("generate_answer", generate_answer)
    graph.add_node("generate_follow_up", generate_follow_up)
    
    graph.set_entry_point("recognize_intent")
    
    # 根据意图路由
    def route_by_intent(state: QAAgentState):
        if state.get('intent') == 'metadata':
            return "answer_metadata"
        return "generate_answer"
    
    graph.add_conditional_edges("recognize_intent", route_by_intent)
    graph.add_edge("answer_metadata", "generate_follow_up")
    graph.add_edge("generate_answer", "generate_follow_up")
    graph.add_edge("generate_follow_up", END)
    
    return graph.compile()


_enhanced_qa_agent = None


def get_enhanced_qa_agent():
    global _enhanced_qa_agent
    if _enhanced_qa_agent is None:
        _enhanced_qa_agent = create_enhanced_qa_agent_graph()
    return _enhanced_qa_agent


async def run_enhanced_qa_agent(paper_id: str, question: str, relevant_chunks: list, paper_metadata: dict = None, history_context: str = None) -> dict:
    """运行增强版问答 Agent"""
    logger.info(f"[增强问答 Agent] 处理问题：{question[:50]}...")
    
    initial_state = QAAgentState(
        paper_id=paper_id,
        question=question,
        paper_metadata=paper_metadata or {},
        history_context=history_context or "",
        intent=None,
        relevant_chunks=relevant_chunks,
        answer=None,
        sources=[],
        citations=[],
        follow_up_questions=[],
        confidence=0.0,
        error=None
    )
    
    agent = get_enhanced_qa_agent()
    result = await agent.ainvoke(initial_state)
    
    logger.info(f"✅ [增强问答 Agent] 处理完成")
    
    return {
        "answer": result.get("answer", ""),
        "intent": result.get("intent", ""),
        "sources": result.get("sources", []),
        "citations": result.get("citations", []),
        "follow_up_questions": result.get("follow_up_questions", []),
        "confidence": result.get("confidence", 0.0)
    }
