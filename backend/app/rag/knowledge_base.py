"""RAG 论文知识库模块 - 优化版（智能分块）"""
from typing import List, Dict, Any, Optional, Tuple
from langchain_core.embeddings import Embeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from app.config import settings
import json
import logging
import os
import re
import httpx
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# 禁用 nltk 下载，使用纯 Python 正则实现分词
# nltk 数据下载在受限环境中不可行，采用纯正则方案


# ==========================================
# 智能分块器
# ==========================================
@dataclass
class ChunkConfig:
    """分块配置"""
    # 小chunk配置（用于精确检索）
    small_chunk_size: int = 400
    small_chunk_overlap: int = 100
    # 大chunk配置（用于提供上下文）
    large_chunk_size: int = 1200
    large_chunk_overlap: int = 200
    # 滑动窗口重叠比例
    overlap_ratio: float = 0.2


class SmartChunker:
    """智能分块器：语义分块 + 滑动窗口 + 层级分块"""
    
    def __init__(self, config: Optional[ChunkConfig] = None):
        self.config = config or ChunkConfig()
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """将文本分割成句子（语义边界）- 纯正则实现，不依赖 nltk"""
        # 使用正则表达式进行句子分割
        # 匹配：句号、问号、感叹号后面跟着空格或换行
        sentence_pattern = r'(?<=[。！？.!?])\s+'
        sentences = re.split(sentence_pattern, text)
        
        # 过滤空句子并清理
        sentences = [s.strip() for s in sentences if s.strip()]
        
        # 如果分割效果不好（只有一个大句子），尝试按段落分割
        if len(sentences) <= 1 and len(text) > 200:
            # 尝试按换行符分割
            sentences = re.split(r'\n+', text)
            sentences = [s.strip() for s in sentences if s.strip()]
            
            # 如果还是不行，按固定长度分割
            if len(sentences) <= 1 and len(text) > 500:
                chunk_size = 200
                sentences = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
        
        return sentences
    
    def _split_into_paragraphs(self, text: str) -> List[str]:
        """将文本分割成段落"""
        # 按双换行符分割
        paragraphs = re.split(r'\n\s*\n', text)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        return paragraphs
    
    def _merge_sentences_to_chunk(
        self, 
        sentences: List[str], 
        target_size: int,
        overlap: int = 0
    ) -> List[Tuple[str, int, int]]:
        """
        将句子合并成指定大小的chunk
        返回: List[(chunk_text, start_sentence_idx, end_sentence_idx)]
        """
        chunks = []
        current_chunk = []
        current_size = 0
        start_idx = 0
        
        for i, sentence in enumerate(sentences):
            sentence_len = len(sentence)
            
            # 如果当前chunk为空，直接添加
            if not current_chunk:
                current_chunk.append(sentence)
                current_size = sentence_len
                start_idx = i
            # 如果添加后不超过目标大小，继续添加
            elif current_size + sentence_len + 1 <= target_size:
                current_chunk.append(sentence)
                current_size += sentence_len + 1
            else:
                # 保存当前chunk
                chunk_text = ' '.join(current_chunk) if self._is_english(' '.join(current_chunk)) else ''.join(current_chunk)
                chunks.append((chunk_text, start_idx, i))
                
                # 计算重叠：保留最后几个句子
                if overlap > 0:
                    overlap_sentences = []
                    overlap_size = 0
                    for j in range(len(current_chunk) - 1, -1, -1):
                        if overlap_size + len(current_chunk[j]) <= overlap:
                            overlap_sentences.insert(0, current_chunk[j])
                            overlap_size += len(current_chunk[j])
                        else:
                            break
                    current_chunk = overlap_sentences + [sentence]
                    current_size = sum(len(s) for s in current_chunk)
                    start_idx = i - len(overlap_sentences)
                else:
                    current_chunk = [sentence]
                    current_size = sentence_len
                    start_idx = i
        
        # 添加最后一个chunk
        if current_chunk:
            chunk_text = ' '.join(current_chunk) if self._is_english(' '.join(current_chunk)) else ''.join(current_chunk)
            chunks.append((chunk_text, start_idx, len(sentences)))
        
        return chunks
    
    def _is_english(self, text: str) -> bool:
        """判断文本是否主要是英文"""
        english_chars = sum(1 for c in text if c.isascii() and c.isalpha())
        total_alpha = sum(1 for c in text if c.isalpha())
        if total_alpha == 0:
            return False
        return english_chars / total_alpha > 0.7
    
    def chunk_text(
        self, 
        text: str, 
        section_title: str = "",
        chunk_type: str = "text"
    ) -> List[Dict[str, Any]]:
        """
        智能分块：语义分块 + 滑动窗口 + 层级分块
        
        返回结构:
        [
            {
                "content": "chunk内容",
                "type": "small/large",
                "section": "章节标题",
                "index": 索引,
                "parent_index": 父chunk索引（仅small chunk有）
            }
        ]
        """
        if not text or not text.strip():
            return []
        
        # 清理文本
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        text = text.strip()
        
        # 分割成句子
        sentences = self._split_into_sentences(text)
        
        if not sentences:
            return []
        
        chunks = []
        chunk_idx = 0
        
        # 1. 生成大chunks（父文档）
        large_chunks = self._merge_sentences_to_chunk(
            sentences,
            self.config.large_chunk_size,
            self.config.large_chunk_overlap
        )
        
        # 2. 为每个大chunk生成小chunks（子文档）
        for parent_idx, (large_text, start_sent, end_sent) in enumerate(large_chunks):
            parent_chunk_index = chunk_idx
            # 添加大chunk
            chunks.append({
                "content": large_text,
                "type": "large",
                "section": section_title,
                "index": chunk_idx,
                "sentence_range": (start_sent, end_sent)
            })
            chunk_idx += 1
            
            # 获取这个大chunk内的句子
            sub_sentences = sentences[start_sent:end_sent]
            
            # 生成小chunks
            small_chunks = self._merge_sentences_to_chunk(
                sub_sentences,
                self.config.small_chunk_size,
                self.config.small_chunk_overlap
            )
            
            for small_text, small_start, small_end in small_chunks:
                # 计算在原文中的句子索引
                actual_start = start_sent + small_start
                actual_end = start_sent + small_end
                
                chunks.append({
                    "content": small_text,
                    "type": "small",
                    "section": section_title,
                    "index": chunk_idx,
                    "parent_index": parent_chunk_index,  # 关联父chunk的真实chunk_index
                    "sentence_range": (actual_start, actual_end)
                })
                chunk_idx += 1
        
        return chunks
    
    def chunk_section(
        self,
        section_title: str,
        section_content: str,
        existing_chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """处理单个章节的分块"""
        new_chunks = self.chunk_text(section_content, section_title)
        
        # 重新编号
        start_idx = len(existing_chunks)
        for chunk in new_chunks:
            chunk["index"] = start_idx
            if "parent_index" in chunk:
                chunk["parent_index"] += start_idx
            start_idx += 1
        
        return existing_chunks + new_chunks

# ==========================================
# 【核心杀招】：手写 Embeddings 类，直接调用百炼 API
# ==========================================
class DashScopeEmbeddings(Embeddings):
    def __init__(self, model: str, api_key: str, base_url: str):
        self.model = model
        self.api_key = api_key
        # 确保 base_url 末尾没有斜杠
        self.base_url = base_url.rstrip('/') 
        # PaperAI intentionally keeps one stable Chroma dimension. Both the
        # previous text-embedding-v3 model and qwen3.7-text-embedding support
        # 1024 dimensions, but their vector spaces must never be mixed.
        self.dimensions = 1024

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
        
        # 初始化结果数组；兼容接口支持数组输入，批量请求显著降低建库耗时。
        all_embeddings = [[] for _ in texts]
        batch_size = 10
        for start in range(0, len(clean_texts), batch_size):
            indexed = [
                (index, clean_texts[index])
                for index in range(start, min(start + batch_size, len(clean_texts)))
                if clean_texts[index]
            ]
            if not indexed:
                continue
            payload = {
                "model": self.model,
                "input": [text for _index, text in indexed],
                "dimensions": self.dimensions,
                "encoding_format": "float",
            }
            try:
                response = httpx.post(url, headers=headers, json=payload, timeout=60.0)
                response.raise_for_status()
                result = response.json()
                data = sorted(result.get("data") or [], key=lambda item: item.get("index", 0))
                if len(data) != len(indexed) or any("embedding" not in item for item in data):
                    raise RuntimeError("Embedding 响应缺少向量数据")
                for (original_index, _text), item in zip(indexed, data):
                    all_embeddings[original_index] = item["embedding"]
            except Exception as e:
                logger.error(
                    "Embedding 失败 model=%s batch=%d error=%s",
                    self.model,
                    len(indexed),
                    str(e)[:160],
                )
                raise RuntimeError(f"Embedding 模型调用失败: {self.model}") from e

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
        """添加论文片段到知识库，支持层级分块"""
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

                # 构建metadata，包含层级信息
                metadata = {
                    "paper_id": str(paper_id),
                    "chunk_type": str(chunk.get('type') or 'text'),  # small 或 large
                    "section": str(chunk.get('section') or ''),
                    "chunk_index": int(chunk.get('index') or 0)
                }

                if chunk.get("page") is not None:
                    metadata["page"] = int(chunk["page"])
                if chunk.get("caption"):
                    metadata["caption"] = str(chunk["caption"])
                if chunk.get("table_number") is not None:
                    metadata["table_number"] = str(chunk["table_number"])
                if chunk.get("table_id"):
                    metadata["table_id"] = str(chunk["table_id"])
                if chunk.get("row_index") is not None:
                    metadata["row_index"] = int(chunk["row_index"])
                if chunk.get("fields"):
                    metadata["fields_json"] = json.dumps(chunk["fields"], ensure_ascii=False)
                if chunk.get("coverage_source"):
                    metadata["coverage_source"] = str(chunk["coverage_source"])
                if chunk.get("element_id"):
                    metadata["element_id"] = str(chunk["element_id"])
                if chunk.get("section_id"):
                    metadata["section_id"] = str(chunk["section_id"])
                if chunk.get("element_type"):
                    metadata["element_type"] = str(chunk["element_type"])
                if chunk.get("bbox"):
                    metadata["bbox_json"] = json.dumps(chunk["bbox"])
                if chunk.get("section_path"):
                    metadata["section_path_json"] = json.dumps(
                        chunk["section_path"],
                        ensure_ascii=False,
                    )
                if chunk.get("layout_confidence") is not None:
                    metadata["layout_confidence"] = float(chunk["layout_confidence"])
                
                # 如果是表格内容，提取表格编号
                if "【表格】" in content or "table" in content.lower():
                    # 匹配"表1"、"表1："、"Table 1"、"Table 1:"等格式
                    table_match = re.search(r'(?:表|Table)\s*(\d+)', content, re.IGNORECASE)
                    if table_match and "table_number" not in metadata:
                        metadata["table_number"] = table_match.group(1)
                
                # 如果是small chunk，存储parent_index用于层级检索
                if chunk.get('parent_index') is not None:
                    metadata["parent_index"] = int(chunk.get('parent_index'))

                docs.append(Document(page_content=content, metadata=metadata))
            
            if docs:
                self.vectorstore.add_documents(docs)
                logger.info(f"✅ 成功添加 {len(docs)} 个片段到知识库 (paper_id: {paper_id})")
            return True
        except Exception as e:
            logger.error(f"❌ 添加论文片段失败：{e}")
            return False
    
    async def query(
        self, 
        paper_id: str, 
        query: str, 
        top_k: int = 5,
        include_parent_context: bool = True
    ) -> List[Dict[str, Any]]:
        """
        查询知识库，支持层级检索
        
        Args:
            paper_id: 论文ID
            query: 查询文本
            top_k: 返回结果数量
            include_parent_context: 是否包含父chunk上下文（层级检索）
        
        Returns:
            检索结果列表
        """
        try:
            import time
            started_at = time.perf_counter()
            # 边界检查：空查询或无效top_k
            if not query or not query.strip():
                logger.warning("查询文本为空，返回空结果")
                return []
            
            if top_k <= 0:
                logger.warning(f"top_k={top_k} 无效，返回空结果")
                return []
            
            retrieval_filter = {
                "$and": [
                    {"paper_id": paper_id},
                    {
                        "$or": [
                            {"chunk_type": "small"},
                            {"chunk_type": "table"},
                            {"chunk_type": "table_row"},
                            {"chunk_type": "image"},
                        ]
                    },
                ]
            }

            try:
                filtered_results = self.vectorstore.similarity_search_with_score(
                    query=query, k=top_k * 8, filter=retrieval_filter
                )
            except TypeError:
                results = self.vectorstore.similarity_search_with_score(
                    query=query, k=top_k * 8
                )
                filtered_results = [
                    (doc, score) for doc, score in results
                    if doc.metadata.get("paper_id") == paper_id
                    and doc.metadata.get("chunk_type") in {"small", "table", "table_row", "image"}
                ]
            
            # 检查查询是否包含表格编号（如"表1"、"Table 1"），如果有则优先返回匹配的表格
            table_number_query = None
            table_match = re.search(r'(?:表|Table)\s*(\d+)', query, re.IGNORECASE)
            if table_match:
                table_number_query = table_match.group(1)
            
            # 如果查询包含表格编号，优先返回匹配的表格
            table_priority_results = []
            other_results = []
            for doc, score in filtered_results:
                table_number = re.sub(r"\D", "", str(doc.metadata.get("table_number", "")))
                if table_number_query and table_number == table_number_query:
                    table_priority_results.append((doc, score))
                else:
                    other_results.append((doc, score))
            
            # 优先结果在前，其他结果在后，并做轻量重排
            filtered_results = self._rerank_results(query, table_priority_results + other_results)
            
            small_chunks = [(doc, score) for doc, score in filtered_results 
                           if doc.metadata.get("chunk_type") == "small"]
            table_chunks = [(doc, score) for doc, score in filtered_results
                            if doc.metadata.get("chunk_type") in {"table", "table_row"}]
            image_chunks = [(doc, score) for doc, score in filtered_results
                            if doc.metadata.get("chunk_type") == "image"]

            table_intent = bool(re.search(r"表格|(?:表|table)\s*\d+", query, re.IGNORECASE))
            image_intent = bool(re.search(r"图片|图像|插图|(?:图|figure)\s*\d+", query, re.IGNORECASE))

            ordered_groups = [small_chunks, table_chunks, image_chunks]
            if table_intent:
                ordered_groups = [table_chunks, small_chunks, image_chunks]
            elif image_intent:
                ordered_groups = [image_chunks, small_chunks, table_chunks]
            
            final_results = []
            for group in ordered_groups:
                for item in group:
                    if len(final_results) >= top_k:
                        break
                    final_results.append(item)
            
            seen_indices = set()
            unique_results = []
            for doc, score in final_results:
                result_key = (
                    doc.metadata.get("chunk_type"),
                    doc.metadata.get("chunk_index"),
                    doc.metadata.get("section"),
                )
                if result_key not in seen_indices:
                    seen_indices.add(result_key)
                    unique_results.append((doc, score))
            
            output = []
            for doc, score in unique_results[:top_k]:
                result = {
                    "content": doc.page_content,
                    "section": doc.metadata.get("section", ""),
                    "chunk_index": doc.metadata.get("chunk_index", 0),
                    "chunk_type": doc.metadata.get("chunk_type", "text"),
                    "score": float(score)
                }
                for field in (
                    "table_number",
                    "caption",
                    "page",
                    "element_id",
                    "section_id",
                    "element_type",
                    "layout_confidence",
                    "table_id",
                    "row_index",
                ):
                    if doc.metadata.get(field) is not None:
                        result[field] = doc.metadata[field]
                for metadata_field, result_field in (
                    ("bbox_json", "bbox"),
                    ("section_path_json", "section_path"),
                    ("fields_json", "fields"),
                ):
                    if doc.metadata.get(metadata_field):
                        try:
                            result[result_field] = json.loads(doc.metadata[metadata_field])
                        except (TypeError, json.JSONDecodeError):
                            logger.warning(
                                "忽略损坏的版面元数据 field=%s chunk=%s",
                                metadata_field,
                                doc.metadata.get("chunk_index"),
                            )
                
                if include_parent_context and doc.metadata.get("chunk_type") == "small":
                    parent_idx = doc.metadata.get("parent_index")
                    if parent_idx is not None:
                        parent_content = await self._get_parent_chunk(paper_id, parent_idx)
                        if parent_content:
                            result["parent_context"] = parent_content
                
                output.append(result)
            
            logger.info(
                "知识库检索完成 paper_id=%s query=%r candidates=%d returned=%d cost=%.2fs",
                paper_id, query[:80], len(filtered_results), len(output), time.perf_counter() - started_at
            )
            return output
        except Exception as e:
            logger.error(f"❌ 查询失败：{e}")
            return []

    def _rerank_results(self, query: str, results: List[Tuple[Document, float]]) -> List[Tuple[Document, float]]:
        """轻量规则重排：向量距离为主，关键词/章节/表格命中加分。"""
        query_l = query.lower()
        terms = [t for t in re.findall(r"[\w\u4e00-\u9fff]+", query_l) if len(t) >= 2]

        def lexical_bonus(doc: Document) -> float:
            content = doc.page_content.lower()
            section = str(doc.metadata.get("section", "")).lower()
            bonus = 0.0
            for term in terms:
                if term in content:
                    bonus += 0.08
                if term in section:
                    bonus += 0.12
            if doc.metadata.get("chunk_type") == "small":
                bonus += 0.03
            if doc.metadata.get("table_number"):
                bonus += 0.05
                query_table = re.search(r"(?:表|table)\s*(\d+)", query_l, re.IGNORECASE)
                document_table = re.sub(r"\D", "", str(doc.metadata.get("table_number", "")))
                if query_table and query_table.group(1) == document_table:
                    bonus += 0.5
            return min(bonus, 0.6)

        return sorted(results, key=lambda item: float(item[1]) - lexical_bonus(item[0]))
    
    async def _get_parent_chunk(self, paper_id: str, parent_index: int) -> Optional[str]:
        """获取父chunk内容（用于层级检索）"""
        try:
            all_docs = self.vectorstore._collection.get(
                where={
                    "$and": [
                        {"paper_id": paper_id},
                        {"chunk_type": "large"},
                        {"chunk_index": parent_index}
                    ]
                }
            )
            if all_docs and all_docs["documents"]:
                return all_docs["documents"][0]
        except Exception as e:
            logger.warning(f"获取父chunk失败: {e}")
        return None
    
    async def delete_paper(self, paper_id: str) -> bool:
        try:
            all_docs = self.vectorstore._collection.get(where={"paper_id": paper_id})
            if all_docs and all_docs["ids"]:
                self.vectorstore._collection.delete(ids=all_docs["ids"])
            return True
        except Exception as e:
            logger.error(f"❌ 删除失败：{e}")
            return False

    async def delete_paper_media(self, paper_id: str) -> bool:
        """Delete only derived table/image chunks before an idempotent media retry."""
        try:
            all_docs = self.vectorstore._collection.get(
                where={
                    "$and": [
                        {"paper_id": str(paper_id)},
                        {"chunk_type": {"$in": ["table", "table_row", "image"]}},
                    ]
                }
            )
            if all_docs and all_docs["ids"]:
                self.vectorstore._collection.delete(ids=all_docs["ids"])
            return True
        except Exception as e:
            logger.error("❌ 删除论文图表片段失败：%s", e)
            return False

_knowledge_base: Optional[PaperKnowledgeBase] = None
def get_knowledge_base() -> PaperKnowledgeBase:
    global _knowledge_base
    if _knowledge_base is None:
        _knowledge_base = PaperKnowledgeBase()
    return _knowledge_base
