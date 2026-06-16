"""论文解析 Agent 工作流模块"""
from langgraph.graph import StateGraph, END
from app.agent.state import PaperParserState
from app.llm.client import get_llm_client
import json
import re
from loguru import logger


def _extract_metadata_by_rules(raw_text: str) -> dict:
    """基于规则从文本中提取元数据（LLM 失败时的 fallback）"""
    result = {}
    
    lines = raw_text.split('\n')
    lines = [line.strip() for line in lines if line.strip()]
    
    if not lines:
        return result
    
    title_parts = []
    author_candidates = []
    
    for i, line in enumerate(lines[:15]):
        if not line or len(line) < 2:
            continue
        
        has_chinese = any('\u4e00' <= c <= '\u9fff' for c in line)
        has_english = any('a' <= c.lower() <= 'z' for c in line)
        has_number = any('0' <= c <= '9' for c in line)
        
        if has_chinese and has_english and ':' in line and len(line) > 10:
            title_parts.append(line)
        elif title_parts and has_chinese and len(line) > 5 and not has_number:
            title_parts.append(line)
        elif has_chinese and len(line) < 150:
            author_pattern = re.search(r'([\u4e00-\u9fff]+(?:[\d,，、]+[\u4e00-\u9fff]+)*)', line)
            if author_pattern and len(author_pattern.group(1)) >= 2:
                author_candidates.append(author_pattern.group(1))
    
    if title_parts:
        full_title = ' '.join(title_parts).replace('  ', ' ').strip()
        full_title = full_title.replace('，', '')
        full_title = full_title.replace('。', '')
        result['title'] = full_title
    elif lines:
        result['title'] = lines[0][:100]
    
    if author_candidates:
        authors = author_candidates[0]
        authors = re.sub(r'[\d†]', '', authors)
        authors = authors.replace('，', ', ')
        result['authors'] = authors.strip()
    
    return result


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
        
        response = await llm.agenerate([prompt])
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
    
    # 【核心修复】：强制类型转换，确保存入数据库的绝对是字符串！
    state['title'] = str(result.get('title', '未知论文')).strip() or '未知论文'
        
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
    
    llm = get_llm_client()
    raw_text = state['raw_text']
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
        response = await llm.agenerate([prompt])
        text = response.generations[0][0].text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        sections = json.loads(text.strip())
        
        # 【核心修复】：遍历每个章节，把 key_points 列表强制转为 JSON 字符串
        for sec in sections:
            kp = sec.get('key_points', [])
            if isinstance(kp, list):
                sec['key_points'] = json.dumps(kp, ensure_ascii=False)
            else:
                sec['key_points'] = str(kp)
                
        state['sections'] = sections[:10]  # 限制最多 10 个章节
        logger.info(f"✅ 章节解析成功：{len(state['sections'])} 个章节")
        
    except Exception as e:
        logger.error(f"❌ 章节解析失败：{e}")
        # 【核心修复】：异常时的默认章节，key_points 也必须是字符串 "[]"
        state['sections'] = [
            {
                "title": "全文",
                "content": raw_text[:1000] + "...",
                "key_points": "[]"  # 字符串 "[]"
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
