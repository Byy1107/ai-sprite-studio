# AI Sprite Studio

AI Sprite Studio is an offline-first Windows workspace for creating and editing micro-pixel and 8-bit game assets. Sprint 7 adds optional reference-guided generation and AI-assisted edits; Sprint 8 adds character animation clips and a timeline. Sprint 9 adds local PNG, spritesheet, JSON, GIF, and Godot-targeted exports. AI providers remain optional and local.

## Current status

- React, TypeScript, Vite, and Tailwind frontend shell.
- FastAPI backend with `/api/v1/health`.
- Frontend status cards for the browser application, backend, local workspace, database configuration, and ComfyUI configuration.
- Unit tests, linting, type checking, build scripts, and Windows setup documentation.
- SQLite project metadata, project folders, safe trash behavior, and project CRUD UI.
- PNG import for character, item, environment, and tileset assets with thumbnails and checksums.
- Immutable asset versions with restore-as-new-version behavior.
- Canvas 2D pixel editor with pencil, eraser, picker, fill, line, rectangle, pan, zoom, grid, palette, and undo/redo.
- Local editor drafts and publishing manual edits as immutable PNG versions.
- Deterministic fake generation jobs support persisted status, cancellation, results, and restart recovery.
- No AI models are downloaded. The fake provider remains the default and works without ComfyUI.
- ComfyUI health, prompt submission, history polling, result retrieval, timeout handling, and candidate acceptance are available when explicitly configured.
- The repository does not include or download checkpoints; users provide a licensed SD1.5-compatible checkpoint.
- Character, item, environment, and tileset generator modes use versioned local presets.
- The optional Akar Langit character preset provides a dark-fantasy bronze, indigo, and teal direction.
- Sprint 7 pins reference versions and discovers optional LoRA, ControlNet and IP-Adapter models through local ComfyUI.
- The pixel editor can queue whole-image variations or rectangular inpainting as candidates; inpaint results preserve pixels outside the selection.
- Optional workflow wiring and safety checks have automated coverage. On a GTX 1070 Ti, baseline generation and AI edits now render at up to 512 pixels before nearest-neighbor resizing; a sword silhouette remained recognizable through variation and masked inpainting. One locally converted LoRA was verified to affect pixels, but did not improve quality. Background cleanup and pixel-art quality remain open; ControlNet and IP-Adapter still require compatible local models and GPU validation.
- Character movesets support version-pinned frames, timing, loop modes, onion skin, pivot, offset, event markers, and reorder.
- Sprint 9 supports nearest-neighbor PNG, character-clip spritesheet PNG with a validated schema-v1 JSON contract, GIF preview, and a selectable Godot 4 preset with a tested sample importer at `examples/godot4/`. Exports use unique project-local directories and never replace previous exports. A fresh Python 3.11 backend setup passed the test, lint, and type-check gates.
- Sprint 10 hardening is complete on its feature branch: local draft recovery, read-only integrity reporting, ZIP backup/restore to a fresh workspace, safe trash/cache policy, keyboard pixel editing, and clearer loading/error states. A real-browser critical path and 200-asset fixture pass; screen-reader and GPU performance audits remain future follow-ups.
- When the editor has focus, B/E/I/F/L/R/H/S select tools; Ctrl+Z/Y undo/redo; Ctrl+S saves an unpublished draft. Typing in form fields does not trigger editor shortcuts.
- Focus the pixel canvas and use arrow keys to move its visible cursor one pixel at a time. Space/Enter applies pencil, eraser, fill, or picker; press twice to set the endpoints for line, rectangle, or region selection. Pan remains pointer/viewport-scroll based.

## Requirements

- Windows 10 or 11 64-bit.
- Node.js 20, 22, or 24 LTS and pnpm 10.
- Python 3.11 64-bit. Python 3.12+ is not part of the supported Sprint 0 matrix.
- Git.

ComfyUI is optional. The application opens and its generation workflow remains usable with the fake provider when ComfyUI is absent.

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

To back up a project, use **Download backup** on its card. To restore, start the app with a fresh workspace and SQLite database, then use **Restore backup**. Restore will not overwrite an existing project. The ZIP excludes browser drafts, trash, cache, and temporary files and is limited to 128 MB and 5,000 files.

Deleted project folders remain in the workspace `.trash` until manually handled; the app never purges them automatically. **Clear cache** removes only disposable, unreferenced files in the selected project's cache after confirmation. It does not touch published assets, exports, or trash. Cache cleanup is not scheduled.

## Validation

```powershell
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm test:e2e

cd apps/api
python -m ruff check .
python -m mypy app
python -m pytest
```

The Windows E2E command requires installed Google Chrome, Python 3.11 backend dependencies, and free ports 8000/5173. It starts FastAPI with a fresh SQLite database and workspace under the system temporary directory, then starts Vite; it does not use your regular project data or download a browser. Set `AI_SPRITE_PYTHON` when your backend virtual environment is in a nonstandard location.

## Safety and privacy

The API binds to `127.0.0.1` by default. User assets, prompts, project databases, and models remain local. Do not expose the API or ComfyUI to a network without deliberate security configuration.

## Roadmap

The authoritative roadmap is the user-maintained `AI_SPRITE_STUDIO_MASTER_PLAN.md`. Work stops after each sprint for review and approval. Add the master plan to the repository when its source file is available inside the workspace.
