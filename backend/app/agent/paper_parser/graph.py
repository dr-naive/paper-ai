"""论文解析 Agent 工作流模块"""
from langgraph.graph import StateGraph, END
from app.agent.state import PaperParserState
from app.llm.client import get_llm_client
import json
import re
import time
from loguru import logger


_TITLE_STOP_PATTERN = re.compile(
    r"^(摘要|abstract|关键词|keywords?)(?:\s|[：:])*$",
    re.IGNORECASE,
)
_FRONT_MATTER_PATTERN = re.compile(
    r"^(published\s+as|arxiv\b|doi\b|preprint\b|proceedings\b|"
    r"copyright\b|收稿日期|基金项目)",
    re.IGNORECASE,
)
_AFFILIATION_PATTERN = re.compile(
    r"(大学|学院|研究院|实验室|研究所|医院|公司|中心|"
    r"university|college|school|institute|laborator(?:y|ies)|department)",
    re.IGNORECASE,
)


def _clean_title(value: str) -> str:
    """Normalize a title and remove content following common paper boundaries."""
    title = str(value or "").strip()
    title = re.split(
        r"(?:\n|\r|\s{2,})(?:摘要|abstract|关键词|keywords?)\s*[：:]?",
        title,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    return re.sub(r"\s+", " ", title).strip(" -—|，,。")


def _looks_like_author_line(line: str, next_line: str = "") -> bool:
    """Identify common author rows without treating numbered titles as authors."""
    if "@" in line or _AFFILIATION_PATTERN.search(line):
        return True
    has_markers = bool(re.search(r"\d(?:\s*[,，]\s*\d)*[†*]?", line))
    has_name_separators = line.count("，") + line.count(",") + line.count("、") >= 2
    next_is_affiliation = bool(_AFFILIATION_PATTERN.search(next_line))
    english_author_row = (
        next_is_affiliation
        and bool(re.search(r",|\band\b|&", line, re.IGNORECASE))
        and len(line.split()) <= 16
    )
    return english_author_row or (
        has_markers and (has_name_separators or next_is_affiliation)
    )


def _extract_front_page_title(lines: list[str]) -> str:
    """Extract the title block before authors/affiliations/abstract on page one."""
    front_lines = []
    for line in lines[:30]:
        if _TITLE_STOP_PATTERN.match(line):
            break
        front_lines.append(line)

    while front_lines and _FRONT_MATTER_PATTERN.match(front_lines[0]):
        front_lines.pop(0)

    title_parts = []
    for index, line in enumerate(front_lines):
        next_line = front_lines[index + 1] if index + 1 < len(front_lines) else ""
        if _looks_like_author_line(line, next_line):
            break
        if 2 <= len(line) <= 200:
            title_parts.append(line)
        if len(title_parts) >= 4:
            break

    return _clean_title(" ".join(title_parts))


def _extract_metadata_by_rules(raw_text: str) -> dict:
    """基于首页结构从文本中提取元数据（LLM 失败时的 fallback）。"""
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    if not lines:
        return {}

    result = {"title": _extract_front_page_title(lines) or _clean_title(lines[0])[:200]}
    author_candidates = []
    for index, line in enumerate(lines[:20]):
        next_line = lines[index + 1] if index + 1 < len(lines) else ""
        if _looks_like_author_line(line, next_line) and not _AFFILIATION_PATTERN.search(line):
            author_candidates.append(line)

    if author_candidates:
        authors = re.sub(r"[\d†*]", "", author_candidates[0])
        result["authors"] = re.sub(r"\s+", " ", authors.replace("，", ", ")).strip(" ,")

    return result


def _select_title(model_title: object, raw_text: str) -> str:
    """Prefer the model title unless it has clear signs of swallowed body text."""
    candidate = _clean_title(str(model_title or ""))
    rule_title = _extract_metadata_by_rules(raw_text).get("title", "")
    looks_corrupted = (
        len(candidate) > 200
        or len(candidate.split()) > 35
        or bool(re.search(r"(本文|我们提出|研究表明|实验表明).{20,}", candidate))
    )
    if not candidate or looks_corrupted:
        return rule_title or candidate[:200] or "未知论文"
    return candidate[:200]


def _parse_sections_by_rules(raw_text: str) -> list[dict]:
    """Parse common paper headings without an LLM call."""
    heading_pattern = re.compile(
        r"^(abstract|摘要|introduction|related work|background|method|methods|methodology|experiment|experiments|evaluation|result|results|discussion|conclusion|references|参考文献|"
        r"\d+(?:\.\d+)*\s+[A-Z][A-Za-z0-9 ,:()/-]{2,80}|"
        r"\d+(?:\.\d+)*\s+[\u4e00-\u9fffA-Za-z0-9 ,:()/-]{2,80})$",
        re.IGNORECASE,
    )
    lines = [line.strip() for line in raw_text.splitlines()]
    sections: list[dict] = []
    current_title: str | None = None
    current_content: list[str] = []

    def flush_current() -> None:
        if current_title and current_content:
            content = "\n".join(line for line in current_content if line).strip()
            if content:
                sections.append({
                    "title": current_title,
                    "content": content,
                    "key_points": []
                })

    for line in lines:
        if not line:
            if current_content:
                current_content.append("")
            continue

        is_heading = (
            len(line) <= 120
            and bool(heading_pattern.match(line))
            and not line.endswith(".")
        )
        if is_heading:
            flush_current()
            current_title = line
            current_content = []
        elif current_title:
            current_content.append(line)

    flush_current()

    meaningful_sections = [
        section for section in sections
        if len(section.get("content", "")) >= 20
    ]
    return meaningful_sections


async def extract_metadata(state: PaperParserState) -> PaperParserState:
    """提取论文元数据（标题、作者、摘要等）"""
    logger.info(f"[论文解析 Agent] 提取元数据")
    
    raw_text = state['raw_text'][:1000]
    logger.info(f"📥 输入文本长度: {len(raw_text)}, 前200字符: {repr(raw_text[:200])}")
    
    result = {}
    use_rule_extraction = False
    
    try:
        llm = get_llm_client()
        prompt = f"""请从以下论文文本中提取信息。返回严格的 JSON 格式，不要包含任何其他内容：

{{"title":"标题","authors":"作者","abstract":"摘要","keywords":["关键词1","关键词2"]}}

论文内容：
{raw_text}

注意：
- 如果某个字段找不到，使用空字符串或空列表
- 作者名只保留姓名，去掉机构编号"""
        
        response = await llm.agenerate([prompt], json_mode=True, enable_thinking=False)
        text = response.generations[0][0].text.strip()
        logger.info(f"📝 LLM 返回原始内容: {repr(text[:300])}")
        
        if not text:
            logger.warning(f"⚠️ LLM 返回空内容，使用规则提取")
            use_rule_extraction = True
        else:
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            
            logger.info(f"📝 清理后内容: {repr(text[:300])}")
            
            try:
                result = json.loads(text.strip())
            except json.JSONDecodeError:
                logger.warning(f"⚠️ JSON 解析失败，使用规则提取")
                use_rule_extraction = True
    
    except Exception as e:
        logger.warning(f"⚠️ LLM 调用失败，使用规则提取: {e}")
        use_rule_extraction = True
    
    if use_rule_extraction:
        result = _extract_metadata_by_rules(raw_text)
    
    if not result.get('title'):
        result = _extract_metadata_by_rules(raw_text)
    
    state['title'] = _select_title(result.get('title'), raw_text)
        
    # authors：如果是列表，用逗号拼接成字符串；否则直接转字符串
    authors_raw = result.get('authors', '')
    if isinstance(authors_raw, list):
        state['authors'] = ", ".join(str(a) for a in authors_raw)
    else:
        state['authors'] = str(authors_raw)
            
    state['abstract'] = str(result.get('abstract', ''))
        
    # keywords：强制转为 JSON 格式的字符串（如 '["AI", "IFDL"]'）
    keywords_raw = result.get('keywords', [])
    if isinstance(keywords_raw, list):
        state['keywords'] = json.dumps(keywords_raw, ensure_ascii=False)
    else:
        state['keywords'] = str(keywords_raw)
            
    logger.info(f"✅ 元数据提取成功：{state['title'][:50]}...")
    
    return state


async def parse_sections(state: PaperParserState) -> PaperParserState:
    """解析论文内容分段（100-200 字）"""
    logger.info(f"[论文解析 Agent] 解析章节内容")
    
    started_at = time.perf_counter()
    llm = get_llm_client()
    raw_text = state['raw_text']

    rule_sections = _parse_sections_by_rules(raw_text)
    if len(rule_sections) >= 2:
        state['sections'] = rule_sections
        logger.info(f"✅ 规则章节解析成功：{len(state['sections'])} 个章节，耗时 {time.perf_counter() - started_at:.2f}s")
        return state

    prompt = f"""
    你是一个严格的 JSON 生成器。请将以下论文内容分段，每段包含 title, content, key_points。
    
    论文内容：
    {raw_text[:5000]}
    
    【最高指令 - 必须严格遵守】：
    1. 必须且只能返回一个合法的 JSON 数组。
    2. 绝对不要包含任何 Markdown 标记（严禁使用 ```json 或 ```）。
    3. 绝对不要包含任何解释性文字、前言或后语（不要说“好的”、“这是”等）。
    4. 你的回答必须直接以 [ 开头，以 ] 结尾。
    
    正确的返回示例：
    [
      {{
        "title": "研究背景",
        "content": "图像伪造检测旨在识别...",
        "key_points": ["识别篡改", "定位区域"]
      }},
      {{
        "title": "现有问题",
        "content": "现有方法多为黑盒模型...",
        "key_points": ["黑盒模型", "缺乏解释"]
      }}
    ]
    """
    
    try:
        response = await llm.agenerate([prompt], json_mode=True, enable_thinking=False)
        text = response.generations[0][0].text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        sections = json.loads(text.strip())
        
        for sec in sections:
            kp = sec.get('key_points', [])
            if not isinstance(kp, list):
                sec['key_points'] = [str(kp)] if kp else []
                
        state['sections'] = sections
        logger.info(f"✅ LLM 章节解析成功：{len(state['sections'])} 个章节，耗时 {time.perf_counter() - started_at:.2f}s")
        
    except Exception as e:
        logger.error(f"❌ 章节解析失败：{e}")
        state['sections'] = [
            {
                "title": "全文",
                "content": raw_text[:1000] + "...",
                "key_points": []
            }
        ]


async def finalize_parsing(state: PaperParserState) -> PaperParserState:
    """完成解析"""
    logger.info(f"[论文解析 Agent] 完成解析")
    state['parsed'] = True
    
    if not state.get('title') or state['title'] == '未知论文':
        state['sections'] = [{
            'title': '全文',
            'content': state.get('raw_text', '')[:500],
            'key_points': []
        }]
    
    return state


def create_paper_parser_graph():
    """创建论文解析 Agent 图"""
    graph = StateGraph(PaperParserState)
    
    graph.add_node("extract_metadata", extract_metadata)
    graph.add_node("parse_sections", parse_sections)
    graph.add_node("finalize_parsing", finalize_parsing)
    
    graph.set_entry_point("extract_metadata")
    graph.add_edge("extract_metadata", "parse_sections")
    graph.add_edge("parse_sections", "finalize_parsing")
    graph.add_edge("finalize_parsing", END)
    
    return graph.compile()


_paper_parser = None


def get_paper_parser_agent():
    global _paper_parser
    if _paper_parser is None:
        _paper_parser = create_paper_parser_graph()
    return _paper_parser


async def run_paper_parser(paper_id: str, file_path: str, raw_text: str) -> dict:
    """运行论文解析 Agent"""
    logger.info(f"[论文解析 Agent] 开始解析论文：{paper_id}")
    
    initial_state = PaperParserState(
        paper_id=paper_id,
        file_path=file_path,
        raw_text=raw_text,
        title=None,
        authors=None,
        abstract=None,
        sections=[],
        keywords=[],
        parsed=False,
        error=None
    )
    
    agent = get_paper_parser_agent()
    result = await agent.ainvoke(initial_state)
    
    logger.info(f"✅ [论文解析 Agent] 解析完成")
    
    return {
        "title": result.get("title", ""),
        "authors": result.get("authors", ""),
        "abstract": result.get("abstract", ""),
        "sections": result.get("sections", []),
        "keywords": result.get("keywords", []),
        "parsed": result.get("parsed", False)
    }
