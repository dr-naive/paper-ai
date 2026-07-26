import asyncio
import json

from app.api.chat import (
    _AnswerTask,
    _citations_from_streamed_answer,
    _consume_answer_events,
    _sse_event,
    _stream_answer_task,
    _streaming_prompt,
    router,
)


def test_sse_event_keeps_unicode_and_protocol_separator():
    event = _sse_event("answer_delta", {"text": "流式回答"})

    assert event.startswith("event: answer_delta\ndata: ")
    assert '"text": "流式回答"' in event
    assert event.endswith("\n\n")


def test_streaming_prompt_requires_grounded_inline_source_ids():
    prompt = _streaming_prompt(
        "主要贡献是什么？",
        [{"section": "引言", "content": "本文提出一种新方法。"}],
        "用户: 研究对象是什么？\nAI: 图像检测。",
    )

    assert "直接输出 Markdown 正文" in prompt
    assert "推理过程和最终回答均使用简体中文" in prompt
    assert "不要因此切换为整段英文推理或回答" in prompt
    assert "[来源 S1]" in prompt
    assert "每个关键结论后必须标注" in prompt
    assert "历史对话" in prompt


def test_streamed_citations_are_unique_and_keep_pdf_metadata():
    chunks = [
        {
            "section": "方法",
            "content": "本文提出一种融合模型，用于完成多模态检测任务。",
            "page": 7,
            "chunk_index": 3,
        },
        {
            "section": "实验",
            "content": "实验结果表明，该模型在测试集上取得最佳性能。",
            "page": 12,
        },
    ]

    citations = _citations_from_streamed_answer(
        "模型结构见 [S1]，实验结论见 [S2]，仍由 [S1] 支持。",
        chunks,
    )

    assert [item["source_id"] for item in citations] == ["S1", "S2"]
    assert citations[0]["page"] == 7
    assert citations[0]["position"] == "PDF 第7页"
    assert citations[1]["section"] == "实验"


def test_stream_route_is_registered():
    paths = {route.path for route in router.routes}

    assert "/api/v1/chat/sessions/{session_id}/ask/stream" in paths
    assert "/api/v1/chat/answer-tasks/{task_id}/stream" in paths
    assert "/api/v1/chat/answer-tasks/{task_id}/stop" in paths


def test_background_answer_task_can_be_resumed_from_offset():
    task = _AnswerTask(
        task_id="task-1",
        session_id="session-1",
        user_id="user-1",
        question="测试问题",
    )

    async def source():
        yield _sse_event("status", {"stage": "generating", "message": "正在生成回答"})
        yield _sse_event("reasoning_delta", {"text": "先分析"})
        yield _sse_event("reasoning_done", {})
        yield _sse_event("answer_delta", {"text": "前半段"})
        yield _sse_event("answer_delta", {"text": "后半段"})
        yield _sse_event("citations", {"items": [{"source_id": "S1"}]})
        yield _sse_event("done", {"message_id": "message-1"})

    async def run():
        await _consume_answer_events(task, source())
        return [event async for event in _stream_answer_task(task, offset=3)]

    events = asyncio.run(run())
    delta_blocks = [block for block in events if block.startswith("event: answer_delta")]

    assert task.status == "completed"
    assert task.reasoning == "先分析"
    assert task.reasoning_done is True
    assert task.answer == "前半段后半段"
    assert len(delta_blocks) == 1
    assert json.loads(delta_blocks[0].split("data: ", 1)[1])["text"] == "后半段"
