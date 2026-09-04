"""Academic literature discovery foundations."""

from .normalize import deduplicate_results, normalize_provider_paper
from .schemas import (
    PaperSearchResultDTO,
    ProviderCapabilities,
    ProviderPaperDTO,
    SearchFiltersDTO,
    SearchIntentDTO,
    SearchPlanDTO,
)

__all__ = [
    "PaperSearchResultDTO",
    "ProviderCapabilities",
    "ProviderPaperDTO",
    "SearchFiltersDTO",
    "SearchIntentDTO",
    "SearchPlanDTO",
    "deduplicate_results",
    "normalize_provider_paper",
]
