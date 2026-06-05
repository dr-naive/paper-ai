"""LLM 大模型客户端模块"""
from typing import Optional, List
from langchain_openai import ChatOpenAI
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self):
        self.provider = settings.LLM_PROVIDER
        self.client = self._create_client()
    
    def _create_client(self) -> ChatOpenAI:
        print(f" 调试信息: LLM_PROVIDER = {settings.LLM_PROVIDER}")
        print(f" 调试信息: OPENAI_API_KEY = {settings.OPENAI_API_KEY}")
        print(f" 调试信息: OPENAI_BASE_URL = {settings.OPENAI_BASE_URL}")
        if self.provider == "qwen":
            return ChatOpenAI(
                model=settings.OPENAI_MODEL,
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL,
                temperature=0.7,
                max_tokens=2000
            )
        elif self.provider == "deepseek":
            return ChatOpenAI(
                model=settings.DEEPSEEK_MODEL,
                api_key=settings.DEEPSEEK_API_KEY,
                base_url=settings.DEEPSEEK_BASE_URL,
                temperature=0.7,
                max_tokens=2000
            )
        else:
            raise ValueError(f"不支持的 LLM 提供商：{self.provider}")
    
    async def agenerate(self, prompts: List[str]):
        logger.info(f"📡 LLMClient.agenerate 被调用，prompts 数量: {len(prompts)}")
        try:
            from langchain.schema import HumanMessage
            # agenerate expects List[List[BaseMessage]] - one message list per prompt
            message_lists = [[HumanMessage(content=prompt)] for prompt in prompts]
            logger.info(f"📡 调用 self.client.agenerate...")
            response = await self.client.agenerate(message_lists)
            logger.info(f" LLM 响应成功，类型: {type(response)}")
            return response
        except Exception as e:
            import traceback
            logger.error(f"❌ LLM 调用失败：{e}")
            logger.error(f"详细堆栈：{traceback.format_exc()}")
            raise


_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
