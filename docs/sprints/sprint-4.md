# Sprint 4: AI Adapter and Fake Provider

## Goal

Establish provider-independent generation contracts, persisted job lifecycle, and a deterministic development provider without requiring a GPU, ComfyUI, or model downloads.

## Completed scope

- `AIProviderAdapter`, generation request, result, and status domain contracts.
- Deterministic fake provider that creates transparent pixel-style PNG candidates from prompt and seed.
- SQLite generation job/result records and Alembic migration.
- Single-worker local queue, queued/running/succeeded/failed/canceled states, progress, and restart recovery.
- Create, list, detail, cancel, and result APIs.
- Generator UI with prompt, asset type, style, dimensions, seed, status polling, and cancel control.

## Deferred scope

- ComfyUI HTTP/WebSocket integration and SD1.5 workflows remain Sprint 5.
- Accepting candidates as asset versions remains Sprint 5.
- Advanced generation presets, references, and AI-assisted editing remain later sprints.

## Technical decisions

- Provider details are isolated behind a Python protocol in the domain layer.
- The fake provider is deterministic for the same request and seed.
- The UI receives normalized job data and never parses provider workflow JSON.
- Jobs interrupted by application restart are marked failed with an actionable code.

## Migration and format changes

- Migration `0003` adds `generation_jobs` and `generation_results`.
- Candidate files are stored beneath each project in `candidates/<job-id>/result.png`.

## Tests and validation

- Backend integration tests cover successful jobs, cancellation, invalid projects, result persistence, and restart recovery.
- Frontend component tests cover fake job submission and the real-generation warning.
- Backend Ruff and mypy pass; all 16 backend tests pass.
- Empty-database Alembic upgrade through migration `0003` passes.
- Frontend lint and typecheck pass; all 10 frontend tests and the production build pass.

## Manual verification

Open a project, submit a fake prompt, observe queued/running/succeeded status, and confirm the UI states that ComfyUI is disconnected.

## Known issues

- The fake output is a development fixture, not AI-generated artwork.
- Progress is coarse and polling-based; provider event streaming begins with the ComfyUI adapter.
- Running fake image creation is short, so cancellation is most reliable while a job is queued.

## Risks and next recommendation

Keep ComfyUI transport, workflow manifests, and provider-specific errors inside the Sprint 5 adapter. Do not expose workflow JSON to React or couple generation jobs to GPU availability.
