# Sprint 10: Recovery, Backup, Performance, and UX Hardening

Status: complete on the Sprint 10 feature branch; ready for review. No merge or release has been performed.

## Goal

Make existing offline-first project and asset workflows safer for real use without adding Sprint 11 packaging or release features.

## Scope and order

1. Recover manual pixel drafts after an interrupted editor session without replacing published versions.
2. Detect and report missing database-referenced project files; never silently delete or recreate published versions.
3. Add safe project backup and restore into a new workspace, followed by trash/cache policy.
4. Improve keyboard access, loading/error states, and profile representative editor, thumbnail, and queue paths.
5. Validate the critical path and a large project fixture against an explicit local performance target.

## Acceptance gates

- An interrupted edit leaves published versions intact and restores a valid draft.
- A backup restores project data and files in a separate workspace without overwriting an existing project.
- Missing files are reported explicitly.
- The large-project fixture meets a documented target.
- Backend and frontend checks plus a critical-path smoke test pass.

## Non-scope

- No cloud backup, telemetry, model downloads, or Sprint 11 release packaging.

## Increment implemented

- Manual pixel drafts autosave to local browser storage 500 ms after a change and flush on page hide. A valid draft is restored after reopening the editor; invalid or incompatible drafts are ignored rather than blocking the published image. Storage failures are shown to the user. Drafts remain separate from immutable published versions.
- `GET /api/v1/projects/{project_id}/integrity` checks project metadata, active asset thumbnails, all versions for active assets, generation results, and export outputs. It reports missing or unsafe paths without changing database records or files. A project card offers an explicit **Check files** action and displays each issue.
- Backend startup checks active projects and logs issue counts, without blocking startup or attempting destructive repairs.
- Focused editor and dashboard tests cover recovery and reporting; backend tests cover detection, non-mutation, and startup reporting.
- Project ZIP backup includes project metadata, database records, and referenced files; it excludes cache, trash, and temporary files. Restore verifies checksums and archive paths, then creates a project in a fresh workspace without replacing existing files or database records. The dashboard exposes download and upload controls.
- Trash collisions fail without deleting the existing trash copy or source project. Deleted project folders remain in the workspace `.trash` indefinitely; there is no automatic purge or in-app trash restore yet.
- Cache cleanup is manual per project (`DELETE /api/v1/projects/{id}/cache`) and requires confirmation in the dashboard. It removes only unreferenced files under that project's `cache` directory, rejects links/unsafe roots and database-referenced cache paths, and leaves assets, exports, and trash untouched. There is no scheduled cleanup.
- Pixel-editor shortcuts are scoped to the focused editor: B/E/I/F/L/R/H/S choose tools, Ctrl+Z/Y undo/redo, Ctrl+Shift+Z redo, and Ctrl+S saves a draft. Text fields and other pages retain their normal keyboard behavior. Buttons expose shortcut metadata and the editor displays a key legend.
- The backend critical-path smoke test now creates a project, imports and manually versions an asset, adds an animation frame, exports a spritesheet, backs up, and restores into a fresh workspace; it compares restored image and JSON bytes.
- A 200-asset fixture opens and lists assets within a provisional 5-second local target. This measures the two API calls after fixture creation, not browser rendering or GPU generation.
- Asset/version, export, and generator panels now distinguish loading and failed requests from empty results. Version restore cannot be submitted twice while pending. Keyboard focus has a visible outline and several low-contrast labels are brighter.
- A mocked frontend integration test exercises project creation, opening, PNG import, animation clip/frame creation, and spritesheet JSON export. It complements the backend critical-path smoke test but is not a browser-level end-to-end test.
- Reproducible local probes now cover 100 editor pencil strokes on a 128×128 canvas, 20 nearest-neighbor thumbnail writes from 512×512 PNGs, and ten serial fake-provider jobs. They assert output correctness but deliberately do not impose machine-dependent CI timing thresholds.
- The focused pixel canvas now exposes a visible keyboard cursor. Arrow keys move one pixel, Space/Enter applies the selected drawing tool, and two presses set the endpoints for line, rectangle, or region selection. Tests cover keyboard drawing and draft autosave without publishing. Pan still requires pointer input or viewport scrolling.
- The viewport is focusable for keyboard scrolling. Project, animation, export, asset, and generator panels distinguish loading and error states with live status or alert roles. Duplicate sibling keys in the asset detail were removed, preventing repeated animation panels; the selected asset now follows refreshed server state after publishing a version.
- A Chrome/Playwright smoke test runs against real FastAPI and Vite servers with a fresh temporary SQLite database and workspace. It covers project creation, PNG import, keyboard pixel edit, immutable publish, animation frame, spritesheet JSON export, and page reload. A second browser test renders 200 imported asset tiles.

## Local performance profile

Run `pnpm --dir apps/web exec vitest run src/features/editor/editorState.performance.test.ts --reporter=verbose` and, from `apps/api`, `python -m pytest tests/test_sprint10_performance.py -q -s`. Local runs measured 36–46 ms for 100 editor strokes, 0.050 s for 20 thumbnail imports, and 0.152 s for ten fake jobs. The backend 200-asset open/list test retains its 5-second target. Chrome rendered 200 asset tiles in 187 ms in one local E2E run. These are process/UI observations on the current development machine, not GPU/ComfyUI measurements or universal frame-rate guarantees.

## Acceptance and exclusions

- Interrupted edits recover as local drafts without altering published versions; backup restores verified data into a separate workspace; integrity and startup checks report missing files without mutation.
- The 200-asset backend fixture meets its provisional 5-second API target, and the real-browser critical path plus 200-tile render pass.
- Basic keyboard and status/error accessibility is covered by automated tests. A manual screen-reader audit and real GPU/ComfyUI performance study remain separate follow-up work, not claims of this sprint.
- In-app trash restore/purge remains deferred by policy; no automatic deletion of recoverable project folders occurs.

## Risks

- Browser local storage is origin- and device-specific, size-limited, and not a project backup. A crash before the 500 ms debounce or a storage failure can lose the latest unpublished stroke. Published versions are unaffected.
- Startup reconciliation is read-only. It detects missing files but does not reconstruct them.
- Backup and restore are limited to 128 MB and 5,000 files, and require a fresh destination workspace. Excluded browser drafts, cache, and trash are not recoverable from the ZIP.

## Validation to date

- Backend: 105 pytest tests passed; Ruff and full mypy passed on Python 3.11. A redundant export-service cast was removed so the type-check gate is clean.
- Frontend: 30 Vitest tests passed; ESLint, TypeScript, and Vite production build passed. Two Chrome/Playwright E2E tests passed against real localhost services and isolated temporary data.
- Reproduce browser checks on Windows with an installed Google Chrome, free ports 8000/5173, Python 3.11 backend dependencies, and `pnpm test:e2e`. Set `AI_SPRITE_PYTHON` to a Python executable if neither `apps/api/.venv-local` nor `apps/api/.venv` is used. Playwright does not download a browser or model for this run.
- Upstream Starlette/Alembic deprecation and Node `--localstorage-file` warnings remain non-fatal. Browser E2E revealed and verified the fix for repeated animation panels.
