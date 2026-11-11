# Architecture

AI Sprite Studio is an offline-first modular monorepo. The browser UI communicates with a local FastAPI service. SQLite and project files will be added behind storage boundaries in Sprint 1. ComfyUI remains a separate local process behind an adapter introduced in Sprint 4.

## Sprint 0 boundaries

```text
React/Vite UI -> HTTP /api/v1 -> FastAPI
                                  |
                                  +-- configuration only

Future: FastAPI -> domain services -> SQLite + project files
                           |
                           +-> AIProviderAdapter -> ComfyUI or mock provider
```

- React components do not parse ComfyUI workflows.
- API routes will delegate business behavior to domain services as features arrive.
- AI generation is intentionally absent from Sprint 0.
- The backend binds to loopback by default.
- Runtime paths come from environment settings and are not hardcoded to a drive.

## Decisions

- pnpm workspaces provide a lightweight monorepo without introducing a task orchestrator yet.
- Canvas 2D, database libraries, migrations, and AI libraries are deferred until their owning sprint.
- The UI may display configuration readiness but must not imply that AI generation works.

