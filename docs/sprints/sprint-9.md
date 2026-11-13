# Sprint 9: PNG, Spritesheet, JSON, GIF, and Godot Export

Status: in progress. PNG, single-clip spritesheet PNG + JSON, and GIF preview are implemented; Godot validation remains.

## Goal

Produce local, game-ready exports from published immutable asset versions and animation clips without modifying source assets or replacing earlier exports.

## Completed scope

- `ExportRecord` and reversible Alembic migration `0006`.
- Integer-scale RGBA PNG export from a pinned published version, using nearest-neighbor resampling.
- Deterministic row-major grid spritesheet for one character clip, with configurable columns, spacing, padding, and scale.
- Schema-v1 JSON with image size, frame rectangles, duration, direction, loop mode, FPS, pivot, offset, event names, and pinned version IDs.
- GIF preview with per-frame duration rounded to GIF centiseconds, loop/once/ping-pong playback, nearest-neighbor scaling, and frame offsets.
- Project-local unique export directories, checksum, listing, and PNG/JSON download endpoints.
- Basic export controls and links in the asset library.
- API/integration tests for scale, alpha, rectangles, metadata, repeatability, version ownership, source integrity, migration, and non-overwrite behavior.

## Scope still pending

- Documented Godot preset and a tested sample import path.
- Manual browser smoke test of export and downloaded files on Windows.
- Full frontend test/build validation in a clean dependency environment.

## Technical decisions and data format

- `POST /api/v1/exports` accepts `format: png` with `version_id` (default: active version), or `format: spritesheet` with a required `animation_id`. Scale is 1, 2, 4, or 8. Spritesheet layout accepts `columns`, `spacing`, and `padding`.
- `GET /api/v1/projects/{project_id}/exports` lists records; `GET /api/v1/exports/{id}` reads one. `GET /api/v1/exports/{id}/download` returns the primary image. `/files/png`, `/files/json`, and `/files/gif` address individual outputs.
- Output lives under `<project>/exports/<export-id>/sprite.png` with `sprite.json` for sheets, or `sprite.gif` for previews. Paths in the database are project-relative. The caller cannot choose a disk path, and every export uses a new UUID directory.
- Frame pixels remain in their original canvas positions; `offset` and `pivot` are preserved as source-pixel metadata for consumers. Rectangle coordinates and dimensions are scaled pixels in the sheet. No scaling uses smoothing.
- JSON and PNG bytes are deterministic for the same pinned versions, clip metadata, and layout. Export IDs and timestamps are intentionally excluded from the JSON payload.
- GIF stores one frame duration in 10 ms units (minimum 20 ms) and cannot preserve full RGBA alpha precision. `ping_pong` expands the interior frames in reverse; `once` omits an infinite-loop extension.
- The service rejects a foreign asset version or clip, missing/corrupted source files, empty or oversized sheets, outputs beyond 32 megapixels, and oversized GIF playback sequences. Source checksums are rechecked before export.
- Export files are written before committing the success record. A process failure between these steps may leave an unlisted UUID export directory; cleanup/reconciliation belongs to Sprint 10, not silent deletion here.

## Migration and compatibility

- Migration `0006` adds only `export_records`; existing project, asset, and animation data are unchanged.
- Downgrade drops the new record table but does not delete user export files.
- The API creates missing tables on startup for a fresh local database, consistent with earlier sprints; existing installations should run Alembic upgrade.

## Validation

- Final local regression: 93 backend tests and 20 frontend tests passed; Ruff, mypy, ESLint, TypeScript, and the production Vite build passed. The export test set includes GIF timing, transparency, loop behavior, source checksum rejection, and migration.
- Backend checks used an existing Python 3.13 environment even though the documented supported runtime is Python 3.11; a fresh Python 3.11 setup still needs verification.
- Browser smoke test and Godot sample validation are still pending.

## Known issues and risk

- The current workspace's pnpm dependency junction prevents Vite/Vitest from loading their config inside the restricted sandbox. Outside that sandbox, the focused UI test and full 20-test frontend suite plus production build passed. A clean dependency install remains unverified.
- Godot import and GIF playback are not claimed until implemented and tested.
- The repository still does not contain the user-maintained master plan; the source document was read from the user's Documents folder for this sprint.

## Recommendation

Complete GIF and Godot preset, validate a clean Windows dependency install and real browser downloads, then close Sprint 9 before starting Sprint 10.
