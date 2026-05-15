## Agent skills

### Issue tracker

Issues and PRDs live as markdown files under `.scratch/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Use the canonical status strings `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, and `wontfix` in issue `Status:` lines. See `docs/agents/triage-labels.md`.

### Domain docs

Treat this as a single-context repo and read `CONTEXT.md` and `docs/adr/` if they exist. See `docs/agents/domain.md`.

## Project Context

`安牛（AnNiu）` is a safety-focused knowledge base assistant for turning uploaded documents into structured Wiki content, then using that content for Q&A, retrieval, and training-material generation.

The current codebase is a `FastAPI` backend plus a `React 18 + TypeScript + Vite + Tailwind/shadcn` frontend. Do not assume the older Tauri/Vue plan in `docs/DEVELOPMENT-PLAN.md` reflects the current implementation. Treat it as legacy context unless the code has clearly caught up.

### Core product areas

- Multi-knowledge-base management
- Document upload, storage, and tracking
- LLM-driven Wiki generation from source documents
- Knowledge-base Q&A with citations
- Original-document keyword search with highlights
- Wiki quality checks / linting
- Training outline and PPT generation
- Model provider and model-role configuration

### Source of truth order

When information conflicts, prefer:

1. The current code
2. `readme.md`
3. `docs/product-requirements.md`
4. `docs/DEVELOPMENT-PLAN.md` only if it still matches the code

## Repo Layout

### Backend

- `backend/app.py` is the API entrypoint.
- `backend/config.py` stores the runtime config file in `~/.anniu/config.json` and defines the knowledge-base/output directories.
- `backend/models.py` contains the shared Pydantic schema for config, knowledge bases, documents, wiki pages, chat, search, and training.
- `backend/services/` holds the main business logic:
  - `knowledge_base.py` creates, lists, deletes, and stats knowledge bases.
  - `document.py` uploads, tracks, deletes, and previews document deletion.
  - `wiki.py` generates Wiki pages, index/log files, and lint checks.
  - `chat.py` answers from Wiki when one or more knowledge bases are selected (`QA_PROMPT` + retrieved pages; empty retrieval still uses KB mode). When **no** knowledge base is selected, it uses web search (if enabled) or a general-domain LLM path. Relevance scoring uses only keywords with **length ≥ 3 characters**; 2-character terms are excluded from scoring to reduce spurious matches. Score contributions: title +4, summary +2, body +1, heading +0.5; pages with score 0 are omitted from the injected excerpts.
  - `search.py` performs original-document search with snippets and highlights.
  - `training.py` generates outlines and PPTX files.
  - `llm.py` wraps model-provider access.
  - `text_extraction.py` extracts text/pages from supported documents.
- `backend/prompts/AGENTS.md` is the system-style instruction set for Wiki generation. Keep it aligned with the repo’s actual Wiki rules.

### Frontend

- `frontend/src/main.tsx` boots the app.
- `frontend/src/app/App.tsx` wires the main pages and reader overlay.
- `frontend/src/app/components/pages/` contains the primary views:
  - Chat
  - Assistant
  - Search
  - Knowledge Base
  - Training
  - Settings
- `frontend/src/lib/context.tsx` syncs app-wide knowledge-base/model state from the backend.
- `frontend/src/lib/api.ts` is the fetch layer for the FastAPI endpoints.
- `frontend/src/lib/types.ts` mirrors the backend models.

### Data directories

- `knowledge-bases/<kb_id>/raw/` stores original uploads.
- `knowledge-bases/<kb_id>/wiki/` stores generated wiki pages, including `index.md` and `log.md`.
- `knowledge-bases/<kb_id>/meta.json` stores knowledge-base metadata.
- `knowledge-bases/<kb_id>/raw/文档追踪.json` tracks uploaded documents, parse status, page counts, and linked wiki pages.
- `output/` stores generated artifacts such as PPTX files.
- `data/wiki/` and `data/raw/` contain sample/reference content.

## Workflow Rules

### Read before editing

- Inspect the current implementation before changing behavior.
- Prefer `rg` over `grep` for searching and `rg --files` for file discovery.
- If a task touches Wiki generation, read both the backend service and `backend/prompts/AGENTS.md` so the prompt contract and the implementation stay consistent.

### Preserve data contracts

- Keep `backend/models.py` and `frontend/src/lib/types.ts` in sync when changing API shapes.
- Preserve knowledge-base metadata, document tracking, and wiki traceability fields unless the task explicitly changes them.
- Do not invent sources, thresholds, procedures, or citations in generated Wiki content.

### Preserve current UI language

- The current UI is a light, card-based, indigo-accented workspace.
- Favor the existing visual language: white surfaces, slate backgrounds, rounded cards, restrained shadows, and clear spacing.
- Avoid changing layout patterns unless the task explicitly asks for a redesign.
- Keep shared message controls consistent between the Chat and Assistant pages. If you add or change copy/export/delete/regenerate behavior in one place, mirror it in the other page unless the user explicitly asks for a divergence.

### Handle file mutations carefully

- Generated content should stay inside the appropriate knowledge-base or output directory.
- When deleting documents, preserve the delete-preview and wiki-link cleanup behavior unless the task says otherwise.
- Avoid touching sample data under `data/` unless the request is about fixtures or examples.

## API Surface

The backend currently exposes endpoints for:

- Global config and current knowledge-base/model selection
- Knowledge-base CRUD
- Document upload, list, content extraction, highlights, and deletion previews
- Wiki page listing, page loading, document parsing, and linting
- Chat in streaming and sync modes
- Search
- Training outline generation, PPT generation, and downloads

If you add or rename an endpoint, update the frontend client and any affected types together.

## Development Notes

- `backend/app.py` defaults to `http://localhost:8000`.
- The frontend expects the backend at `http://localhost:8000`.
- The app uses local storage for some chat/session UI state, so behavior may be stateful between reloads.
- Existing automated tests live under `backend/tests/`; add or update tests when changing backend behavior.

## When using LLM outputs

- Wiki generation must return a valid JSON array only, with each item containing `file` and `content`.
- Keep `wiki/index.md` and `wiki/log.md` reserved.
- Prefer a small number of high-value wiki pages over many thin pages.
- Answers from chat should stay grounded in the wiki and clearly state when the knowledge base does not contain enough information.
- Chat and Assistant responses should avoid user-visible truncation. If the upstream model stops because of length, the backend should continue the answer rather than surfacing a half-finished reply.
- When modifying `chat.py` relevance scoring, keep the **keyword length ≥ 3** rule intact for the KB retrieval path. Loosening it to include 2-character terms tends to match almost every page in a safety-domain KB and dilutes the excerpts sent to the model.

## Chat routing (knowledge base vs open)

`ChatService.ask()` in `backend/services/chat.py`:

- **At least one `knowledge_base_ids`**: always wiki-backed Q&A (`QA_PROMPT` with index + any scored pages; `use_web_search` is ignored for routing).
- **No `knowledge_base_ids`**: if `use_web_search` and web results exist → web-grounded answer; otherwise → general LLM (`_build_general_messages`).

Retrieval helpers are covered in `backend/tests/test_chat_kb_retrieval.py`; web selection and no-KB flows in `backend/tests/test_chat_service_web_search.py`.
