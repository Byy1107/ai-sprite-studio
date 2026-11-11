# Sprint 0: Repository and Engineering Baseline

## Goal

Provide a reproducible foundation for the React/Vite frontend and FastAPI backend without introducing product features or heavyweight AI dependencies.

## Completed scope

- Monorepo and Git baseline.
- React, TypeScript strict mode, Vite, Tailwind, routing, and query state.
- FastAPI application settings and `/api/v1/health`.
- Status dashboard with honest future-feature boundaries.
- Frontend and backend tests, linting, type checking, and build configuration.
- Windows setup, architecture, testing, ADR, environment, and changelog documentation.

## Deferred scope

- Project CRUD and SQLite migrations belong to Sprint 1.
- Assets, pixel editor, animation, exports, AI queue, mock provider, and ComfyUI adapters belong to later sprints.
- CI remote workflow is deferred until a repository remote is available and dependency checks pass locally.

## Technical decisions

- pnpm 10 is the sole JavaScript package manager.
- Python 3.11 is the supported backend runtime.
- ComfyUI remains a separately operated future provider.
- Backend and frontend bind to loopback during development.

## Data and migrations

No database schema or persisted project format is introduced in Sprint 0.

## Tests and validation

- `python -m compileall -q apps/api/app apps/api/tests`: passed with the available Python 3.13 interpreter as a syntax-only check.
- `node --check apps/web/eslint.config.js`: passed.
- `git diff --check`: passed for tracked content, but the repository has no initial commit and files remain untracked.
- `pnpm install`: blocked because this managed environment denies access to `registry.npmjs.org`.
- `pnpm lint`, `pnpm typecheck`, `pnpm test`, and `pnpm build`: attempted but blocked by the same missing dependency/network condition.
- `python -m pytest`, `python -m ruff`, and `python -m mypy`: attempted but unavailable because Python development dependencies are not installed.

## Manual verification

Start the API and frontend, open the dashboard, and verify that backend health changes from unavailable to ready. Confirm the UI states that generation is not implemented.

## Known issues

- The current workstation reports Python 3.13; install or select Python 3.11 before backend dependency validation.
- Package installation is blocked in the current sandbox, so dependency-backed lint, tests, type checking, and build remain to be run in an environment with registry access.
- The repository branch could not be changed because the managed environment denied writes to Git reference lock files; the working tree currently remains on `main`.
- The master plan source is outside this task workspace and was read as the sprint authority, but is not duplicated into this repository.
- ComfyUI health is configuration-only in this sprint.

## Risks and next recommendation

Validate setup on a clean Windows environment before Sprint 1. Begin Sprint 1 only after review and explicit approval.
