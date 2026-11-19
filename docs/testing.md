# Testing

## Frontend

```powershell
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

Vitest and React Testing Library cover project, editor, generator, animation, and export behavior. `pnpm test:e2e` runs Chrome against isolated FastAPI/Vite services and a temporary SQLite/workspace; it covers the first PNG download, manual editing, animation, spritesheet export, and a 200-asset view. Use Python 3.11 for the API and set `AI_SPRITE_PYTHON` if its virtual environment is outside `apps/api`.

## Backend

From `apps/api` with the Python 3.11 virtual environment active:

```powershell
python -m ruff check .
python -m mypy app
python -m pytest
```

Backend tests use temporary SQLite databases and workspaces with FastAPI's in-process client. They include migrations, backup/restore, path safety, export bytes, and mocked ComfyUI adapters. No model, GPU, or cloud service is required.

## Validation order

Run the narrowest affected test first, then lint, type checking, full tests, build, and the browser critical path. Optional real ComfyUI/GPU validation must be recorded separately; fake and mock tests do not establish model quality.

