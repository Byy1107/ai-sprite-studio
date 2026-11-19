# V1 Release Candidate Checklist

This checklist is a gate, not a release announcement. Record actual results in `docs/sprints/sprint-11.md` before tagging.

## Required checks

- [x] Recreate isolated Windows environments with Python 3.11, Node 22, and pnpm 10; migrate a new SQLite database and download the first PNG in Chrome. This validates a clean local setup, not a second physical Windows machine.
- [x] Run frontend lint, typecheck, 30 unit tests, build, and two Chrome E2E tests against isolated data.
- [x] Run Python 3.11 backend Ruff, mypy, and full pytest regression.
- [x] Apply Alembic `upgrade head` on an empty database and test `0005` → `0006` with a preserved project, new import, export, and integrity check.
- [x] Test stored-root tampering, traversal, directory junctions, archive checksums, missing files, and update/delete/restore safety. No known data-loss defect remains in the tested V1 flows.
- [x] Back up and restore a project into a fresh workspace; compare published PNG and JSON bytes and run **Check files**.
- [x] Cover focused keyboard pixel editing and labels/statuses in automated tests. A real screen-reader session remains a disclosed follow-up, not a claim of coverage.
- [x] Do not claim local AI model readiness: ComfyUI/SD1.5 hardware quality, ControlNet, and IP-Adapter remain optional and separately gated.
- [x] Record warnings and limitations in `docs/sprints/sprint-11.md`; the owner authorized source integration. Tagging still requires separate review.

## Known limitations to disclose

- No model or checkpoint is bundled. ComfyUI, LoRA, ControlNet, and IP-Adapter need separate compatible local installation; ControlNet and IP-Adapter have not been GPU-validated on the target GTX 1070 Ti.
- Browser drafts are device/origin-specific and can lose the most recent stroke before the 500 ms autosave or when storage fails. Published versions are unaffected.
- ZIP backups exclude drafts, cache, and trash and are capped at 128 MB/5,000 files. Restore is into a fresh workspace, not an in-place merge.
- Trash has no in-app restore or automatic purge. Missing published files are reported, not reconstructed.
- Real screen-reader coverage, a second clean physical Windows machine, and broad GPU performance/quality studies remain pending; automated tests do not prove those claims.

## Tagging plan (not executed)

1. Merge the reviewed Sprint 11 branch only after all required gates pass or approved exceptions are recorded.
2. Confirm the target commit, changelog, migration head, schema versions, and clean working tree.
3. Create an annotated `v1.0.0-rc.1` tag on that reviewed commit; publish release notes with the known limitations and exact tested platform.
4. Promote to `v1.0.0` only after RC feedback and owner sign-off. Never retag or force-push an existing release.

## V2 priorities from V1 findings

1. Safer recovery for drafts and deleted projects, including explicit trash restore, without silent data replacement.
2. Manual accessibility audit fixes and broader Windows install/runtime validation.
3. Tested GPU capability matrix and visual-quality iteration for optional ControlNet/IP-Adapter and pixel cleanup on 8 GB VRAM.
4. Larger-project backup strategy beyond the V1 ZIP limit, with versioned migration tooling.
