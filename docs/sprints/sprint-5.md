# Sprint 5: ComfyUI and SD1.5 Baseline

## Goal

Connect the provider-neutral queue to a local ComfyUI installation using an explicit, versioned SD1.5 baseline without downloading or bundling models.

## Completed scope

- Opt-in ComfyUI provider selected with `AI_SPRITE_AI_PROVIDER=comfyui`; fake remains default.
- ComfyUI health check, prompt submission, history polling, PNG retrieval, timeout, and actionable offline errors.
- Versioned `sd15-text-to-sprite-v1` workflow template and configurable checkpoint alias.
- Seed, prompt ID, checkpoint, and workflow metadata persistence.
- Generated candidate acceptance as an immutable asset version linked to its generation job.
- Dashboard provider health and explicit configuration messaging.

## Deferred scope

- LoRA, IP-Adapter, ControlNet, and inpainting remain Sprint 7.
- Rich presets and four specialized generation forms remain Sprint 6.
- Model download and installation automation are intentionally excluded.

## Technical decisions

- HTTP history polling is the stable baseline; WebSocket progress can be added without changing the domain contract.
- ComfyUI workflow JSON stays inside the backend adapter.
- The fake provider remains available for development, tests, and systems without GPU support.

## Migration and format changes

- Migration `0004` links asset versions to generation jobs through nullable `generation_id`.
- Environment adds `AI_SPRITE_AI_PROVIDER` and `AI_SPRITE_COMFYUI_CHECKPOINT`.

## Tests and validation

- Mocked adapter tests cover workflow mapping, history/result retrieval, and offline health.
- Integration tests cover candidate acceptance and immutable generated versions.

## Manual verification

Install ComfyUI separately, place a licensed SD1.5-compatible checkpoint in ComfyUI, set the provider and checkpoint environment values, start ComfyUI on loopback, and verify health before submitting a low-resolution batch-one job.

## Known issues

- The baseline workflow assumes standard built-in ComfyUI nodes.
- Progress is coarse while HTTP polling is used.
- Generated candidate dimensions must match the target asset to be accepted.

## Risks and next recommendation

Never auto-download models or execute untrusted workflows. Validate the baseline manually on the GTX 1070 Ti with conservative dimensions before expanding Sprint 6 presets.
