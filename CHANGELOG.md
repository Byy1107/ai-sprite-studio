# Changelog

All notable changes to AI Sprite Studio are documented here.

## Unreleased

- Start a separate local LoRA training foundation: export curated, captioned immutable asset versions as a checksum-verified ImageFolder-style ZIP. No trainer, model download, or GPU training is included.
- Add post-V1 LoRA dataset export and opt-in offline CLI preflight/launcher with optional trainer dependency/CUDA probe and atomic process-state records; no trainer, model weights, or GPU result is bundled or claimed.
- Complete Sprint 11 V1 release-candidate work on a local feature branch with first-export and ComfyUI troubleshooting guides, versioned project/backup/migration reference, and a gated release checklist. No tag or release is created.
- Reject unsafe stored project roots, traversal paths, linked asset/export/candidate directories, and unsafe trash roots; use a unique temporary metadata file and prevent duplicate-name updates from changing `project.json` before database validation.
- Verify a fresh Python 3.11 API environment, empty and previous-schema migrations, Node 22/pnpm 10 install, full regression, and browser PNG download.

- Sprint 10 complete on its feature branch: autosave/recovery for unpublished editor drafts, read-only project integrity reports, verified local project ZIP backup/restore, and real-browser critical-path validation.
- Add editor-scoped keyboard shortcuts for drawing tools, undo/redo, and local draft saving without intercepting text inputs.
- Add confirmed per-project cache cleanup with database-reference and path guards; preserve trash indefinitely without automatic purging.
- Improve asset, export, and generator loading/error feedback and keyboard focus visibility; add a mocked frontend critical-path integration test.
- Add reproducible Sprint 10 local editor, thumbnail, and fake-queue performance probes without brittle CI timing assertions.
- Add keyboard navigation and drawing on the focused pixel canvas, with a visible cursor and unpublished-draft regression coverage.
- Add isolated Chrome/Playwright smoke tests for the full project-to-export path and a 200-asset browser render; fix duplicate animation panels and stale selected-asset state found by the browser test.
- Add a selectable Godot 4 spritesheet preset and example importer for Sprint 9.

- Sprint 9 complete: immutable PNG, character-clip spritesheet PNG + schema-v1 JSON, GIF preview, download API, export history, and a basic export panel; verified on a fresh Python 3.11 environment.
- Sprint 8 timeline updates the direction field when switching clips; a UI regression test covers the transition.

### Added

- Sprint 8 character animation clips, persisted frame order and timing, and version-pinned frame metadata.
- Timeline preview with loop/once/ping-pong playback, onion skin, frame editing, and moveset grouping.
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

