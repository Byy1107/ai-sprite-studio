# Sprint 8: Animation Timeline and Moveset

Status: implemented locally; automated checks and production-preview browser smoke test pass.

## Goal

Compose and preview character sprite animations from immutable asset versions. A character's clips form its moveset; no visual state machine is included.

## Completed scope

- SQLite animation and frame tables with Alembic migration `0005`.
- API to create, list, edit, and delete clips; add, edit, duplicate, delete, and reorder frames.
- Frames pin an existing version belonging to the same character asset and matching the clip canvas.
- Frame duration, order, pivot, offset, and optional event marker persist in SQLite.
- Character timeline with drag/drop and button reorder, version picker, loop/once/ping-pong playback, optional onion skin, and nearest-neighbor preview.
- Preview uses each frame's duration; FPS sets the default duration for newly added frames.

## Technical decisions and data format

- Clips belong to a character asset. `direction` and clip name are metadata strings. A moveset is all clips for that asset.
- Frames reference immutable `asset_versions.id`; duplicate copies metadata without copying PNG bytes. Deleting a clip/frame never deletes the referenced version.
- Duration uses integer milliseconds. Offset and pivot use source-image pixels. These fields are exposed for the Sprint 9 export contract, but export itself is not part of this sprint.
- Existing data is unchanged. Migration `0005` is reversible and adds two tables. The backend also creates missing tables at startup for new local databases.

## Validation

- Backend: 68 tests passed; Ruff and mypy passed (33 source files).
- Frontend: 17 tests passed; ESLint, TypeScript, and production Vite build passed.
- Backend API integration covers version ownership, persistence after reopening the engine, reorder validation, duplicate, delete, and metadata.
- Migration test covers upgrade and downgrade on an empty SQLite database.
- Frontend tests cover timing boundaries, clip/frame interaction, reorder, and onion skin on/off.

## Manual verification

On 2026-11-13, an isolated local database and workspace were used with the fake
provider. In the production preview, a character with two saved versions could
create `walk`, add both frames, edit duration/pivot/offset/event, enable onion
skin, start and stop playback, and reorder frames. After reloading the page,
the reordered durations and frame metadata remained visible. The item-asset
visibility check and all three playback modes remain covered by automated
tests or need a separate manual pass; they were not all clicked in this smoke test.

## Known limits and remaining work

- Frames can be added from existing versions; importing an external PNG directly into an animation is not implemented. Publish it as an asset version first.
- Preview uses the browser clock and may pause in background tabs. Export uses the stored timing metadata in Sprint 9.
- The local Vite development server could not render because its existing pnpm
  dependency junction omitted a Babel `lru-cache` link (`_lruCache is not a
  constructor`). The production build and preview worked. A clean dependency
  install should be checked before claiming fresh-setup validation.
- Sprint 7 was completed locally in a separate uncommitted worktree. This
  Sprint 8 branch still starts at the older merged baseline; integrate the
  Sprint 7 work safely before publishing Sprint 8.
- GitHub remote status could not be rechecked during this session because the network connection was unavailable. Work is local and uncommitted on `codex/sprint-08-animation-timeline`.
- Sprint 9 has not started.
