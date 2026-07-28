import asyncio

from app.agent.qa_agent.workflow import QAWorkflowState, UnifiedQAWorkflow
from app.agent.qa_agent.enhanced_graph import build_deterministic_citations


class FakeLLM:
    async def astream_content(self, _prompt, *, enable_thinking=None):
        if enable_thinking:
            yield "reasoning", "先核对证据。"
        yield "answer", "论文提出了统一方法 [S1]。"


def test_unified_workflow_streams_nodes_reasoning_answer_and_citations(monkeypatch):
    monkeypatch.setattr(
        "app.agent.qa_agent.workflow.get_llm_client",
        lambda: FakeLLM(),
    )
    state = QAWorkflowState(
        session_id="",
        user_id="",
        paper_id="paper-1",
        question="论文提出了什么？",
        enable_thinking=True,
        persist_message=False,
        paper_metadata={"title": "测试论文"},
        chunks=[{
            "section": "方法",
            "content": "论文提出了统一方法。",
            "page": 3,
            "chunk_index": 1,
        }],
    )
    workflow = UnifiedQAWorkflow(state)

    async def run():
        return [event async for event in workflow.stream()]

    events = asyncio.run(run())
    event_names = [name for name, _payload in events]

    assert workflow.visited_nodes == [
        "load_context",
        "classify_intent",
        "retrieve_evidence",
        "evaluate_evidence",
        "generate_answer",
        "organize_citations",
        "persist_message",
        "finalize",
    ]
    assert "reasoning_delta" in event_names
    assert "answer_delta" in event_names
    assert event_names[-2:] == ["citations", "done"]
    assert state.citations[0]["page"] == 3
    assert state.answer == "论文提出了统一方法 [S1]。"
    assert state.trace["status"] == "completed"
    assert state.trace["model_calls"] == 1
    assert state.trace["answer_tokens"] > 0
    assert state.trace["thinking_tokens"] > 0
    assert state.trace["first_token_ms"] is not None
    assert state.trace["citation_count"] == 1
    assert state.trace["total_ms"] > 0
    assert state.trace["intent_ms"] >= 0
    assert state.trace["retrieval_ms"] >= 0


def test_unified_workflow_routes_missing_evidence_without_calling_llm(monkeypatch):
    monkeypatch.setattr(
        "app.agent.qa_agent.workflow.get_llm_client",
        lambda: (_ for _ in ()).throw(AssertionError("不应调用模型")),
    )
    state = QAWorkflowState(
        session_id="",
        user_id="",
        paper_id="paper-1",
        question="论文没有覆盖的问题",
        persist_message=False,
        paper_metadata={"title": "测试论文"},
    )
    workflow = UnifiedQAWorkflow(state)

    async def run():
        return [event async for event in workflow.stream()]

    events = asyncio.run(run())

    assert "answer_without_evidence" in workflow.visited_nodes
    assert "generate_answer" not in workflow.visited_nodes
    assert state.evidence_confidence == 0.0
    assert state.trace["model_calls"] == 0
    assert state.trace["citation_count"] == 0
    assert any(name == "answer_delta" for name, _payload in events)


def test_graph_definition_exposes_conditional_evidence_route():
    graph = UnifiedQAWorkflow.graph_definition()

    assert graph["start"] == "load_context"
    assert (
        "evaluate_evidence",
        "generate_answer",
        "有证据",
    ) in graph["edges"]
    assert (
        "evaluate_evidence",
        "answer_without_evidence",
        "无证据",
    ) in graph["edges"]


def test_deterministic_citations_hide_duplicate_sources_on_same_page():
    text = "论文提出统一视觉编码器，并通过跨模态注意力完成图文语义对齐。" * 3
    chunks = [
        {"content": text, "section": "全文", "page": 4},
        {
            "content": text,
            "section": "方法",
            "page": 4,
            "element_id": "element-4-1",
            "bbox": [40, 100, 500, 180],
        },
    ]
    citations = build_deterministic_citations("结论 [S1][S2]", chunks)
    assert len(citations) == 1
    assert citations[0]["element_id"] == "element-4-1"
