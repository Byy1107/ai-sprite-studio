# AI Sprite Studio

AI Sprite Studio is an offline-first Windows workspace for creating and editing micro-pixel and 8-bit game assets. The project is being delivered incrementally; Sprint 3 adds the manual pixel editor core.

## Sprint 3 status

- React, TypeScript, Vite, and Tailwind frontend shell.
- FastAPI backend with `/api/v1/health`.
- Frontend status cards for the browser application, backend, local workspace, database configuration, and ComfyUI configuration.
- Unit tests, linting, type checking, build scripts, and Windows setup documentation.
- SQLite project metadata, project folders, safe trash behavior, and project CRUD UI.
- PNG import for character, item, environment, and tileset assets with thumbnails and checksums.
- Immutable asset versions with restore-as-new-version behavior.
- Canvas 2D pixel editor with pencil, eraser, picker, fill, line, rectangle, pan, zoom, grid, palette, and undo/redo.
- Local editor drafts and publishing manual edits as immutable PNG versions.
- No AI models are downloaded and generation is not implemented yet.

## Requirements

- Windows 10 or 11 64-bit.
- Node.js 20, 22, or 24 LTS and pnpm 10.
- Python 3.11 64-bit. Python 3.12+ is not part of the supported Sprint 0 matrix.
- Git.

ComfyUI is optional during Sprint 1. Its default endpoint is recorded for future adapters, but the application must open without it.

## Quick start

```powershell
Copy-Item .env.example .env.local
pnpm install
pnpm dev:web
```

In another terminal:

```powershell
cd apps/api
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m alembic upgrade head
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:5173`. See `docs/setup-windows.md` for the full setup and troubleshooting guide.

## Validation

```powershell
pnpm lint
pnpm typecheck
pnpm test
pnpm build

cd apps/api
python -m ruff check .
python -m mypy app
python -m pytest
```

## Safety and privacy

The API binds to `127.0.0.1` by default. User assets, prompts, project databases, and models remain local. Do not expose the API or ComfyUI to a network without deliberate security configuration.

## Roadmap

The authoritative roadmap is the user-maintained `AI_SPRITE_STUDIO_MASTER_PLAN.md`. Work stops after each sprint for review and approval. Add the master plan to the repository when its source file is available inside the workspace.
