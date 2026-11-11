# Architecture

AI Sprite Studio is an offline-first modular monorepo. The browser UI communicates with a local FastAPI service. SQLite stores searchable metadata while project files remain behind a storage service. ComfyUI remains a separate local process behind an adapter introduced in Sprint 4.

## Sprint 1 boundaries

```text
React/Vite UI -> HTTP /api/v1 -> FastAPI -> project service -> SQLite
                                                       |
                                                       +-> project storage

Future: FastAPI -> domain services
                           |
                           +-> AIProviderAdapter -> fake provider (Sprint 4)
                                                -> ComfyUI adapter (Sprint 5)
```

- React components do not parse ComfyUI workflows.
- API routes delegate project behavior to a service and domain validation layer.
- Project folders use atomic `project.json` writes and workspace-local trash.
- AI generation is intentionally absent from Sprint 0.
- The backend binds to loopback by default.
- Runtime paths come from environment settings and are not hardcoded to a drive.

## Decisions

- pnpm workspaces provide a lightweight monorepo without introducing a task orchestrator yet.
- SQLAlchemy 2 and Alembic own database access and migrations.
- Canvas 2D and AI libraries remain deferred until their owning sprint.
- The UI may display configuration readiness but must not imply that AI generation works.
- Generation requests cross a provider-neutral domain contract. The UI never receives workflow JSON.
- A single-worker executor serializes fake generation jobs; persisted state supports restart recovery.

