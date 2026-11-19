# Sprint 10: Recovery, Backup, Performance, and UX Hardening

Status: in progress. Work remains local and uncommitted until requested.

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
- No commit, push, or merge without a separate user request.

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

## Remaining before acceptance

- In-app trash restore/purge remains deferred; there is no automatic deletion of recoverable project folders.
- Broader accessibility review, final loading/error states, and representative profiling.
- Browser-level critical-path smoke test, representative editor/thumbnail/queue profiling, and full Sprint 10 acceptance.

## Risks

- Browser local storage is origin- and device-specific, size-limited, and not a project backup. A crash before the 500 ms debounce or a storage failure can lose the latest unpublished stroke. Published versions are unaffected.
- Startup reconciliation is read-only. It detects missing files but does not reconstruct them.
- Backup and restore are limited to 128 MB and 5,000 files, and require a fresh destination workspace. Excluded browser drafts, cache, and trash are not recoverable from the ZIP.

## Validation to date

- Focused project and editor tests passed. Full backend regression: 103 tests passed; Ruff and targeted mypy pass on Python 3.11. Full mypy fails on a redundant cast in the unchanged `app/services/exports.py:196`.
- Full frontend regression: 24 tests passed; ESLint, TypeScript, and Vite production build passed.
- Upstream Starlette/Alembic deprecation warnings and the pre-existing duplicate React key warning remain non-fatal. Browser-level critical-path validation, representative profiling, and accessibility review are still required before declaring Sprint 10 complete.
