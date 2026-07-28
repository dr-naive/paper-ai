"""增强版问答 Agent 工作流模块 - 支持引用溯源和智能追问"""
from langgraph.graph import StateGraph, END
from app.agent.state import QAAgentState
from app.llm.client import get_llm_client
import json
import logging
import re
import time
from difflib import SequenceMatcher
from typing import Any
from loguru import logger

logger = logging.getLogger(__name__)


METADATA_PATTERNS = {
    "title": [r"标题", r"题目", r"title", r"paper name"],
    "authors": [r"作者", r"谁写", r"author", r"authors"],
    "abstract": [r"摘要", r"abstract"],
    "keywords": [r"关键词", r"关键字", r"keywords"],
    "venue": [r"期刊", r"会议", r"venue", r"发表在哪", r"published"],
    "publication_year": [r"年份", r"哪一年", r"year"],
    "doi": [r"\bdoi\b"],
}

SIMPLE_INTENT_PATTERNS = [
    r"总结",
    r"概括",
    r"主要内容",
    r"讲了什么",
    r"研究什么",
    r"核心观点",
    r"main idea",
    r"summary",
    r"summarize",
    r"what is .* about",
]

CONTEXT_DEPENDENT_PATTERNS = [
    r"这个",
    r"上面",
    r"刚才",
    r"前面",
    r"\bit\b",
    r"\bthat\b",
    r"\babove\b",
    r"\bprevious\b",
]

COMPLEX_REASONING_PATTERNS = [
    r"证明",
    r"推导",
    r"数学",
    r"公式",
    r"为什么.*成立",
    r"derive",
    r"prove",
    r"equation",
    r"formula",
]

DEEP_REASONING_CONTEXT_PATTERNS = [
    r"复杂",
    r"多步",
    r"严格",
    r"数学",
    r"推导",
    r"证明",
    r"公式",
    r"成立",
    r"derive",
    r"prove",
    r"equation",
    r"formula",
    r"theorem",
]


def detect_metadata_intent(question: str) -> str | None:
    q = question.lower()
    # “表1的标题”等媒体问题不是论文元数据问题。
    if re.search(r"(?:表|table|图|figure)\s*\d+", q, re.IGNORECASE):
        return None
    for field, patterns in METADATA_PATTERNS.items():
        if any(re.search(pattern, q, re.IGNORECASE) for pattern in patterns):
            return field
    return None


def detect_simple_intent(question: str) -> str | None:
    """Conservative rule path for short overview questions."""
    q = question.lower().strip()
    if len(q) > 80:
        return None
    if any(re.search(pattern, q, re.IGNORECASE) for pattern in CONTEXT_DEPENDENT_PATTERNS):
        return None
    if any(re.search(pattern, q, re.IGNORECASE) for pattern in SIMPLE_INTENT_PATTERNS):
        return "general"
    return None


def needs_deep_thinking(question: str) -> bool:
    q = question.lower().strip()
    if any(re.search(pattern, q, re.IGNORECASE) for pattern in COMPLEX_REASONING_PATTERNS):
        return True
    # “机制/原理/mechanism”类问题常常只是证据抽取与归纳，不应单独触发
    # thinking；只有同时出现证明、公式、多步推理等强信号时才开启。
    has_mechanism_word = bool(re.search(r"机制|原理|mechanism|principle", q, re.IGNORECASE))
    has_deep_context = any(
        re.search(pattern, q, re.IGNORECASE)
        for pattern in DEEP_REASONING_CONTEXT_PATTERNS
    )
    return has_mechanism_word and has_deep_context


def safe_json_loads(text: str) -> dict:
    """Parse model JSON output with light cleanup."""
    cleaned = text.strip()
    if "```json" in cleaned:
        cleaned = cleaned.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in cleaned:
        cleaned = cleaned.split("```", 1)[1].split("```", 1)[0]
    try:
        return json.loads(cleaned.strip())
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def _normalize_locator_text(text: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", str(text or "").lower())


def _best_source_excerpt(citation_text: str, source_content: str, max_chars: int = 180) -> str:
    """Choose an exact source sentence for client-side PDF text location."""
    source_content = str(source_content or "").strip()
    if not source_content:
        return ""

    candidates = [
        part.strip()
        for part in re.split(r"(?<=[。！？.!?；;])\s*|\n+", source_content)
        if len(_normalize_locator_text(part)) >= 8
    ]
    if not candidates:
        return source_content[:max_chars]

    normalized_citation = _normalize_locator_text(citation_text)
    if not normalized_citation:
        return candidates[0][:max_chars]

    best = max(
        candidates,
        key=lambda part: SequenceMatcher(
            None,
            normalized_citation,
            _normalize_locator_text(part),
        ).ratio(),
    )
    return best[:max_chars]


def _enrich_citations(citations: list, chunks: list) -> list:
    """Attach deterministic retrieval metadata used for PDF source location."""
    enriched = []
    for citation in citations or []:
        if not isinstance(citation, dict):
            continue

        item = dict(citation)
        source = None
        source_id = str(item.get("source_id") or "").upper()
        if source_id.startswith("S") and source_id[1:].isdigit():
            index = int(source_id[1:]) - 1
            if 0 <= index < len(chunks):
                source = chunks[index]

        if source is None:
            section = str(item.get("section") or "")
            source = next(
                (chunk for chunk in chunks if str(chunk.get("section") or "") == section),
                None,
            )

        if source:
            item["source_id"] = f"S{chunks.index(source) + 1}"
            for field in (
                "page",
                "table_number",
                "chunk_type",
                "chunk_index",
                "element_id",
                "element_type",
                "bbox",
                "section_path",
                "layout_confidence",
                "table_id",
                "row_index",
                "fields",
                "cell_bboxes",
            ):
                if source.get(field) is not None:
                    item[field] = source[field]
            if source.get("page") is not None:
                item["position"] = f"PDF 第{source['page']}页"
            item["search_text"] = _best_source_excerpt(
                item.get("text", ""),
                source.get("content", ""),
            )
        enriched.append(item)
    return enriched


def build_deterministic_citations(answer: str, chunks: list) -> list:
    """Resolve model source markers to exact retrieval metadata."""
    source_indexes = []
    for value in re.findall(r"\[S(\d+)\]", answer or "", flags=re.IGNORECASE):
        index = int(value) - 1
        if 0 <= index < len(chunks) and index not in source_indexes:
            source_indexes.append(index)

    citations = []
    for index in source_indexes:
        chunk = chunks[index]
        content = str(chunk.get("content") or "").strip()
        citations.append({
            "source_id": f"S{index + 1}",
            "section": chunk.get("section", "未知章节"),
            "text": _best_source_excerpt("", content),
        })
    return _deduplicate_citations(_enrich_citations(citations, chunks))


def _citation_text_signature(value: Any) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", str(value or "").lower())


def _citation_precision(item: dict) -> tuple[int, int, int]:
    return (
        int(bool(item.get("element_id") and item.get("bbox"))),
        int(bool(item.get("table_id") and item.get("row_index") is not None)),
        int(bool(item.get("search_text"))),
    )


def _deduplicate_citations(citations: list[dict]) -> list[dict]:
    """Remove repeated display citations without changing source provenance."""
    unique: list[dict] = []
    for citation in citations:
        duplicate_index = None
        for index, existing in enumerate(unique):
            if str(existing.get("page") or "") != str(citation.get("page") or ""):
                continue
            same_element = (
                citation.get("element_id")
                and citation.get("element_id") == existing.get("element_id")
            )
            same_bbox = (
                citation.get("bbox")
                and citation.get("bbox") == existing.get("bbox")
            )
            left = _citation_text_signature(
                citation.get("search_text") or citation.get("text")
            )
            right = _citation_text_signature(
                existing.get("search_text") or existing.get("text")
            )
            shorter, longer = sorted((left, right), key=len)
            same_text = bool(
                len(shorter) >= 24
                and (
                    (shorter in longer and len(shorter) / max(len(longer), 1) >= 0.72)
                    or SequenceMatcher(None, left, right).ratio() >= 0.88
                )
            )
            if same_element or same_bbox or same_text:
                duplicate_index = index
                break
        if duplicate_index is None:
            unique.append(citation)
        elif _citation_precision(citation) > _citation_precision(unique[duplicate_index]):
            unique[duplicate_index] = citation
    return unique


def calculate_evidence_confidence(
    answer: str,
    citations: list,
    chunks: list,
    intent: str | None = None,
) -> float:
    """Estimate source support, never statistical answer correctness."""
    if not str(answer or "").strip():
        return 0.0
    valid_citations = [item for item in citations or [] if isinstance(item, dict)]
    if intent == "metadata":
        return 0.95 if valid_citations else 0.0
    if not valid_citations or not chunks:
        return 0.0

    grounded = 0
    for citation in valid_citations:
        source_id = str(citation.get("source_id") or "").upper()
        if not (source_id.startswith("S") and source_id[1:].isdigit()):
            continue
        index = int(source_id[1:]) - 1
        if not 0 <= index < len(chunks):
            continue
        citation_text = _normalize_locator_text(citation.get("text", ""))
        source_text = _normalize_locator_text(chunks[index].get("content", ""))
        if citation_text and (
            citation_text in source_text
            or SequenceMatcher(None, citation_text, source_text).ratio() >= 0.55
        ):
            grounded += 1

    grounding_ratio = grounded / len(valid_citations)
    citation_coverage_factor = 0.7 + 0.3 * min(len(valid_citations) / 2, 1.0)
    return round(grounding_ratio * citation_coverage_factor, 4)


async def recognize_intent(state: QAAgentState) -> QAAgentState:
    """识别问题意图"""
    logger.info(f"[增强问答 Agent] 识别问题意图")
    
    question = state['question']
    metadata_field = detect_metadata_intent(question)
    if metadata_field:
        state['intent'] = 'metadata'
        state['intent_confidence'] = 0.95
        state['metadata_field'] = metadata_field
        logger.info(f"✅ 规则识别元数据问题：{metadata_field}")
        return state

    simple_intent = detect_simple_intent(question)
    if simple_intent:
        state['intent'] = simple_intent
        state['intent_confidence'] = 0.8
        state['simple_question'] = True
        logger.info(f"✅ 规则识别简单问题：{simple_intent}")
        return state

    if re.search(r"表格|(?:表|table)\s*\d+", question, re.IGNORECASE):
        state['intent'] = 'detail'
        state['intent_confidence'] = 0.95
        logger.info("✅ 规则识别表格细节问题")
        return state

    llm = get_llm_client()
    
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
        response = await llm.agenerate([prompt], json_mode=True, enable_thinking=False)
        text = response.generations[0][0].text.strip()
        result = safe_json_loads(text)
        state['intent'] = result.get('intent', 'general')
        state['intent_confidence'] = result.get('confidence', 0.5)
        logger.info(f"✅ 意图识别成功：{state['intent']}")
    except Exception as e:
        logger.error(f"❌ 意图识别失败：{e}")
        state['intent'] = 'general'
        state['intent_confidence'] = 0.5
    
    return state


async def answer_metadata(state: QAAgentState) -> QAAgentState:
    """回答元数据类问题（作者、标题等）"""
    logger.info(f"[增强问答 Agent] 回答元数据问题")
    
    metadata = state.get('paper_metadata', {})
    question = state['question']
    field = state.get('metadata_field') or detect_metadata_intent(question)
    field_labels = {
        "title": "标题",
        "authors": "作者",
        "abstract": "摘要",
        "keywords": "关键词",
        "venue": "发表 venue",
        "publication_year": "发表年份",
        "doi": "DOI",
    }

    if field:
        value = metadata.get(field)
        if isinstance(value, list):
            value_text = "、".join(str(v) for v in value if v)
        else:
            value_text = str(value or "").strip()
        label = field_labels.get(field, field)
        if value_text:
            state['answer'] = f"论文的{label}是：{value_text}"
            state['citations'] = [{"section": "论文元数据", "text": f"{label}：{value_text}", "position": "metadata"}]
            state['sources'] = ["论文元数据"]
        else:
            state['answer'] = f"论文信息中未提供{label}。"
            state['citations'] = []
            state['sources'] = []
        return state
    
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
        response = await llm.agenerate([prompt], json_mode=True, enable_thinking=False)
        text = response.generations[0][0].text.strip()
        try:
            result = safe_json_loads(text)
        except json.JSONDecodeError:
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
    
    table_question = bool(re.search(r"表格|(?:表|table)\s*\d+", question, re.IGNORECASE))

    # 构建带章节和媒体元数据的上下文，保留更多原文
    context_parts = []
    for i, c in enumerate(chunks):
        section = c.get('section', '未知章节')
        content = c.get('content', '')
        media_label = ""
        if c.get("chunk_type") == "table":
            number = c.get("table_number")
            media_label = f"[表格: 表{number}]\n" if number else "[表格]\n"
        context_parts.append(f"[来源: S{i + 1}]\n[章节: {section}]\n{media_label}{content}")
    
    context = "\n\n---\n\n".join(context_parts)
    
    # 构建历史对话提示
    history_prompt = ""
    if history_context:
        history_prompt = f"""
        
        【历史对话参考】
        以下是之前的对话记录，请结合上下文理解用户当前问题的意图：
        {history_context}
        
        注意：回答当前问题时可以参考历史信息，但要以论文内容为准。
        """

    table_prompt = ""
    if table_question:
        table_prompt = """
    7. 这是表格数据问题。优先依据标记为[表格]的原始表格数据作答，说明列名、主要行和对应数值；不要只复述表格总结。
    8. 若上下文中已经提供目标表格，不得回答“未找到”；若表格过长，应概括结构并列出关键数据，明确说明省略范围。
    9. 表中的方法数量、行列数量、数值和排名必须逐项核对后再陈述；不要根据印象补全。除非逐行计数并确认，否则不要写“其他N种方法”，直接列出方法名。
    10. 必须使用 Markdown 表格展示用户要求的数据。单个表格尽量不超过 6 列；原表很宽时按数据集或指标拆成最多 2-3 个小表，或将表格转置。
        对“多个数据集 × ACC/F1”这类表，优先每 3-4 个数据集一组，列格式为“Method | 数据集1 (ACC/F1) | 数据集2 (ACC/F1) ...”，不要为每个数据集单独生成一个表。
    11. 表格之后用 2-4 个项目符号总结关键观察；缺失值保持为“-”，不得自行推测。
        """
    
    prompt = f"""
    请根据以下论文内容回答问题。要求：
    1. 回答准确、完整、专业
    2. 每个关键结论后只标注对应来源编号，如 [S1]、[S2]
    3. 如果内容不足以回答问题，请明确说明"论文中未提及"
    4. 回答要有条理，使用分点或分段
    5. 只能使用上下文中提供的来源编号，不要生成章节、页码、引用原文或 JSON
    6. 使用 Markdown 排版：段落之间空一行；并列内容每项单独一行；适合比较的数据使用表格。不要把编号、项目符号和多个数据项挤在同一行。
    {table_prompt}
    {history_prompt}
    问题：{question}
    
    相关内容：
    {context}
    
    直接返回回答正文，不要使用 JSON。
    """
    
    try:
        response = await llm.agenerate(
            [prompt],
            json_mode=False,
            enable_thinking=needs_deep_thinking(question)
        )
        answer = response.generations[0][0].text.strip()
        state['answer'] = answer or '暂无回答'
        state['citations'] = build_deterministic_citations(answer, chunks)
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
    if not state.get('generate_follow_up', True):
        state['follow_up_questions'] = []
        logger.info("[增强问答 Agent] 跳过同步追问生成")
        return state
    
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
        response = await llm.agenerate([prompt], json_mode=True, enable_thinking=False)
        text = response.generations[0][0].text.strip()
        result = safe_json_loads(text)
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
    graph.add_node("generate_follow_up_questions", generate_follow_up)
    
    graph.set_entry_point("recognize_intent")
    
    # 根据意图路由
    def route_by_intent(state: QAAgentState):
        if state.get('intent') == 'metadata':
            return "answer_metadata"
        return "generate_answer"
    
    graph.add_conditional_edges("recognize_intent", route_by_intent)
    graph.add_edge("answer_metadata", "generate_follow_up_questions")
    graph.add_edge("generate_answer", "generate_follow_up_questions")
    graph.add_edge("generate_follow_up_questions", END)
    
    return graph.compile()


_enhanced_qa_agent = None


def get_enhanced_qa_agent():
    global _enhanced_qa_agent
    if _enhanced_qa_agent is None:
        _enhanced_qa_agent = create_enhanced_qa_agent_graph()
    return _enhanced_qa_agent


async def generate_follow_up_questions(question: str, answer: str, intent: str = "general") -> list[str]:
    state = QAAgentState(
        paper_id="",
        question=question,
        paper_metadata={},
        history_context="",
        intent=intent,
        relevant_chunks=[],
        answer=answer,
        sources=[],
        citations=[],
        follow_up_questions=[],
        generate_follow_up=True,
        metadata_field=None,
        simple_question=False,
        intent_confidence=0.0,
        evidence_confidence=0.0,
        error=None
    )
    result = await generate_follow_up(state)
    return result.get("follow_up_questions", [])


async def run_enhanced_qa_agent(
    paper_id: str,
    question: str,
    relevant_chunks: list,
    paper_metadata: dict = None,
    history_context: str = None,
    generate_follow_up: bool = True
) -> dict:
    """Compatibility wrapper around the same workflow used by streaming chat."""
    from app.agent.qa_agent.workflow import run_preloaded_qa_workflow

    logger.info("[统一问答工作流] 处理预检索问题：%s...", question[:50])
    result = await run_preloaded_qa_workflow(
        paper_id=paper_id,
        question=question,
        chunks=relevant_chunks,
        paper_metadata=paper_metadata,
        history_context=history_context or "",
        enable_thinking=needs_deep_thinking(question),
    )
    if generate_follow_up:
        result["follow_up_questions"] = await generate_follow_up_questions(
            question,
            result.get("answer", ""),
            result.get("intent", "general"),
        )
    return result
