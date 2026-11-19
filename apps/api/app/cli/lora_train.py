import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

MAX_ARCHIVE_BYTES = 96 * 1024 * 1024
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
RUNTIME_PROBE = """
import json
from importlib.metadata import version
import torch
packages = {name: version(name) for name in (
    "torch", "accelerate", "diffusers", "datasets", "transformers", "peft"
)}
print(json.dumps({
    "packages": packages,
    "cuda_available": torch.cuda.is_available(),
    "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
}))
"""


@dataclass(frozen=True)
class DatasetSummary:
    resolution: int
    image_names: tuple[str, ...]
    captions: tuple[str, ...]


def inspect_dataset(archive_path: Path) -> DatasetSummary:
    if not archive_path.is_file() or archive_path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("Dataset ZIP is missing or exceeds the 96 MB safety limit.")
    try:
        with zipfile.ZipFile(archive_path) as archive:
            entries = archive.infolist()
            if (len(entries) < 3 or len(entries) > 66
                    or len({entry.filename for entry in entries}) != len(entries)
                    or sum(entry.file_size for entry in entries) > MAX_ARCHIVE_BYTES):
                raise ValueError("Dataset ZIP has duplicate, excessive, or oversized entries.")
            names = {entry.filename for entry in entries}
            if any(entry.is_dir() or "/" in entry.filename or "\\" in entry.filename
                   for entry in entries):
                raise ValueError("Dataset ZIP contains an unsafe path.")
            if "metadata.jsonl" not in names or "manifest.json" not in names:
                raise ValueError("Dataset ZIP needs metadata.jsonl and manifest.json.")
            manifest: dict[str, Any] = json.loads(archive.read("manifest.json"))
            resolution = manifest.get("resolution")
            samples = manifest.get("samples")
            if (manifest.get("format_version") != 1 or resolution not in (256, 512)
                    or not isinstance(samples, list) or not 1 <= len(samples) <= 64):
                raise ValueError("Dataset manifest format is unsupported.")
            image_names = tuple(f"{index:04d}.png" for index in range(1, len(samples) + 1))
            if names != {*image_names, "metadata.jsonl", "manifest.json"}:
                raise ValueError("Dataset ZIP files do not match the manifest.")
            metadata = archive.read("metadata.jsonl").decode("utf-8").splitlines()
            if len(metadata) != len(samples):
                raise ValueError("Dataset caption count does not match image count.")
            captions: list[str] = []
            for filename, sample, line in zip(image_names, samples, metadata, strict=True):
                row = json.loads(line)
                if (not isinstance(sample, dict) or sample.get("file_name") != filename
                        or not isinstance(row, dict) or row.get("file_name") != filename
                        or not isinstance(row.get("text"), str)
                        or not 1 <= len(row["text"].strip()) <= 240):
                    raise ValueError("Dataset caption or image order is invalid.")
                content = archive.read(filename)
                if (len(content) > 8 * 1024 * 1024
                        or hashlib.sha256(content).hexdigest() != sample.get("prepared_sha256")):
                    raise ValueError("Dataset image checksum or size is invalid.")
                try:
                    with Image.open(BytesIO(content)) as image:
                        image.load()
                        if image.format != "PNG" or image.mode != "RGB" or image.size != (
                            resolution, resolution
                        ):
                            raise ValueError("Dataset image format or dimensions are invalid.")
                except (OSError, UnidentifiedImageError) as error:
                    raise ValueError("Dataset image is unreadable.") from error
                captions.append(row["text"].strip())
            return DatasetSummary(resolution, image_names, tuple(captions))
    except (zipfile.BadZipFile, UnicodeError, json.JSONDecodeError, KeyError) as error:
        raise ValueError("Dataset ZIP is corrupt or has invalid metadata.") from error


def inspect_base_model(model_dir: Path) -> None:
    required = (
        "model_index.json", "unet/config.json", "vae/config.json",
        "text_encoder/config.json", "tokenizer/tokenizer_config.json",
        "scheduler/scheduler_config.json",
    )
    if not model_dir.is_dir() or any(not (model_dir / item).is_file() for item in required):
        raise ValueError("Base model must be a complete local Diffusers SD1.5 directory.")
    try:
        model_index = json.loads((model_dir / "model_index.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("Base model index is unreadable.") from error
    if model_index.get("_class_name") != "StableDiffusionPipeline":
        raise ValueError("Only local StableDiffusionPipeline-format base models are supported.")
    for component in ("unet", "vae", "text_encoder"):
        directory = model_dir / component
        if not any(path.suffix in {".safetensors", ".bin"} for path in directory.iterdir()):
            raise ValueError(f"Base model is missing {component} weights.")


def inspect_paths(
    archive_path: Path, model_dir: Path, trainer_script: Path,
    trainer_python: Path, output_dir: Path,
) -> DatasetSummary:
    summary = inspect_dataset(archive_path)
    inspect_base_model(model_dir)
    if not trainer_script.is_file() or trainer_script.name != "train_text_to_image_lora.py":
        raise ValueError("Select a local Diffusers train_text_to_image_lora.py script.")
    if not trainer_python.is_file():
        raise ValueError("Select the Python executable of a separate local trainer environment.")
    destination = output_dir.resolve()
    if (output_dir.exists() or not output_dir.parent.is_dir()
            or destination.is_relative_to(REPOSITORY_ROOT)
            or destination.is_relative_to(model_dir.resolve())):
        raise ValueError("Output must be a new directory outside the repository and base model.")
    return summary


def training_command(
    trainer_python: Path, trainer_script: Path, model_dir: Path,
    dataset_dir: Path, output_dir: Path, resolution: int, max_steps: int,
) -> list[str]:
    if not 1 <= max_steps <= 2000:
        raise ValueError("Training steps must be between 1 and 2000.")
    return [
        str(trainer_python.resolve()), "-m", "accelerate.commands.launch",
        "--num_processes=1", "--num_machines=1", "--mixed_precision=fp16",
        str(trainer_script.resolve()),
        "--pretrained_model_name_or_path", str(model_dir.resolve()),
        "--train_data_dir", str(dataset_dir), "--caption_column", "text",
        "--resolution", str(resolution), "--train_batch_size", "1",
        "--gradient_accumulation_steps", "4", "--gradient_checkpointing",
        "--rank", "4", "--max_train_steps", str(max_steps),
        "--learning_rate", "0.0001", "--lr_scheduler", "constant",
        "--lr_warmup_steps", "0", "--report_to", "none",
        "--seed", "42", "--output_dir", str(output_dir.resolve()),
    ]


def offline_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.update({
        "HF_HUB_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1", "HF_HUB_DISABLE_IMPLICIT_TOKEN": "1",
        "HF_HUB_DISABLE_TELEMETRY": "1", "DO_NOT_TRACK": "1",
        "WANDB_MODE": "disabled", "TOKENIZERS_PARALLELISM": "false",
    })
    return environment


def inspect_trainer_runtime(trainer_python: Path) -> dict[str, Any]:
    try:
        result = subprocess.run(
            [str(trainer_python.resolve()), "-I", "-c", RUNTIME_PROBE],
            env=offline_environment(), capture_output=True, text=True,
            timeout=45, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError(
            "Trainer Python could not complete the 45-second runtime probe."
        ) from error
    if result.returncode != 0:
        raise ValueError(
            "Trainer environment needs local torch, accelerate, diffusers, datasets, "
            "transformers, and peft installations. No package was installed."
        )
    try:
        runtime: dict[str, Any] = json.loads(result.stdout)
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError("Trainer runtime probe returned invalid data.") from error
    if not isinstance(runtime, dict) or runtime.get("cuda_available") is not True:
        raise ValueError("Trainer Python cannot access a CUDA GPU; training was not started.")
    if not isinstance(runtime.get("gpu_name"), str) or not runtime["gpu_name"]:
        raise ValueError("Trainer runtime probe did not identify a CUDA GPU.")
    print(f"Trainer CUDA device: {runtime['gpu_name']}")
    return runtime


def write_run_state(output_dir: Path, status: str, exit_code: int | None = None) -> None:
    state_path = output_dir / "run-state.json"
    temporary_path = output_dir / "run-state.json.tmp"
    temporary_path.write_text(json.dumps({
        "format_version": 1, "status": status, "exit_code": exit_code,
    }, indent=2) + "\n", encoding="utf-8")
    temporary_path.replace(state_path)


def run_training(
    archive_path: Path, model_dir: Path, trainer_script: Path,
    trainer_python: Path, output_dir: Path, max_steps: int, *, execute: bool,
    check_runtime: bool = False,
) -> int:
    summary = inspect_paths(
        archive_path, model_dir, trainer_script, trainer_python, output_dir
    )
    if not 1 <= max_steps <= 2000:
        raise ValueError("Training steps must be between 1 and 2000.")
    print(f"Validated {len(summary.image_names)} local images at {summary.resolution}px.")
    runtime = inspect_trainer_runtime(trainer_python) if check_runtime or execute else None
    if not execute:
        print("Preflight only. No training job, download, or output directory was started.")
        return 0
    output_dir.mkdir(exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="ai-sprite-lora-") as scratch:
        dataset_dir = Path(scratch)
        with zipfile.ZipFile(archive_path) as archive:
            for name in (*summary.image_names, "metadata.jsonl"):
                (dataset_dir / name).write_bytes(archive.read(name))
        command = training_command(
            trainer_python, trainer_script, model_dir, dataset_dir,
            output_dir, summary.resolution, max_steps,
        )
        (output_dir / "run-plan.json").write_text(json.dumps({
            "format_version": 1,
            "dataset_sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
            "trainer_sha256": hashlib.sha256(trainer_script.read_bytes()).hexdigest(),
            "sample_count": len(summary.image_names), "resolution": summary.resolution,
            "max_steps": max_steps, "base_model_dir": str(model_dir.resolve()),
            "trainer_runtime": runtime,
        }, indent=2) + "\n", encoding="utf-8")
        write_run_state(output_dir, "started")
        try:
            exit_code = subprocess.run(
                command, env=offline_environment(), check=False
            ).returncode
        except OSError as error:
            write_run_state(output_dir, "launch_failed")
            raise ValueError(
                "Trainer process could not be started; inspect run-state.json."
            ) from error
        write_run_state(
            output_dir, "process_completed" if exit_code == 0 else "process_failed",
            exit_code,
        )
        return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description="Preflight or run local SD1.5 LoRA training")
    parser.add_argument("--dataset-zip", type=Path, required=True)
    parser.add_argument("--base-model", type=Path, required=True)
    parser.add_argument("--trainer-script", type=Path, required=True)
    parser.add_argument("--trainer-python", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-steps", type=int, default=200)
    parser.add_argument("--check-runtime", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-rights", action="store_true")
    arguments = parser.parse_args()
    if arguments.execute and not arguments.confirm_rights:
        parser.error("--execute requires --confirm-rights for model and training images")
    try:
        return run_training(
            arguments.dataset_zip, arguments.base_model, arguments.trainer_script,
            arguments.trainer_python, arguments.output_dir, arguments.max_steps,
            execute=arguments.execute, check_runtime=arguments.check_runtime,
        )
    except ValueError as error:
        parser.error(str(error))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
