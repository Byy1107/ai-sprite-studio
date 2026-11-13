# Sprint 7: Reference Consistency and AI-Assisted Edit

Status: Sprint 7 acceptance criteria complete locally; optional GPU/model quality
validation remains partial.
Reference versioning, capability discovery, LoRA, prepared-image ControlNet,
optional IP-Adapter, inpainting and variations are implemented. None of these
optional workflows is claimed to work with arbitrary model combinations.

Validation before publication: 66 backend tests and 13 frontend tests passed,
along with lint, type checks and the production frontend build.
Current local validation: 86 backend tests and 15 frontend tests passed;
Ruff, Mypy, TypeScript, ESLint and the production frontend build passed.

## Sprint 7 acceptance checklist

- Missing optional nodes/models leave ordinary generation and the editor usable;
  optional requests fail explicitly instead of silently dropping settings.
- Queued requests persist a pinned reference version, weight, LoRA selection,
  ControlNet settings and any IP-Adapter model choices.
- Inpainting composites only the selected candidate rectangle over the pinned
  source; outside pixels are exact copies, including in the local GPU run.
- Original and active versions are unchanged until candidate acceptance.
- Optional node/model setup and limitations are documented in
  [Windows setup](../setup-windows.md).

These are the Sprint 7 criteria from the master plan. They do not certify a
specific optional model pair or guarantee polished pixel art from SD1.5.

## First increment

- Pin an optional reference to an immutable asset version when queuing a job.
- Validate target and reference ownership, existence, and deletion state.
- Persist the reference identity and weight for reproducibility.
- Report explicitly that the baseline providers do not apply reference conditioning.
- Preserve existing text generation and candidate-only publication.

## Local GPU validation (2026-11-13)

- Windows, GTX 1070 Ti 8 GB, local ComfyUI 0.45.0 and an SD1.5 FP16 checkpoint;
  FastAPI used the ComfyUI provider, not the fake fallback.
- The application API completed one 128×128 baseline item job, one whole-image
  variation and one rectangular inpaint job. Each returned a PNG candidate.
- The baseline candidate did not change the active asset version until explicitly
  accepted. Variation and inpaint candidates left that active version unchanged.
  Inpaint output pixels outside the selected rectangle matched the pinned source.
- These are functional integration results, not a visual-quality pass: the three
  outputs were abstract color blobs rather than recognizable pixel-art items.
  Direct 128×128 SD1.5 sampling needs workflow/quality improvements before use.
- A second local test used 512×512 SD1.5 inference and nearest-neighbor resizing
  to 128×128. The baseline item silhouette became recognizable, and the full
  application baseline/variation/inpaint sequence passed again. The background
  remains noisy. At this stage variation and inpaint still sampled at source size.
- A third test scaled the pinned source and rectangular mask to 512×512 for
  variation and inpaint, then reduced each candidate to 128×128. Both jobs
  succeeded through the application API; the sword silhouette remained
  recognizable in both outputs. Pixels outside the inpaint selection still
  matched the pinned source exactly, and the active version did not change.
  Backgrounds remain noisy, so this is not final pixel-art quality acceptance.
- A later real LoRA job on the same GPU exposed silent incompatibility: an
  SD1.5 Diffusers-format LoRA was listed and its job succeeded, but its image
  was pixel-identical to the no-LoRA baseline at the same seed. A locally
  converted ComfyUI-format copy changed the output, proving the loader path
  can work, but the resulting image was worse. Neither file is in Git.
  Metadata now distinguishes a wired node from verified application; the
  adapter cannot assert the latter from a successful ComfyUI job.
- ControlNet and IP-Adapter were not exercised on GPU because compatible
  optional models/nodes were not installed. No optional workflow is claimed
  to work with arbitrary model combinations.
- Failed ComfyUI history entries now surface their execution error instead of
  raising an opaque empty-output exception; completed jobs without a saved
  image fail explicitly. Result retrieval uses the designated SaveImage node,
  even when other nodes also appear in history output.

## V1 quality follow-up outside Sprint 7 acceptance

- Improve background cleanup and verify useful pixel-art output on the target GPU.
  ControlNet and IP-Adapter GPU quality/VRAM validation still require compatible
  optional models/nodes. LoRA loader execution has been validated with a converted
  local model, but no tested LoRA improves visual quality. No model download is
  performed by this repository.

## Third increment: conservative capability discovery

`GET /api/v1/system/ai/capabilities` reports provider, discovery status,
known detected nodes and enabled features. Fake mode performs no network request.
ComfyUI discovery uses its local `/object_info` endpoint with a three-second timeout.
Missing nodes, malformed responses and an offline server leave features disabled.
Node presence alone does not verify model availability or workflow compatibility.
LoRA and ControlNet selection require their loader inputs and model names in the
node catalogue. ControlNet also requires LoadImage and ControlNetApplyAdvanced.
IP-Adapter and image-edit features are advertised only when their required
nodes and local model choices are found; this is discovery, not GPU validation.
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
- LoRA loader execution was verified on the target GPU with a locally converted
  SD1.5 model. Arbitrary model compatibility and visual quality are not assured.

See [Windows LoRA setup](../setup-windows.md#optional-lora).

## Fifth increment: historical references

- The reference picker lists immutable versions and previews the selected version.
- Selecting an asset snapshots its active version immediately; background asset refreshes
  no longer switch an already selected reference to a newer active version.
- Selecting another asset resets the version to that asset's active version.
- History-loading failures preserve the pinned reference and show an error.
- Clearing the asset clears the submitted version.

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
- Reference weight is used by IP-Adapter, not ControlNet, which has its own strength.
- Fake mode rejects ControlNet requests; missing nodes/models fail explicitly without
  silently dropping the option. Users can select No ControlNet to use text generation.
- Candidate generation preserves the original and active versions until acceptance.
- Mocked tests cover workflow wiring, upload validation, missing nodes, pinned bytes,
  checksum changes, interval validation, request persistence and UI submission.
- Actual GPU execution, visual quality and model compatibility remain unverified.

ComfyUI keeps the uploaded copy in its input folder, including when a later job fails.
The application does not automatically delete server inputs, as workflows may reuse them.
See [Windows ControlNet setup](../setup-windows.md#optional-controlnet).

## Seventh increment: IP-Adapter and AI-assisted editing

- Discovery lists compatible-looking local IP-Adapter and CLIP vision model names
  only when the required custom/built-in nodes and inputs are advertised.
- The generator requires both model choices and a pinned reference version;
  execution revalidates the catalogue and uploaded reference bytes before wiring
  IPAdapterModelLoader, CLIPVisionLoader, LoadImage and IPAdapterAdvanced.
- The pixel editor can queue a whole-image variation or select a rectangular
  region for inpainting against the latest published asset version. Unsaved
  manual changes must be published first.
- Variation uses VAEEncode and partial denoising. Inpainting uses
  VAEEncodeForInpaint with an uploaded selection mask. Returned PNG dimensions
  are checked, and inpaint candidates are composited against the pinned source
  so pixels outside the rectangle remain identical.
- Generated output remains a candidate. The active asset version changes only
  when the user explicitly accepts it. Fake mode and missing optional nodes fail
  explicitly; neither silently substitutes text-only generation.
- API, workflow, pixel-compositing and UI tests cover the optional paths. This
  is mocked acceptance, not proof of model compatibility or GPU output quality.

See [Windows IP-Adapter and AI edit setup](../setup-windows.md#optional-ip-adapter-and-ai-edit).
