# Windows Development Setup

## Supported baseline

- Windows 10/11 64-bit with current security updates.
- Git.
- Node.js 20, 22, or 24 LTS.
- pnpm 10 via Corepack or a trusted local installation.
- Python 3.11 64-bit.

The target machine may also contain newer Node or Python versions, but validation uses the supported baseline above. ComfyUI and model downloads are not required.

## Clone and environment

```powershell
git clone <repository-url> ai-sprite-studio
cd ai-sprite-studio
Copy-Item .env.example .env.local
```

Review `.env.local`. Relative workspace and database paths are suitable for development. Keep this file out of Git.

## Frontend

```powershell
corepack enable
corepack prepare pnpm@10.11.0 --activate
pnpm install
pnpm dev:web
```

The frontend runs at `http://127.0.0.1:5173` and proxies `/api` to the local backend.

## Backend

```powershell
cd apps/api
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m alembic upgrade head
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Check `http://127.0.0.1:8000/api/v1/health` or the interactive API page at `http://127.0.0.1:8000/api/docs`.
Then follow `docs/user-guide.md` to create a project, import a PNG, and download a first export. This path uses the fake provider and requires no GPU or checkpoint.

If PowerShell blocks virtual-environment activation, run the interpreter directly:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

If the `py` launcher is unavailable, create `.venv` with your installed Python 3.11 executable directly. Verify `python --version` inside that environment before installing dependencies; Python 3.12+ is outside the supported V1 matrix.

Project metadata and files remain local. Configure `AI_SPRITE_DATABASE_URL` and `AI_SPRITE_WORKSPACE_DIR` in `.env.local`; never commit the database or project workspace.
Before upgrading an existing installation, stop the API and back up both SQLite and the workspace; see `docs/project-format.md` for the V1 format and migration policy.

## Optional ComfyUI setting

ComfyUI is not required. Keep `AI_SPRITE_AI_PROVIDER=fake` for deterministic local development without a GPU. To opt in, install ComfyUI separately, place a licensed SD1.5-compatible checkpoint in its checkpoint directory, and configure:

```text
AI_SPRITE_AI_PROVIDER=comfyui
AI_SPRITE_COMFYUI_HTTP_URL=http://127.0.0.1:8188
AI_SPRITE_COMFYUI_CHECKPOINT=your-checkpoint.safetensors
```

The app submits a versioned built-in workflow and never downloads model files. Generation and AI edits sample at up to 512 pixels on the longest side, then use nearest-neighbor resizing to the requested canvas; a 32x32 output still requires roughly 512x512 inference memory. Edits upscale the pinned source and selection mask together. Start with one candidate and inspect the result before accepting it. The dashboard reports whether the selected provider is ready.

## Troubleshooting

For optional LoRA setup, see the section below.

- Use `node --version`, `pnpm --version`, and `py -3.11 --version` to verify tools.
- Install Python 3.11 alongside newer Python versions and always create the virtual environment with `py -3.11`.
- Keep Windows fully updated if a terminal reports Control-flow Enforcement Technology (CET) compatibility errors.
- Ensure ports 5173 and 8000 are free and do not expose them through firewall rules.

## Optional LoRA

Use the existing ComfyUI installation and an SD1.5-compatible checkpoint. Place a
licensed, SD1.5-compatible LoRA in `ComfyUI/models/loras` (subfolders are supported),
then refresh ComfyUI or restart it so its model list updates. No custom node is
required for the built-in `LoraLoader`.

With the backend provider set to `comfyui`, select **Refresh AI capabilities** in
the generator. Select the listed LoRA and its weight, then generate one candidate.
The weight affects both MODEL and CLIP; **No LoRA** restores the baseline workflow.
The app reads model names from ComfyUI and does not download or copy model files.

If no model is listed, verify the file location and the selected provider.
If a file disappears after selection, the job fails with an actionable error and
does not silently generate without that LoRA. Existing asset versions remain intact.
Detection confirms that the loader and name are advertised; it cannot verify
SD1.5 compatibility, tensor-key mapping or successful loading into GPU memory.
ComfyUI may complete a job while silently ignoring incompatible LoRA tensors.
Compare identical prompt, seed and settings with **No LoRA**; a successful job
or `lora_node_wired` metadata alone does not prove the weights affected pixels.
Result metadata reports `lora_applied: null` for a selected LoRA because the
adapter cannot independently verify that ComfyUI matched its tensor keys.

Baseline and one local SD1.5 LoRA were exercised on the GTX 1070 Ti. The original
Diffusers-format LoRA produced pixels identical to the baseline despite a
successful job; a locally converted ComfyUI-format copy changed the pixels but
worsened visual quality. Neither file is included in the repository or
recommended as a default. Verify baseline generation first, then test a
compatible LoRA and inspect the candidate before accepting it. IP-Adapter and
inpainting are optional, separately gated workflows; neither is required for
LoRA use.

Reference: [ComfyUI LoRA node](https://docs.comfy.org/built-in-nodes/LoraLoader).

## Optional ControlNet

First verify plain SD1.5 generation in your separate ComfyUI installation. Place a
licensed SD1.5-compatible ControlNet model in `ComfyUI/models/controlnet`, then
refresh or restart ComfyUI. The application uses the built-in ControlNetLoader,
ControlNetApplyAdvanced and LoadImage nodes; no extra preprocessor node is required.

Import a prepared PNG control image into the same project. For example, use an edge
map for an edge ControlNet, or an appropriate pose/depth map for that model family.
Select its asset and version in the generator's reference library. The application
uses these pixels directly; it does not infer an edge, pose or depth map from a sprite.
Align the control map's framing and aspect ratio with the intended output.

With the provider set to `comfyui`, refresh AI capabilities, choose the ControlNet
model and adjust strength and start/end fractions. Start must be less than end.
These fractions specify when guidance is active during sampling; they are not animation
timings. The separate reference-weight control affects IP-Adapter only and does
not affect ControlNet.

Generate a single candidate and inspect it before accepting. Start with ControlNet alone
before combining it with LoRA. Detection does not verify compatibility, visual quality,
VRAM capacity or successful GPU execution. Real testing on the target GTX 1070 Ti is
still pending; no model files are downloaded by this feature.

A missing model, unreadable or changed reference, or failed upload produces a failed
job. Refresh the catalogue, correct the reference, or choose No ControlNet to continue
with ordinary generation. The source asset remains unchanged. ComfyUI retains uploaded
copies in `input/ai-sprite-studio`; manage those copies separately when no workflows use them.

References: [ControlNet loader](https://docs.comfy.org/built-in-nodes/ControlNetLoader),
[Apply ControlNet](https://docs.comfy.org/built-in-nodes/ControlNetApplyAdvanced).

## Optional IP-Adapter and AI edit

Keep the fake provider for ordinary offline development. To try these workflows,
first verify a plain candidate with a separately installed ComfyUI and a licensed
SD1.5-compatible checkpoint. No model or custom node is installed by this app.
For IP-Adapter, install the upstream
[ComfyUI_IPAdapter_plus](https://github.com/cubiq/ComfyUI_IPAdapter_plus)
custom nodes following that project's instructions. Supply licensed, compatible
IP-Adapter and CLIP vision model files in the directories documented upstream;
restart ComfyUI and select **Refresh AI capabilities**. The generator lists only
models advertised by the local node catalogue. Choose a project-local reference
asset and immutable version, then select both the IP-Adapter and CLIP vision
models. The reference-weight input controls IP-Adapter strength. **No IP-Adapter**
returns to the baseline workflow. Catalogue discovery does not prove that the
model pair is compatible or fits in VRAM.

For variation or inpainting, open a published asset in the pixel editor. The
backend requires ComfyUI's LoadImage, VAEEncode and VAEEncodeForInpaint nodes
respectively. Enter a prompt and seed. **Generate variation** applies to the
whole source; for **Inpaint selection**, use **Select region** to drag a rectangle
over the canvas first. Publish any manual changes before queuing an AI edit.
The editor pins the latest published version, not an unsaved draft. The result
is a reviewable candidate; accepting it creates a new asset version. For
inpainting, the app restores all pixels outside the selected rectangle from
the pinned source even if the provider changes them.

Missing nodes, model names, a changed source file or an offline ComfyUI cause
an explicit unavailable/failed state; no text-only or fake result is silently
substituted. ComfyUI retains uploaded reference and mask copies under
`input/ai-sprite-studio`; manage them separately. Start with one small sprite
on the GTX 1070 Ti and inspect both output and memory use. Variation and inpaint
completed on this machine at 512x512 inference; the edited sword silhouette
remained recognizable, but noisy backgrounds and pixel-art cleanup remain.

## ComfyUI troubleshooting for V1

- **Provider unavailable:** Confirm ComfyUI is running only on your local machine at the configured `AI_SPRITE_COMFYUI_HTTP_URL`, and that the backend uses `AI_SPRITE_AI_PROVIDER=comfyui`. Restart the API after changing `.env.local`, then refresh AI capabilities. Switch back to `fake` to continue project work without a GPU.
- **Checkpoint missing:** Put a licensed SD1.5-compatible file in ComfyUI's checkpoints directory, refresh/restart ComfyUI, and set `AI_SPRITE_COMFYUI_CHECKPOINT` to the exact advertised name. The studio does not download it for you.
- **Out of memory:** Stop other GPU-heavy processes, disable optional adapters, and submit one candidate at a time. Merely selecting a smaller final sprite does not eliminate the 512-pixel inference workload. An OOM job should fail without changing the active asset version; inspect its error before retrying.
- **LoRA job succeeds but looks unchanged:** Compare the same prompt and seed with and without the LoRA. Check SD1.5 compatibility and tensor-key format; a wired loader is not proof that weights affected pixels.
- **ControlNet or IP-Adapter unavailable:** Install compatible local models and required nodes separately, restart ComfyUI, and refresh the catalogue. Supply an appropriate prepared control/reference PNG; the studio does not synthesize a control map automatically.
- **Pinned reference changed or vanished:** Reimport or restore the missing file from a verified backup, then select a valid published version. The app refuses a changed checksum rather than silently using different pixels.

Do not expose the API or ComfyUI to a network as a troubleshooting shortcut. See `docs/release-checklist.md` for V1 limitations and `docs/project-format.md` before migrating an existing workspace.

