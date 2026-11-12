# Architecture

AI Sprite Studio is an offline-first modular monorepo. The browser UI communicates with a local FastAPI service. SQLite stores searchable metadata while project files remain behind a storage service. ComfyUI remains a separate optional local process behind the Sprint 5 adapter.

## Current boundaries

```text
React/Vite UI -> HTTP /api/v1 -> FastAPI -> project service -> SQLite
                                                       |
                                                       +-> project storage

FastAPI -> generation service -> AIProviderAdapter -> fake provider
                                              |
                                              +-> ComfyUI adapter -> local ComfyUI
```

- React components do not parse ComfyUI workflows.
- API routes delegate project behavior to a service and domain validation layer.
- Project folders use atomic `project.json` writes and workspace-local trash.
- Provider-neutral generation jobs persist independently from ComfyUI workflow details.
- The backend binds to loopback by default.
- Runtime paths come from environment settings and are not hardcoded to a drive.

## Decisions

- pnpm workspaces provide a lightweight monorepo without introducing a task orchestrator yet.
- SQLAlchemy 2 and Alembic own database access and migrations.
- Canvas 2D remains isolated from provider transport details.
- The UI displays the selected provider's actual readiness and does not imply ComfyUI is available when offline.
- Generation requests cross a provider-neutral domain contract. The UI never receives workflow JSON.
- A single-worker executor serializes local generation jobs; persisted state supports restart recovery.

