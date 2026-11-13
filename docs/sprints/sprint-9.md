# Sprint 9: PNG, Spritesheet, JSON, GIF, and Godot Export

Status: complete. Feature acceptance and supported Python 3.11 fresh-setup checks passed. Sprint 10 requires separate approval.

## Goal

Produce local, game-ready exports from published immutable asset versions and animation clips without modifying source assets or replacing earlier exports.

## Completed scope

- `ExportRecord` and reversible Alembic migration `0006`.
- Integer-scale RGBA PNG export from a pinned published version, using nearest-neighbor resampling.
- Deterministic row-major grid spritesheet for one character clip, with configurable columns, spacing, padding, and scale.
- Schema-v1 JSON with image size, frame rectangles, duration, direction, loop mode, FPS, pivot, offset, event names, and pinned version IDs.
- A published Draft 2020-12 JSON Schema at `docs/schemas/spritesheet-v1.schema.json`, validated against generic and Godot exports in backend tests.
- GIF preview with per-frame duration rounded to GIF centiseconds, loop/once/ping-pong playback, nearest-neighbor scaling, and frame offsets.
- Project-local unique export directories, checksum, listing, and PNG/JSON download endpoints.
- Basic export controls and links in the asset library.
- Selectable Godot 4 preset, with a sample `AnimatedSprite2D` importer in `examples/godot4/`.
- Reusable Godot 4.4 headless smoke script validating imported frames against actual exported PNG + JSON.
- API/integration tests for scale, alpha, rectangles, metadata, repeatability, version ownership, source integrity, migration, and non-overwrite behavior.

## Scope still pending

- None for Sprint 9. Release-level checks remain in Sprint 11.

## Technical decisions and data format

- `POST /api/v1/exports` accepts `format: png` with `version_id` (default: active version), or `format: spritesheet` with a required `animation_id`. Scale is 1, 2, 4, or 8. Spritesheet layout accepts `columns`, `spacing`, and `padding`. Optional `preset_id: godot4` records the Godot target and marks the JSON schema-v1 metadata for the sample importer; it does not generate `.tres`.
- `GET /api/v1/projects/{project_id}/exports` lists records; `GET /api/v1/exports/{id}` reads one. `GET /api/v1/exports/{id}/download` returns the primary image. `/files/png`, `/files/json`, and `/files/gif` address individual outputs.
- Output lives under `<project>/exports/<export-id>/sprite.png` with `sprite.json` for sheets, or `sprite.gif` for previews. Paths in the database are project-relative. The caller cannot choose a disk path, and every export uses a new UUID directory.
- Frame pixels remain in their original canvas positions; `offset` and `pivot` are preserved as source-pixel metadata for consumers. Rectangle coordinates and dimensions are scaled pixels in the sheet. No scaling uses smoothing.
- JSON and PNG bytes are deterministic for the same pinned versions, clip metadata, and layout. Export IDs and timestamps are intentionally excluded from the JSON payload.
- The JSON Schema is local documentation and a test contract; export requests do not perform network schema lookup.
- GIF stores one frame duration in 10 ms units (minimum 20 ms) and cannot preserve full RGBA alpha precision. `ping_pong` expands the interior frames in reverse; `once` omits an infinite-loop extension.
- The service rejects a foreign asset version or clip, missing/corrupted source files, empty or oversized sheets, outputs beyond 32 megapixels, and oversized GIF playback sequences. Source checksums are rechecked before export.
- Export files are written before committing the success record. A process failure between these steps may leave an unlisted UUID export directory; cleanup/reconciliation belongs to Sprint 10, not silent deletion here.

## Migration and compatibility

- Migration `0006` adds only `export_records`; existing project, asset, and animation data are unchanged.
- Downgrade drops the new record table but does not delete user export files.
- The API creates missing tables on startup for a fresh local database, consistent with earlier sprints; existing installations should run Alembic upgrade.

## Validation

- Final local regression: 94 backend tests and 20 frontend tests passed; Ruff, mypy, ESLint, TypeScript, and the production Vite build passed. The export test set includes GIF timing, transparency, loop behavior, source checksum rejection, migration, and the Godot metadata contract.
- A frozen-lockfile pnpm 10.11.0 reinstall restored the frontend dependency tree; focused and full frontend checks passed, and the Vite development server served `src/main.tsx` with HTTP 200. The first offline attempt failed because the cache lacked packages; the online reinstall completed without changing the lockfile.
- A portable Python 3.11.18 runtime and isolated virtual environment were provisioned outside the repository. Fresh installation of the declared API development dependencies passed 6 export-focused tests, all 94 backend tests, Ruff, and mypy across 38 source files. The fresh dependency set emitted only upstream Starlette and Alembic deprecation warnings.
- Frontend regression was repeated: 20 tests, ESLint, TypeScript, and the Vite production build passed. The existing asset-library test still emits a duplicate React key warning; it does not fail this sprint gate.
- Windows browser smoke test passed against an isolated local database using a production preview: created a project, imported a 16×16 PNG, added a one-frame clip, exported PNG, Godot 4 sheet + JSON, and GIF, and triggered all three download links.
- Godot 4.4 stable was run as a portable, self-contained binary against the browser-exported PNG + JSON in an isolated copy of `examples/godot4/`. Headless editor import exited 0; `smoke_test.gd` printed `Godot 4.4 import smoke passed` and exited 0 after checking the animation name, frame count, FPS, loop mode, duration, and rectangle. Godot logged a non-fatal root certificate store warning in the sandbox; the test used no network.
- The Godot importer cannot automatically apply per-frame pivot, offset, or event markers. These remain in JSON for game code.

## Known issues and risk

- The earlier pnpm/Babel `_lruCache is not a constructor` development-server error was caused by an incomplete local dependency tree and disappeared after the frozen-lockfile reinstall. The offline cache was incomplete, so a first-time install needs registry access.
- The Godot test covered one exported one-frame clip. Multi-frame ping-pong behavior remains covered by backend metadata tests, not a Godot runtime fixture. No Godot binary is in the repository.
- The repository still does not contain the user-maintained master plan; the source document was read from the user's Documents folder for this sprint.

## Recommendation

Sprint 9 is ready for review. The remaining release-level checks belong to Sprint 11; do not start Sprint 10 without approval.
