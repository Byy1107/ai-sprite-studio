# Sprint 2: Asset Library, Import, and Versioning

## Goal

Allow users to import validated PNG assets, browse their metadata, and retain immutable version history across restarts.

## Completed scope

- Asset and AssetVersion database records with Alembic migration `0002`.
- PNG validation, 16 MB upload limit, 4096-pixel dimension limit, and corrupt-file rejection.
- SHA-256 checksum, nearest-neighbor thumbnail generation, and atomic file writes.
- Asset import/list/detail and version list/restore API routes.
- Asset library UI for character, item, environment, and tileset types.
- Restore creates a new active version and preserves the original history.

## Deferred scope

- Manual pixel editing and publishing editor drafts remain Sprint 3.
- AI-generated versions remain Sprint 4 and later.
- Asset deletion, trash recovery, and permanent cleanup remain hardening work.

## Technical decisions

- Pillow performs format verification and thumbnail generation without changing source pixels.
- Original PNG bytes are stored as immutable version files under the project asset folder.
- Active version identity is stored on the asset while version rows remain append-only.

## Migration and format changes

- Migration `0002` creates `assets` and `asset_versions` with project/asset foreign keys.
- Imported files live in `assets/<asset-id>/versions`; thumbnails live in `assets/<asset-id>/thumbnails`.

## Tests and validation

- Backend Ruff and mypy checks pass; all 10 backend tests pass.
- Frontend lint, typecheck, all 4 tests, and production build pass.
- Alembic upgrade, downgrade to `0001`, and re-upgrade to `0002` pass on SQLite.

## Manual verification

Open a project, import a PNG, select its asset card, and verify version 1 is active. Restore version 1 and confirm version 2 becomes active without deleting version 1.

## Known issues

- Thumbnail files are generated for future serving but are not exposed as image URLs in the UI yet.
- New manual versions are intentionally deferred until the pixel editor sprint.

## Risks and next recommendation

Verify large and malformed images remain rejected without partial database rows. Begin Sprint 3 only after Sprint 2 checks and review pass.
