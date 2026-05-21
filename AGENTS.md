## Agent skills

### Issue tracker

Issues and PRDs live as markdown files under `.scratch/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Use the canonical status strings `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, and `wontfix` in issue `Status:` lines. See `docs/agents/triage-labels.md`.

### Domain docs

Treat this as a single-context repo and read `CONTEXT.md` and `docs/adr/` if they exist. See `docs/agents/domain.md`.

## Project Context

`安牛（AnNiu）` is a safety-focused knowledge base assistant for turning uploaded documents into structured Wiki content, then using that content for Q&A, retrieval, and training-material generation. It is developed by 杭州了安科技有限公司 as a public-interest safety project.

The current codebase is a **FastAPI** backend plus a **React 18 + TypeScript + Vite + Tailwind/shadcn** frontend. Do not assume the older Tauri/Vue plan in `docs/DEVELOPMENT-PLAN.md` reflects the current implementation. Treat it as legacy context unless the code has clearly caught up.

### Core product areas

- Multi-knowledge-base management (CRUD, rename, stats)
- Document upload, storage, and tracking (PDF/DOCX/DOC/TXT/MD)
- LLM-driven Wiki generation from source documents (parallel pipeline)
- Knowledge-base Q&A with citations (always KB-grounded when KB is selected)
- Original-document keyword search with highlights and page numbers
- Wiki quality checks / linting (errors, warnings, hints)
- Training outline, PPTX, and standalone HTML generation
- Preset assistant definitions with custom system prompts + prompt optimization
- Model provider and model-role configuration (3 presets: DeepSeek, SiliconFlow, 阿里云百炼)
- Built-in document reader with highlights
- Chat message export to DOCX
- About page with version info and update check

### Source of truth order

When information conflicts, prefer:

1. The current code
2. `readme.md`
3. `docs/product-requirements.md`
4. `docs/DEVELOPMENT-PLAN.md` only if it still matches the code

## Repo Layout

### Backend

- `backend/app.py` — API entrypoint with all routes.
- `backend/config.py` — Runtime config file in `~/.anniu/config.json`; defines knowledge-base/output directories.
- `backend/models.py` — Shared Pydantic v2 schema for config, knowledge bases, documents, wiki pages, chat, search, and training.
- `backend/logging_config.py` — Logging configuration.
- `backend/services/` — Business logic layer:
  - `knowledge_base.py` — KB CRUD, rename, stats.
  - `document.py` — Upload, track, delete, delete-preview.
  - `wiki.py` — Wiki page generation (parallel pipeline), index/log files, lint checks.
  - `chat.py` — Q&A engine. When one or more KBs selected: always wiki-backed (`QA_PROMPT` + retrieved pages; empty retrieval still uses KB mode). When **no** KB selected: web search (if enabled) or general LLM. Relevance scoring uses only keywords with **length ≥ 3 characters**; 2-character terms excluded. Score: title +4, summary +2, body +1, heading +0.5.
  - `search.py` — Original-document keyword search with snippet highlights.
  - `llm.py` — OpenAI-compatible LLM provider wrapper.
  - `text_extraction.py` — PDF/DOCX/DOC/TXT/MD text/page extraction.
  - `training_html.py` — Standalone HTML training material generation.
  - `training_ppt.py` — PPTX training generation.
  - `training_downloads.py` — File download resolution.
  - `message_export.py` — Export chat messages to DOCX.
  - `assistant_prompt.py` — LLM-driven assistant prompt optimization.
  - `presentation/` — Training generation subsystem:
    - `content_pack.py`, `models.py`, `outline_builder.py`, `pptx_renderer.py`, `project_store.py`, `quality_check.py`, `safety_templates.py`, `slide_planner.py`.
- `backend/prompts/AGENTS.md` — System-style instruction set for Wiki generation. Keep aligned with the repo's actual Wiki rules.
- `backend/tests/` — 15+ pytest test files covering chat routing, web search, auto-continuation, LLM service, wiki pipeline, presentation generation, HTML training, uploads, config, message export, and assistant optimization.

### Frontend

- `frontend/src/main.tsx` — App bootstrap.
- `frontend/src/app/App.tsx` — Root component with state-based page routing (no React Router; uses `currentPage` state + localStorage persistence).
- `frontend/src/app/components/pages/` — Primary views:
  - `ChatPage` — Q&A with streaming, KB selection, web search toggle.
  - `AssistantPage` — Preset assistant prompt switching with chat.
  - `SearchPage` — Full-text document search.
  - `KnowledgeBasePage` — KB management, document upload, wiki generation, lint.
  - `TrainingPage` — Training outline, PPTX, and HTML generation.
  - `SettingsPage` — Model provider, API key, model-role configuration.
  - `AboutPage` — Product info, version, check for updates.
  - `ReaderPage` — Document viewer overlay (page nav, highlights).
- `frontend/src/lib/` — API client (`api.ts`), TypeScript types (`types.ts`), global state context (`context.tsx`), chat utilities.
- `frontend/src/app/data/` — Assistant definitions (`assistants.ts`) and icon map (`assistant-icons.ts`).

### PageType enum (App.tsx)

```
'chat' | 'assistant' | 'search' | 'knowledge' | 'training' | 'settings' | 'about'
```

The sidebar has two groups:
- **Main nav**: 对话, 专业助手, 原文检索, 知识库管理, PPT生成
- **Bottom nav**: 设置, 关于

### Data directories

- `knowledge-bases/<kb_id>/raw/` — Original uploads.
- `knowledge-bases/<kb_id>/wiki/` — Generated wiki pages including `index.md` and `log.md` (reserved files).
- `knowledge-bases/<kb_id>/meta.json` — KB metadata and stats.
- `knowledge-bases/<kb_id>/raw/文档追踪.json` — Document tracking.
- `output/` — Generated PPTX and HTML files.
- `data/` — Sample/reference content.

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

- **Config**: GET/PUT `/api/config`, validate, current-kb, current-model
- **Knowledge bases**: CRUD + rename (`PUT /api/knowledge-bases/{kb_id}`)
- **Documents**: list, upload, delete-preview, delete, content, highlights (save/load)
- **Wiki**: list pages, get page, parse document (trigger generation), lint
- **Chat**: streaming (`POST /api/chat` SSE), sync (`POST /api/chat/sync`), export DOCX (`POST /api/chat/export`)
- **Search**: `POST /api/search`
- **Training**: outline, generate (PPTX), html, progress/{job_id}, cancel/{job_id}, download/{filename}, preview/{filename}, cleanup
- **Assistants**: list, optimize-prompt

If you add or rename an endpoint, update the frontend client and any affected types together.

## Development Notes

- `backend/app.py` defaults to `http://localhost:8000` with auto-reload.
- The frontend expects the backend at `http://localhost:8000`.
- The app uses local storage for some chat/session UI state (`anniu-current-page-v1` key), so behavior may be stateful between reloads.
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
