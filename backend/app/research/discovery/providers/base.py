"""Provider protocol and deterministic provider-error types."""
from __future__ import annotations

from typing import Protocol

from ..schemas import ProviderCapabilities, ProviderPaperDTO, SearchFiltersDTO


class AcademicSearchProvider(Protocol):
    name: str

    def capabilities(self) -> ProviderCapabilities:
        """Return explicit support instead of assuming every provider accepts every filter."""
        ...

    async def search(
        self,
        query: str,
        filters: SearchFiltersDTO,
        limit: int,
    ) -> list[ProviderPaperDTO]:
        """Run one atomic provider search without workflow planning or persistence."""
        ...


class AcademicSearchProviderError(RuntimeError):
    """Base error safe for application-layer mapping in Block 2B."""


class AcademicSearchAuthenticationError(AcademicSearchProviderError):
    pass


class AcademicSearchRateLimitError(AcademicSearchProviderError):
    def __init__(self, message: str, *, retry_after_seconds: float | None = None):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class AcademicSearchTimeoutError(AcademicSearchProviderError):
    pass


class AcademicSearchMalformedResponseError(AcademicSearchProviderError):
    pass
