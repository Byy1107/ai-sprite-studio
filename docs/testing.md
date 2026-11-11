# Testing

## Frontend

```powershell
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

Vitest and React Testing Library verify the shell and backend health states. Vite production build is the Sprint 0 browser smoke gate.

## Backend

From `apps/api` with the Python 3.11 virtual environment active:

```powershell
python -m ruff check .
python -m mypy app
python -m pytest
```

Backend tests use FastAPI's in-process test client and require no database, workspace files, ComfyUI, GPU, or network access.

## Validation order

Run the narrowest affected test first, then lint, type checking, full tests, and builds for the component changed. GPU checks are not part of Sprint 0.

