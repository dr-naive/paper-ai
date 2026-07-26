import asyncio
from types import SimpleNamespace

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from app.llm.client import LLMClient


class FakeChatClient:
    def __init__(self):
        self.messages = None

    async def agenerate(self, messages, **_kwargs):
        self.messages = messages
        return SimpleNamespace(generations=[], llm_output={"token_usage": {"prompt_tokens": 10}})


class FakeStreamingChatClient:
    def astream(self, messages, **_kwargs):
        async def chunks():
            yield SimpleNamespace(
                content="",
                additional_kwargs={"reasoning_content": "先检查证据"},
            )
            yield SimpleNamespace(content="最终回答", additional_kwargs={})

        return chunks()


def test_llm_requests_isolate_untrusted_document_content():
    fake = FakeChatClient()
    client = object.__new__(LLMClient)
    client.provider = "qwen"
    client.client = fake

    asyncio.run(client.agenerate(["paper text"], enable_thinking=False))

    assert isinstance(fake.messages[0][0], SystemMessage)
    assert "不可信数据" in fake.messages[0][0].content
    assert isinstance(fake.messages[0][1], HumanMessage)
    assert fake.messages[0][1].content == "paper text"


def test_llm_stream_separates_reasoning_from_final_answer():
    client = object.__new__(LLMClient)
    client.provider = "deepseek"
    client.client = FakeStreamingChatClient()

    async def collect():
        return [
            item
            async for item in client.astream_content(
                "paper text",
                enable_thinking=True,
            )
        ]

    assert asyncio.run(collect()) == [
        ("reasoning", "先检查证据"),
        ("answer", "最终回答"),
    ]
