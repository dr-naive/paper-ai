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
        # 注意：qwen3.6-plus 等模型有 reasoning tokens，
        # 需要预留足够的 token 给实际输出内容
        if self.provider == "qwen":
            return ChatOpenAI(
                model=settings.OPENAI_MODEL,
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL,
                temperature=0.7,
                max_tokens=8000  # 增加 token 限制，为 reasoning tokens 预留空间
            )
        elif self.provider == "deepseek":
            return ChatOpenAI(
                model=settings.DEEPSEEK_MODEL,
                api_key=settings.DEEPSEEK_API_KEY,
                base_url=settings.DEEPSEEK_BASE_URL,
                temperature=0.7,
                max_tokens=8000  # 增加 token 限制，为 reasoning tokens 预留空间
            )
        else:
            raise ValueError(f"不支持的 LLM 提供商：{self.provider}")
    
    async def agenerate(self, prompts: List[str]):
        logger.info(f"📡 LLMClient.agenerate 被调用，prompts 数量: {len(prompts)}")
        try:
            # 使用 langchain_core 中的 HumanMessage（新版本 langchain 的正确导入方式）
            from langchain_core.messages import HumanMessage
            # agenerate expects List[List[BaseMessage]] - one message list per prompt
            message_lists = [[HumanMessage(content=prompt)] for prompt in prompts]
            logger.info(f"📡 调用 self.client.agenerate...")
            response = await self.client.agenerate(message_lists)
            logger.info(f" LLM 响应成功，类型: {type(response)}")
            
            if hasattr(response, 'generations'):
                logger.info(f"  generations 长度: {len(response.generations)}")
                for i, gen_list in enumerate(response.generations):
                    for j, gen in enumerate(gen_list):
                        logger.info(f"  生成 [{i}][{j}] 类型: {type(gen)}")
                        if hasattr(gen, 'text'):
                            text = getattr(gen, 'text', '')
                            logger.info(f"  文本内容长度: {len(text) if text else 0}")
                            logger.info(f"  文本内容完整值: {repr(text)}")
                        if hasattr(gen, 'message'):
                            msg = getattr(gen, 'message', None)
                            logger.info(f"  message 属性: {type(msg)}")
                            if msg and hasattr(msg, 'content'):
                                logger.info(f"  message.content: {repr(msg.content[:500]) if msg.content else '空'}")
            
            if hasattr(response, 'llm_output'):
                logger.info(f"  llm_output: {response.llm_output}")
            
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
