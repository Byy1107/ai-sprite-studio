# Preparing Local LoRA Data

The studio can prepare a captioned dataset from immutable published PNG versions. A separate, opt-in CLI can preflight and launch a locally supplied trainer, but no trainer, model, or weights are installed by the studio. See `docs/sprints/sprint-12.md` for the current scope.

1. Import or publish artwork you own or have permission to train on. Review each image at native pixel size.
2. Open the project, scroll to **Prepare LoRA training data**, select the active versions you want, and edit each caption. The UI never selects artwork automatically.
3. Choose 256×256 or 512×512 and an explicit RGB background for transparent pixels. Download the ZIP and inspect the PNGs and `metadata.jsonl` before using them with any trainer. The pixels are scaled with nearest-neighbor and centered; they are not AI-cleaned.
4. Keep the ZIP and any base model outside Git. Do not assume a ComfyUI `.safetensors` checkpoint is a Diffusers-format training directory or that a successful loader job proves the LoRA changed the image.

The archive uses ImageFolder-style `metadata.jsonl` rows with `file_name` and `text` captions, matching the default caption column of the [Diffusers text-to-image LoRA example](https://github.com/huggingface/diffusers/blob/main/examples/text_to_image/train_text_to_image_lora.py). This is a data format, **not** an approved training command for the target GPU. The archive includes at most 64 selected images from one project; source PNG bytes are capped at 64 MB in aggregate and 16 MB each. It is generated in memory and does not modify the project.

## Optional Windows training CLI

Use a **trusted** copy of the [Diffusers text-to-image LoRA script](https://github.com/huggingface/diffusers/blob/main/examples/text_to_image/train_text_to_image_lora.py) and its dependencies in a separate local Python environment. The base model must already exist as an unpacked Diffusers `StableDiffusionPipeline` directory with UNet, VAE, text encoder, tokenizer, and scheduler components; a single ComfyUI `.safetensors` checkpoint is **not** accepted. Verify the model license and image training rights yourself. Keep the ZIP, model, trainer environment, and output **outside the repository**.

From `apps/api`, run the preflight first (PowerShell example; replace all paths):

```powershell
& .\.venv\Scripts\python.exe -m app.cli.lora_train --dataset-zip 'C:\AI\dataset.zip' --base-model 'C:\AI\sd15-diffusers' --trainer-script 'C:\AI\diffusers\examples\text_to_image\train_text_to_image_lora.py' --trainer-python 'C:\AI\trainer-venv\Scripts\python.exe' --output-dir 'C:\AI\runs\sprite-lora-001' --max-steps 200
```

Preflight validates archive integrity, captions, PNG dimensions, model layout, input paths, and a new output location. Add `--check-runtime` to run a **separate, optional** probe in the trainer environment: it checks installed package versions and whether PyTorch sees a CUDA GPU, without loading the model or starting training. A plain preflight does not execute the trainer Python. `--execute` always runs this probe first and refuses to create an output folder if packages or CUDA are missing. The probe is not a VRAM, model-compatibility, or LoRA-convergence test. It does execute the selected Python interpreter, so use only a trainer environment you trust.

Only after reviewing the inputs, run the **same command** with `--execute --confirm-rights` appended. The launcher uses one process, fp16, batch size 1, gradient accumulation/checkpointing and rank 4; these conservative settings are not a GTX 1070 Ti success guarantee. It creates a separate output folder containing `run-plan.json` (including detected package/GPU information), extracts the dataset into a temporary folder, and invokes the local script via Accelerate. `run-state.json` starts as `started`, then records `process_completed` with exit code 0, `process_failed` with a nonzero code, or `launch_failed` if the process cannot start. A zero exit code **does not** verify that usable LoRA weights were produced or improve image quality. If the machine or parent process crashes, `started` may remain stale; inspect local processes and output manually rather than assuming training is still running. No download or cloud upload is requested. The child receives Hugging Face offline and telemetry-disable environment flags, but those flags are **not** an OS-level network sandbox for an untrusted trainer script. [Accelerate supports the Python-module launcher](https://huggingface.co/docs/accelerate/basic_tutorials/launch); [Hugging Face documents `HF_HUB_OFFLINE`](https://huggingface.co/docs/huggingface_hub/en/package_reference/environment_variables).

Do not put output or private paths in Git. A failed/interrupted job leaves its output directory for inspection; the CLI does not yet implement cancellation, resume, automatic cleanup, checkpoint conversion to ComfyUI, or same-seed no-LoRA comparison. Train only with a script and model you trust. No real GPU run has been validated for this increment.
