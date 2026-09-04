# Current Database Schema

Schema baseline revision: `0001_current_schema`.

## Identity and content

- `users`
- `papers`
- `sections`
- `document_elements`
- `tables`
- `table_structures`
- `table_cells`
- `images`
- `qa_pairs`
- `notes`
- `folders`

## Conversation and observability

- `chat_sessions`, optionally bound to a paper or research project
- `chat_messages`, legacy question/answer row format
- `summary_cache`
- `interpret_cache`
- `answer_traces`

## Research projects and artifacts

- `research_projects`
- `project_papers`, unique by project and paper
- `writing_artifacts`

The baseline deliberately preserves the physical types and constraints of the current ORM. Runtime V2, evidence, memory items, and writing documents are not part of this revision and must be introduced by later additive migrations.
