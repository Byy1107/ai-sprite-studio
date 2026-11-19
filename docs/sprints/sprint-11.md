# Sprint 11: V1 Release Candidate

Status: Sprint 11 implementation and validation complete. The owner authorized commit, push, and merge; no V1 release tag is authorized.

## Goal

Validate and document the existing V1 feature set. Do not add V2 features or imply that an optional ComfyUI setup works without a compatible local installation and model.

## Scope

1. Reproduce a fresh Windows setup and run the full backend, frontend, and browser regression gates.
2. Review local file and archive paths for accidental overwrite, traversal, and data loss; add focused regression tests for findings.
3. Document project and export formats, database migrations, first-export steps, and ComfyUI troubleshooting.
4. Record known issues, release checklist, version-tagging plan, and prioritized V2 follow-ups based on observed V1 gaps.

## Acceptance gates

- Every V1 quality gate passes, or an exception is explicitly documented for owner review.
- No known data-loss bug remains open.
- A new Windows user can follow setup and create a first export.
- The V1 project, backup, export, and database migration versions are unambiguous.
- V2 priorities come from actual V1 findings.

## Audit outcome

- Sprint 10 is complete on its feature branch; this sprint starts from that commit without rewriting prior work.
- `project.json` and the SQLite project record carry schema version 1; backup archives use `backup_version` 1; spritesheet metadata uses schema version 1. Alembic currently has revisions 0001–0006.
- Project update and deletion originally trusted the stored `root_path` directly. A modified or linked root could affect files outside the configured workspace. Shared project lookup now rejects that root for project, asset, and export operations; generation also checks it. A project-path resolver rejects traversal, absolute paths, and symlinks/junctions in asset, export, candidate, and reference paths. Metadata writes use a unique temporary file rather than a predictable `.tmp` name.
- Regression tests cover tampered roots, traversal in database paths, Windows directory junctions for asset/trash paths, duplicate-name metadata consistency, archive traversal/checksums, immutable version safety, and backup/restore into a fresh workspace. No known data-loss defect remains in the tested V1 workflows.
- Manual screen-reader validation and real GPU/ControlNet/IP-Adapter performance are not covered by these gates. They remain disclosed follow-ups; this sprint does not claim them as passing or claim a fully validated AI model.

## Validation log

- On this Windows host, a fresh isolated Python 3.11.18 environment was created and the API plus development dependencies were installed from a local uv cache. A fresh SQLite database upgraded through Alembic `0006 (head)`. A separate regression upgrades a populated `0005` project to `0006`, imports a new asset, exports PNG, and passes integrity checking.
- Backend with that Python 3.11 environment: 113 pytest tests passed with no skips; Ruff and strict mypy passed. Seven non-fatal upstream Starlette/Alembic deprecation warnings were reported.
- Node 22.22.0 and pnpm 10.11.0 completed a frozen dependency install. The first run needed three lockfile-pinned package downloads, after which the frozen offline reinstall passed. Under Node 22, ESLint, TypeScript, all 30 Vitest tests, and the production Vite build passed.
- Chrome/Playwright with the fresh Python 3.11 backend and Node 22 frontend: both E2E tests passed against isolated temporary SQLite and workspace data. The critical path now downloads a first PNG, publishes an immutable manual edit, exports a spritesheet/JSON, and survives reload; the other test renders 200 assets. No model or browser download was needed.
- Backup/restore tests compare published PNG and export JSON bytes in a fresh workspace; path and archive tests verify refusal rather than silent overwrite. The first-export guide and V1 schema/migration document were checked against these API/UI paths.
- This was a clean isolated setup on the current Windows host, not a second physical clean machine. Manual screen-reader and optional model/GPU quality studies remain outside the tested RC claims and should be scheduled before broader distribution.

## Release decision

Sprint 11 work is complete. Core V1 engineering and release gates in the master plan passed in the isolated supported-runtime setup; no exception to those gates is claimed. This is not a general-availability or AI-model-readiness claim. The owner authorized source integration after reviewing the progress. Known limitations in `docs/release-checklist.md` remain; release tagging and broader distribution require separate review.
