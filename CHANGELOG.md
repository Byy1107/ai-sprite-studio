# Changelog

All notable changes to AI Sprite Studio are documented here.

## Unreleased

### Added

- SD1.5 generation and AI edits infer at up to 512 pixels on the longest side, then resize to the requested sprite canvas; edit sources and rectangular masks are scaled together, and workflow version 2 records both sizes.
- Sprint 7 immutable reference pinning, local capability discovery and optional LoRA, prepared-image ControlNet and IP-Adapter workflows.
- Pixel-editor variation and selected-region inpainting jobs with candidate review and unchanged active versions until acceptance.
- Exact outside-mask compositing, edit dimension checks and optional-node/model failure handling.
- Honest LoRA result metadata: a wired node is reported separately from unverified weight application, with a same-seed comparison warning in the generator.
- Explicit ComfyUI execution-error and empty-image reporting for optional workflows; result retrieval targets the intended SaveImage node.
- Sprint 6 specialized character, item, environment, and tileset generator presets.
- Optional Akar Langit dark-fantasy preset and provider-neutral negative prompts.
- Sprint 5 opt-in ComfyUI adapter and versioned SD1.5 baseline workflow.
- ComfyUI health/error reporting, result retrieval, and generated candidate acceptance.
- Sprint 4 provider-independent generation contracts and deterministic fake provider.
- Persisted serial generation queue with cancellation, results, and restart recovery.
- Fake generator UI with explicit warnings that ComfyUI and real models remain disconnected.
- Sprint 3 manual pixel editor with nearest-neighbor canvas rendering and core drawing tools.
- Undo/redo history, palette controls, pan/zoom/grid, local drafts, and manual version publishing.
- Sprint 2 PNG asset import, thumbnails, checksums, and immutable version history.
- Asset library UI for character, item, environment, and tileset metadata.
- Safe restore behavior that creates a new active version without deleting history.
- Sprint 1 SQLite project schema and initial Alembic migration.
- Safe local project storage with `project.json`, Windows name validation, and trash behavior.
- Project CRUD API and local project browser UI.
- Backend integration tests and frontend project creation coverage.
- Sprint 0 monorepo baseline for the React/Vite frontend and FastAPI backend.
- Health endpoint, application status dashboard, tests, and Windows setup documentation.
- Offline-first environment defaults and a future-facing ComfyUI configuration boundary.

