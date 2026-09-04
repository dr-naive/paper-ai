"""Safe remote-paper intake for allowlisted scholarly sources."""
from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx


ARXIV_ID_PATTERN = re.compile(r"^(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?$", re.IGNORECASE)
ARXIV_ALLOWED_HOSTS = {"arxiv.org", "export.arxiv.org"}


class RemotePaperImportError(RuntimeError):
    pass


@dataclass(frozen=True)
class RemotePaperDownload:
    arxiv_id: str
    pdf_url: str
    file_path: str
    file_size: int
    file_sha256: str


def normalize_arxiv_id(value: str) -> str:
    candidate = str(value or "").strip()
    candidate = re.sub(r"^https?://(?:export\.)?arxiv\.org/(?:abs|pdf)/", "", candidate, flags=re.IGNORECASE)
    candidate = re.sub(r"\.pdf$", "", candidate, flags=re.IGNORECASE)
    if not ARXIV_ID_PATTERN.fullmatch(candidate):
        raise ValueError("arxiv_id 格式无效")
    return candidate


async def download_arxiv_pdf(
    arxiv_id: str,
    *,
    paper_id: str,
    storage_path: str,
    max_size: int,
    timeout_seconds: float = 45.0,
) -> RemotePaperDownload:
    """Download one arXiv PDF with strict identifier, host, type, and size checks."""
    normalized = normalize_arxiv_id(arxiv_id)
    url = f"https://export.arxiv.org/pdf/{normalized}"
    os.makedirs(storage_path, exist_ok=True)
    final_path = os.path.join(storage_path, f"{paper_id}.pdf")
    partial_path = final_path + ".part"
    digest = hashlib.sha256()
    total = 0
    prefix = b""
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
            async with client.stream("GET", url, headers={"User-Agent": "PaperAI/1.0 scholarly-import"}) as response:
                response.raise_for_status()
                host = (urlparse(str(response.url)).hostname or "").lower()
                if host not in ARXIV_ALLOWED_HOSTS:
                    raise RemotePaperImportError("arXiv 下载被重定向到非允许域名")
                declared = int(response.headers.get("content-length") or 0)
                if declared and declared > max_size:
                    raise RemotePaperImportError("远程 PDF 超过上传大小限制")
                with open(partial_path, "wb") as target:
                    async for chunk in response.aiter_bytes(1024 * 256):
                        total += len(chunk)
                        if total > max_size:
                            raise RemotePaperImportError("远程 PDF 超过上传大小限制")
                        if len(prefix) < 5:
                            prefix += chunk[: 5 - len(prefix)]
                        digest.update(chunk)
                        target.write(chunk)
        if prefix != b"%PDF-":
            raise RemotePaperImportError("远程响应不是有效 PDF")
        os.replace(partial_path, final_path)
        return RemotePaperDownload(normalized, url, final_path, total, digest.hexdigest())
    except Exception:
        for path in (partial_path, final_path):
            if os.path.exists(path):
                os.remove(path)
        raise
