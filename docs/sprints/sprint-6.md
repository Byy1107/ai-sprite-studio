# Sprint 6: Specialized Generators and Presets

## Goal

Provide focused character, item, environment, and tileset generation modes without coupling the UI to ComfyUI workflows or downloading models.

## Completed scope

- Versioned backend preset registry exposed through `GET /api/v1/generation-presets`.
- Two presets for each asset type with safe default dimensions, style, positive prompt, and negative prompt.
- Four focused UI modes with contextual creative-direction fields and asset-type filtering.
- Optional Akar Langit dark-fantasy character preset.
- Preset identity and negative prompts persist in generation requests and provider metadata.
- Backend validation prevents applying a preset to the wrong asset type.

## Deferred scope

- LoRA, IP-Adapter, ControlNet, references, and inpainting remain Sprint 7.
- Animation and movesets remain later milestones.
- Model installation and automatic downloads remain intentionally excluded.

## Acceptance criteria

- All four generator modes can queue jobs through the fake provider without a GPU.
- ComfyUI receives positive and negative prompts when explicitly enabled.
- Presets remain provider-neutral and React never receives workflow JSON.
- Existing generated-candidate acceptance and immutable asset versioning continue to work.

## Safety

Preset text is application data, not an executable ComfyUI workflow. The fake provider remains the default, and the repository includes no checkpoint or generated user asset.
