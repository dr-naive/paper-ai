from app.api.chat import (
    _citations_from_streamed_answer,
    _sse_event,
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
