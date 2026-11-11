# Sprint 1: Project Workspace and Database

## Goal

Allow users to create, list, open, update, and safely remove local projects while preserving metadata across backend restarts.

## Completed scope

- SQLite-backed Project record and initial Alembic migration.
- Project domain validation for Windows-safe names and deterministic slugs.
- Storage service for project folders, atomic `project.json`, and workspace-local trash.
- Project CRUD and open endpoints under `/api/v1/projects`.
- Local project browser with create, empty, loading, error, open, and trash states.
- Backend integration and frontend component tests.

## Deferred scope

- Asset storage and versioning remain Sprint 2.
- Pixel editing, AI adapters, animation, and exports remain later sprints.
- Permanent deletion and trash cleanup remain recovery/hardening work.

## Technical decisions

- SQLAlchemy 2 is used for persistence and Alembic for reversible schema migration.
- Project slugs are generated at creation and remain stable when a display name changes.
- Project deletion moves files to `<workspace>/.trash/<project-id>` before soft-deleting metadata.
- SQLite foreign keys and WAL mode are enabled for every application connection.

## Migration and format changes

- Migration `0001` creates the `projects` table and name/slug indexes.
- Project folders contain `project.json` with `schema_version: 1` plus standard directories.

## Tests and validation

- Backend project CRUD, persistence, duplicate, path safety, and Windows reserved-name tests.
- Frontend project workspace, health, empty state, and create form tests.
- Backend Ruff, mypy, and pytest passed; 8 backend tests passed.
- Alembic empty-database upgrade, downgrade, and second upgrade passed.
- Frontend ESLint, TypeScript type-check, Vitest, and production build passed; 3 frontend tests passed.
- `git diff --check` passed.

## Manual verification

Create a project in the browser, restart the backend, and confirm it remains listed. Move it to trash and confirm the active list is empty while the folder exists under workspace `.trash`.

## Known issues

- Editing a project name intentionally does not rename its folder or stable slug.
- Trash restore and permanent cleanup are not part of Sprint 1.
- Local backend validation used Python 3.13 because this Windows installation could not execute its newly installed Python 3.11 runtime due to the host CET issue; CI remains the Python 3.11 acceptance environment.

## Risks and next recommendation

Validate migration upgrade on an empty database and persistence after restart. Begin Sprint 2 only after this sprint is reviewed, merged, and its checks pass.
