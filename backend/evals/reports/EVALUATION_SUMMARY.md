# PaperAI Retrieval Evaluation Summary

## Dataset

- Five papers covering Chinese/English, short/long documents, tables, methods, experiments, and cross-section questions.
- 30 generated candidates: 12 human-verified Gold cases, 12 Silver cases, and 6 Draft cases.
- Gold cases were split by paper rather than randomly by question.

## Results

| Run | Cases | Hit@5 | Evidence Recall@5 | Precision@5 | MRR | Table Hit@5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Dev baseline | 12 | 75.00% | 75.00% | 20.00% | 0.5694 | 100.00% |
| Dev after front-matter indexing | 12 | 100.00% | 100.00% | 31.67% | 0.8194 | 100.00% |
| Gold sealed test | 12 | 50.00% | 45.83% | 10.00% | 0.4444 | N/A |
| Post-fix regression | 12 | 91.67% | 87.50% | 21.67% | 0.7500 | N/A |

## Findings

The evaluation exposed two retrieval defects rather than a prompt-only problem:

1. Content before the first parsed section was not reliably indexed.
2. The legacy fallback `全文` section persisted only the first 3,000 characters, leaving later PDF pages outside the vector store.

The indexing pipeline now preserves bounded front matter and retains up to 100,000 characters when section parsing fails. Existing affected papers were repaired with page-level fallback chunks.

## Remaining Limitations

- The sealed Gold test score remains 50.00%. Because its failures were inspected and used for fixes, the post-fix 91.67% result is a regression score, not a new unbiased holdout score.
- `p05_q004` still misses the theorem-3 evidence at Top-5.
- `p05_q006` retrieves one of two required evidence spans, giving 50% evidence recall for that case.
- The dataset is intentionally small and demonstrates behavior on the selected corpus, not universal accuracy across arbitrary academic PDFs.

