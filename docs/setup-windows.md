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

If PowerShell blocks virtual-environment activation, run the interpreter directly:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Project metadata and files remain local. Configure `AI_SPRITE_DATABASE_URL` and `AI_SPRITE_WORKSPACE_DIR` in `.env.local`; never commit the database or project workspace.

## Optional ComfyUI setting

ComfyUI is not required. Keep `AI_SPRITE_AI_PROVIDER=fake` for deterministic local development without a GPU. To opt in, install ComfyUI separately, place a licensed SD1.5-compatible checkpoint in its checkpoint directory, and configure:

```text
AI_SPRITE_AI_PROVIDER=comfyui
AI_SPRITE_COMFYUI_HTTP_URL=http://127.0.0.1:8188
AI_SPRITE_COMFYUI_CHECKPOINT=your-checkpoint.safetensors
```

The app submits a versioned built-in workflow and never downloads model files. Start with a 32x32 or 64x64 single-image job. The dashboard reports whether the selected provider is ready.

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
SD1.5 compatibility or successful loading into GPU memory.

The GTX 1070 Ti machine has not yet been used for real LoRA validation. Verify
baseline generation first, then test one compatible LoRA and inspect the candidate
before accepting it. IP-Adapter and inpainting remain pending Sprint 7 work.

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
timings. The separate reference-weight control is reserved for IP-Adapter and does
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

