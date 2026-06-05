"""RAG 论文知识库模块 - 终极修复版"""
from typing import List, Dict, Any, Optional
from langchain_core.embeddings import Embeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from app.config import settings
import logging
import os
import re
import httpx  # 使用 httpx 直接发请求，绕过 LangChain 的坑

logger = logging.getLogger(__name__)

# ==========================================
# 【核心杀招】：手写 Embeddings 类，直接调用百炼 API
# ==========================================
class DashScopeEmbeddings(Embeddings):
    def __init__(self, model: str, api_key: str, base_url: str):
        self.model = model
        self.api_key = api_key
        # 确保 base_url 末尾没有斜杠
        self.base_url = base_url.rstrip('/') 

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._call_api(texts)

    def embed_query(self, text: str) -> List[float]:
        return self._call_api([text])[0]

    def _call_api(self, texts: List[str]) -> List[List[float]]:
        # 1. 深度清洗数据
        clean_texts = []
        for t in texts:
            s = str(t).strip()
            s = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', s)
            if s and s != "None":
                clean_texts.append(s)
            else:
                clean_texts.append("") # 空值占位
        
        url = f"{self.base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # 初始化结果数组
        all_embeddings = [[] for _ in texts]
        
        # 【终极杀招】：batch_size = 1，逐个发送！彻底绕过百炼的批量限制和序列化 Bug
        for i, text in enumerate(clean_texts):
            if not text:
                continue # 跳过空文本
            
            payload = {
                "model": self.model,
                "input": text  # 注意：这里直接传字符串，不传数组！
            }
            
            try:
                response = httpx.post(url, headers=headers, json=payload, timeout=30.0)
                response.raise_for_status()
                result = response.json()
                all_embeddings[i] = result["data"][0]["embedding"]
            except Exception as e:
                logger.warning(f"⚠️ 单个文本向量化失败 (长度:{len(text)}), 已跳过: {str(e)[:100]}")
                all_embeddings[i] = [0.0] * 1536 # 失败则填充 0 向量
                
        return all_embeddings

# ==========================================
# 知识库主类
# ==========================================
class PaperKnowledgeBase:
    def __init__(self):
        # 使用我们手写的 DashScopeEmbeddings
        self.embeddings = DashScopeEmbeddings(
            model=settings.EMBEDDING_MODEL,
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL
        )
        self._vectorstore = None
    
    @property
    def vectorstore(self):
        if self._vectorstore is None:
            os.makedirs(settings.VECTOR_STORE_PATH, exist_ok=True)
            self._vectorstore = Chroma(
                collection_name="papers",
                embedding_function=self.embeddings,
                persist_directory=settings.VECTOR_STORE_PATH
            )
        return self._vectorstore
    
    async def add_paper_chunks(self, paper_id: str, chunks: List[Dict[str, Any]]) -> bool:
        try:
            docs = []
            for chunk in chunks:
                content = str(chunk.get('content', '')).strip()
                content = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', content)
                if not content or content == "None":
                    continue
                
                # 限制长度
                if len(content) > 2000:
                    content = content[:2000]

                docs.append(
                    Document(
                        page_content=content,
                        metadata={
                            "paper_id": str(paper_id),
                            "chunk_type": str(chunk.get('type') or 'text'),
                            "section": str(chunk.get('section') or ''),
                            "chunk_index": int(chunk.get('index') or 0)
                        }
                    )
                )
            
            if docs:
                # 批量添加（因为我们手写的 Embeddings 已经处理好了列表，Chroma 会正确调用）
                self.vectorstore.add_documents(docs)
                logger.info(f"✅ 成功添加 {len(docs)} 个片段到知识库 (paper_id: {paper_id})")
            return True
        except Exception as e:
            logger.error(f"❌ 添加论文片段失败：{e}")
            return False
    
    async def query(self, paper_id: str, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        try:
            results = self.vectorstore.similarity_search_with_score(
                query=query, k=top_k, filter={"paper_id": paper_id}
            )
            return [
                {
                    "content": doc.page_content,
                    "section": doc.metadata.get("section", ""),
                    "chunk_index": doc.metadata.get("chunk_index", 0),
                    "score": float(score)
                }
                for doc, score in results
            ]
        except Exception as e:
            logger.error(f"❌ 查询失败：{e}")
            return []
    
    async def delete_paper(self, paper_id: str) -> bool:
        try:
            self.vectorstore.delete(filter={"paper_id": paper_id})
            return True
        except Exception as e:
            logger.error(f"❌ 删除失败：{e}")
            return False

_knowledge_base: Optional[PaperKnowledgeBase] = None
def get_knowledge_base() -> PaperKnowledgeBase:
    global _knowledge_base
    if _knowledge_base is None:
        _knowledge_base = PaperKnowledgeBase()
    return _knowledge_base