"""Run an online hybrid-retrieval smoke check for one paper."""

from __future__ import annotations

import argparse
import asyncio
import json

from app.database import AsyncSessionLocal, close_db
# Load all relationship targets before SQLAlchemy configures mappers.
from app.models.chat import ChatMessage, ChatSession, InterpretCache, SummaryCache  # noqa: F401
from app.models.user import User  # noqa: F401
from app.rag.hybrid_retrieval import HybridPaperRetriever


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--paper-id", required=True)
    parser.add_argument("--query", required=True)
    args = parser.parse_args()
    try:
        async with AsyncSessionLocal() as db:
            result = await HybridPaperRetriever(db).retrieve(
                args.paper_id, args.query
            )
            print(json.dumps({
                "query": result.standalone_question,
                "top_k": result.top_k,
                "second_pass": result.second_pass,
                "results": [{
                    "type": item.get("chunk_type"),
                    "page": item.get("page"),
                    "table": item.get("table_number"),
                    "content": str(item.get("content") or "")[:180],
                } for item in result.chunks],
            }, ensure_ascii=False))
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
