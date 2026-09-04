"""Academic search provider adapters."""

from .arxiv import ArxivAcademicSearchProvider
from .base import (
    AcademicSearchAuthenticationError,
    AcademicSearchMalformedResponseError,
    AcademicSearchProvider,
    AcademicSearchProviderError,
    AcademicSearchRateLimitError,
    AcademicSearchTimeoutError,
)
from .crossref import CrossrefMetadataProvider
from .semantic_scholar import SemanticScholarAcademicSearchProvider

__all__ = [
    "AcademicSearchAuthenticationError",
    "AcademicSearchMalformedResponseError",
    "AcademicSearchProvider",
    "AcademicSearchProviderError",
    "AcademicSearchRateLimitError",
    "AcademicSearchTimeoutError",
    "ArxivAcademicSearchProvider",
    "CrossrefMetadataProvider",
    "SemanticScholarAcademicSearchProvider",
]
