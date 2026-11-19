# V1 Project, Backup, and Migration Format

## Local project

The SQLite database is the authoritative index for projects, assets, immutable asset versions, generation jobs/results, animations/frames, and exports. The configured workspace (`AI_SPRITE_WORKSPACE_DIR`) stores one folder per project slug. Do not move, rename, or edit project folders or the database independently while the API is running.

Each project root contains `project.json` with `schema_version: 1`, `id`, `name`, `slug`, `description`, `created_at`, and `updated_at`. The SQLite `projects.schema_version` is also 1. Published PNGs live under `assets/<asset-id>/versions/`, thumbnails under `assets/<asset-id>/thumbnails/`, and exports under `exports/<export-id>/`. Animation records and frame references are stored in SQLite, not as standalone animation files. `cache/` and `trash/` are local working directories. Browser editor drafts are origin-specific local storage, not project files.

The project folder alone is **not** a portable project. Use the project ZIP backup to preserve database rows and referenced files together. Backups have manifest `backup_version: 1`, table records, SHA-256 file checksums, and `files/` entries. They exclude cache, trash, temporary files, and browser drafts. The archive is limited to 128 MB and 5,000 files. Restore verifies paths/checksums and requires a new workspace/database; it does not merge or overwrite projects. Keep an untouched original backup until integrity and a test export pass in the restored workspace.

## Export contracts

- Single PNG: nearest-neighbor integer scale 1×/2×/4×/8× from a chosen published version.
- Spritesheet: `sprite.png` plus `sprite.json`, with `meta.schema_version: 1`. The JSON schema is `docs/schemas/spritesheet-v1.schema.json`; frame records include rectangles, duration, pivot, offset, and events. The Godot 4 preset adds `meta.preset_id: "godot4"` without changing schema version.
- GIF: preview output from a character animation; GIF timing is rounded to GIF's 10 ms granularity and is not a lossless source project format.
- Export record `config_json` stores the request with `schema_version: 1`. Every export uses a new UUID folder and does not overwrite prior output.

## Database migration policy

Alembic revisions `0001` through `0006` create the V1 database schema; `0006` is the current head. On an existing installation, stop the API, copy both the SQLite database **and** workspace to a safe location, then run `python -m alembic upgrade head` from `apps/api` using the same environment settings as the API. Start the API, run **Check files**, and verify one existing export and one new export. Do not copy only the database or only the workspace. The CLI migration updates SQLite schema; it does not migrate `project.json` or ZIP backup formats. Restore from a verified backup if migration or verification fails; do not hand-edit `alembic_version`.

Future project or backup format changes must increment the relevant version, supply a migration/compatibility test, and document how older projects are handled. A newer, unknown backup version is rejected rather than guessed at.
