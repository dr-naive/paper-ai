"""Agent 状态定义模块"""
from typing import TypedDict, List, Optional, Dict, Any


class PaperParserState(TypedDict):
    paper_id: str
    file_path: str
    raw_text: str
    title: Optional[str]
    authors: Optional[str]
    abstract: Optional[str]
    sections: List[Dict[str, Any]]
    keywords: List[str]
    parsed: bool
    error: Optional[str]


class QAAgentState(TypedDict):
    paper_id: str
    question: str
    paper_metadata: Dict[str, Any]  # 论文元数据：title, authors, abstract 等
    history_context: str  # 历史对话上下文
    intent: Optional[str]
    metadata_field: Optional[str]
    simple_question: bool
    relevant_chunks: List[Dict[str, Any]]
    answer: Optional[str]
    sources: List[str]
    citations: List[Dict[str, Any]]  # 引用溯源：[{section, text, position}]
    follow_up_questions: List[str]  # 智能追问
    generate_follow_up: bool  # 是否同步生成智能追问
    confidence: float
    error: Optional[str]


class SummarizerState(TypedDict):
    paper_id: str
    summary_type: str
    sections: List[Dict[str, Any]]
    summary: Optional[str]
    key_findings: List[str]
    contributions: List[str]
    limitations: List[str]
    error: Optional[str]
