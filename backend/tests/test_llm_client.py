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
