# Sprint 12: Local LoRA Training Foundation

Status: dataset export and opt-in local CLI preflight/launcher implemented; not a trained-model or V1 production-readiness claim.

## Scope decision

The original master plan places a local LoRA training helper in V3 and excludes full model training from V1. The owner requested LoRA work next, so this is a separate, opt-in post-V1 increment. It does not change Sprint 11's release gates or imply V1 is ready for general distribution.

## First increment

- Curate active published versions in the asset library, edit captions, choose 256 or 512 pixels and an RGB transparency background, then download a local training ZIP.
- `POST /api/v1/projects/{project_id}/lora-dataset` accepts 1–64 explicit version IDs and captions, `resolution` 256/512, and a six-digit `background` RGB value without `#`.
- The ZIP contains `0001.png` etc. as nearest-neighbor, square, RGB images, `metadata.jsonl` with `file_name` and `text`, and `manifest.json` with pinned source IDs and SHA-256 checksums. Original asset files and active versions remain unchanged.
- The API validates project ownership, published-file checksums, image metadata, duplicate selections, path safety, and source-size limits. The ZIP is built in memory and is not uploaded, saved to the project, or sent to a training service.

## Validation and limits

- Focused backend API tests cover output pixels/metadata and refusal of foreign, duplicate, invalid, and changed versions. Frontend component test covers explicit selection and request payload. The Chrome E2E critical path downloads the ZIP before continuing through edit, animation, and export.
- Local checks: 115 backend tests, Ruff, and mypy passed on Python 3.11; 31 frontend tests, ESLint, TypeScript, and Vite build passed on Node 22; both Chrome E2E tests passed against isolated temporary project data.
- The default white background may be inappropriate for some sprite palettes. Review prepared images and captions before training; poor or unlicensed source art should not be included.
- This increment does **not** install a trainer, run a GPU job, convert checkpoints, or create LoRA weights. A ComfyUI-listed LoRA can still be incompatible or visually ineffective. Model licenses, training-image rights, and GPU feasibility require explicit review.

## Second increment: offline CLI launcher

- `python -m app.cli.lora_train` preflights a downloaded studio ZIP, a local Diffusers-format `StableDiffusionPipeline` base directory, a local trainer Python/script, and a new output path outside the repo. Its default mode is read-only.
- Only `--execute --confirm-rights` starts Accelerate with local paths and conservative one-process fp16/rank-4 settings. The CLI sets Hugging Face offline/telemetry-disabled flags, never adds Hub upload arguments, and records dataset/trainer checksums in `run-plan.json`.
- Unit tests use a fake subprocess to verify default no-op, offline environment, extracted data, and rejection of tampered ZIPs or non-SD1.5 pipeline classes. No dependency installation, real GPU execution, trainer trust validation, or successful LoRA inference is claimed.
- An optional `--check-runtime` probes package versions and PyTorch CUDA visibility in the selected trainer Python; `--execute` requires this probe to pass before creating the output folder. A missing dependency or GPU fails closed. This does not validate free VRAM, model compatibility, or the trustworthiness of the Python executable.
- The CLI now writes `run-state.json` atomically for started, process-completed, process-failed, and launch-failed outcomes. It preserves a failed run's output for inspection. Exit code 0 is not proof of useful weights; a crash can leave a stale `started` state, and cancellation/resume are still unimplemented.
- After the process-state increment, backend Ruff and mypy pass with 122 pytest tests; frontend ESLint, TypeScript, Vite build, and 31 Vitest tests pass. The browser E2E path was validated in the first increment and was not rerun for CLI-only changes.
- Usage and limits are in `docs/lora-training.md`. A trusted trainer script can still make its own network calls; the environment flags do not sandbox it.

## Next increment gate

Pin and validate a trainer/dependency version on the target GTX 1070 Ti, then add safe job lifecycle/cancel/resume and a same-seed no-LoRA comparison before calling in-app training supported. Do not enable network publishing or automatic model downloads. The current runtime probe has only fake-subprocess test coverage; no local trainer environment was supplied for a real probe.
