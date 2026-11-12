# Sprint 7: Reference Consistency and AI-Assisted Edit

Status: in progress. This publication contains reference versioning, capability
discovery, LoRA and prepared-image ControlNet. IP-Adapter, inpainting, variations
and real GPU validation remain pending.

Validation before publication: 66 backend tests and 13 frontend tests passed,
along with lint, type checks and the production frontend build.

## First increment

- Pin an optional reference to an immutable asset version when queuing a job.
- Validate target and reference ownership, existence, and deletion state.
- Persist the reference identity and weight for reproducibility.
- Report explicitly that the baseline providers do not apply reference conditioning.
- Preserve existing text generation and candidate-only publication.

## Remaining work

- Optional IP-Adapter capability detection and workflow.
- Real GPU validation of LoRA and ControlNet with compatible local models.
- Editor selection masks, inpainting and variations.
- Optional node/model setup documentation and end-to-end acceptance tests.

## Third increment: conservative capability discovery

`GET /api/v1/system/ai/capabilities` reports provider, discovery status,
known detected nodes and enabled features. Fake mode performs no network request.
ComfyUI discovery uses its local `/object_info` endpoint with a three-second timeout.
Missing nodes, malformed responses and an offline server leave features disabled.
Node presence alone does not verify model availability or workflow compatibility.
LoRA and ControlNet selection require their loader inputs and model names in the
node catalogue. ControlNet also requires LoadImage and ControlNetApplyAdvanced.
IP-Adapter and inpainting remain disabled until integrated and tested.
No automatic fallback silently replaces real generation with mock output.

API reference: https://docs.comfy.org/development/comfyui-server/comms_routes

## Acceptance for this increment

- Missing, deleted and foreign-project assets cannot be queued as references or targets.
- A selected version must belong to its reference asset.
- Queuing snapshots the active reference version; later edits cannot change the request.
- Invalid weights fail validation; the baseline result discloses ignored conditioning.
- No models are downloaded and no active asset version changes before acceptance.

This increment does not claim functional reference-guided AI generation or completion of Sprint 7.

## Second increment

- Generator includes a project-local reference picker, pixelated preview and weight input.
- Requests explicitly pin the displayed version, rather than resolving a newer version silently.
- Clearing the reference clears its version; switching project or preset resets the picker.
- UI explains that baseline providers store settings but do not apply reference conditioning.
- Asset-loading errors are shown without preventing ordinary text generation.

## Fourth increment: LoRA workflow

- Capability discovery exposes local LoRA names; the generator offers one model and a 0–2 weight.
- Requests persist `lora_name` and `lora_weight` in existing request JSON, without a migration.
- ComfyUI inserts a built-in LoraLoader between the checkpoint and both sampler/text encoders.
- The same weight applies to model and CLIP. Zero is supported; no selection uses the baseline.
- Execution refreshes the catalogue and rejects a missing loader/model before submitting a prompt.
- Fake mode rejects LoRA requests with 422 rather than claiming to apply a model.
- Job workflow identity and result metadata distinguish the LoRA variant.
- Mocked transport tests cover wiring, missing models, persistence, validation and UI selection.
- Actual SD1.5 generation and model compatibility remain unverified on the target GPU.

See [Windows LoRA setup](../setup-windows.md#optional-lora).

## Fifth increment: historical references

- The reference picker lists immutable versions and previews the selected version.
- Selecting an asset snapshots its active version immediately; background asset refreshes
  no longer switch an already selected reference to a newer active version.
- Selecting another asset resets the version to that asset's active version.
- History-loading failures preserve the pinned reference and show an error.
- Clearing the asset clears the submitted version. IP-Adapter reference conditioning remains pending.

## Sixth increment: ControlNet with a prepared control image

- Discovery returns `controlnet_models` and enables selection only when the loader,
  image loader and conditioning node inputs are advertised.
- Requests persist `controlnet_name`, `controlnet_strength` (0–2),
  `controlnet_start` and `controlnet_end` (0–1, start strictly before end).
- ControlNet requires a reference asset; its immutable version is pinned at queue time.
- Before execution the service rechecks ownership, deletion state, project path,
  PNG validity and checksum. Missing or modified references fail before upload.
- The adapter uploads a uniquely named copy to ComfyUI input/ai-sprite-studio without
  overwrite, then wires LoadImage, ControlNetLoader and ControlNetApplyAdvanced.
- Both positive and negative conditioning are connected. LoRA and ControlNet can be combined.
- The prepared image is used directly; automatic edge/depth/pose preprocessing is not implemented.
- Reference weight is reserved for future IP-Adapter; ControlNet uses its own strength.
- Fake mode rejects ControlNet requests; missing nodes/models fail explicitly without
  silently dropping the option. Users can select No ControlNet to use text generation.
- Candidate generation preserves the original and active versions until acceptance.
- Mocked tests cover workflow wiring, upload validation, missing nodes, pinned bytes,
  checksum changes, interval validation, request persistence and UI submission.
- Actual GPU execution, visual quality and model compatibility remain unverified.

ComfyUI keeps the uploaded copy in its input folder, including when a later job fails.
The application does not automatically delete server inputs, as workflows may reuse them.
See [Windows ControlNet setup](../setup-windows.md#optional-controlnet).
