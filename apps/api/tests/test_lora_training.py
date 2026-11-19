import hashlib
import json
import subprocess
import sys
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from app.cli.lora_train import inspect_dataset, run_training


def dataset_zip(tmp_path: Path) -> Path:
    image_output = BytesIO()
    Image.new("RGB", (256, 256), (12, 34, 56)).save(image_output, "PNG")
    image = image_output.getvalue()
    archive_path = tmp_path / "dataset.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("0001.png", image)
        archive.writestr("metadata.jsonl", '{"file_name":"0001.png","text":"red sword"}\n')
        archive.writestr("manifest.json", json.dumps({
            "format_version": 1, "resolution": 256,
            "samples": [{
                "file_name": "0001.png",
                "prepared_sha256": hashlib.sha256(image).hexdigest(),
            }],
        }))
    return archive_path


def base_model(tmp_path: Path) -> Path:
    model_dir = tmp_path / "sd15-diffusers"
    (model_dir / "model_index.json").parent.mkdir()
    (model_dir / "model_index.json").write_text(
        '{"_class_name":"StableDiffusionPipeline"}', encoding="utf-8"
    )
    for component, config in (
        ("unet", "config.json"), ("vae", "config.json"),
        ("text_encoder", "config.json"),
        ("tokenizer", "tokenizer_config.json"),
        ("scheduler", "scheduler_config.json"),
    ):
        directory = model_dir / component
        directory.mkdir()
        (directory / config).write_text("{}", encoding="utf-8")
        if component in {"unet", "vae", "text_encoder"}:
            (directory / "weights.safetensors").write_bytes(b"test weights")
    return model_dir


def test_preflight_does_not_execute_or_create_output(tmp_path: Path) -> None:
    archive = dataset_zip(tmp_path)
    model = base_model(tmp_path)
    trainer = tmp_path / "train_text_to_image_lora.py"
    trainer.write_text("pass\n", encoding="utf-8")
    destination = tmp_path / "new-training-output"
    summary = inspect_dataset(archive)
    assert summary.resolution == 256
    assert summary.captions == ("red sword",)
    assert run_training(
        archive, model, trainer, Path(sys.executable), destination, 200, execute=False
    ) == 0
    assert not destination.exists()


def test_execution_sets_offline_flags_and_uses_separate_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = dataset_zip(tmp_path)
    model = base_model(tmp_path)
    trainer = tmp_path / "train_text_to_image_lora.py"
    trainer.write_text("pass\n", encoding="utf-8")
    destination = tmp_path / "training-output"
    observed: dict[str, Any] = {}

    def fake_run(
        command: list[str], *, env: dict[str, str], check: bool,
        capture_output: bool = False, text: bool = False, timeout: int | None = None,
    ) -> subprocess.CompletedProcess[str]:
        if "-c" in command:
            assert capture_output and text and timeout == 45
            assert env["HF_HUB_OFFLINE"] == "1"
            return subprocess.CompletedProcess(command, 0, stdout=json.dumps({
                "packages": {"torch": "2.0"}, "cuda_available": True,
                "gpu_name": "Test GPU",
            }))
        observed.update({"command": command, "env": env, "check": check})
        state = json.loads((destination / "run-state.json").read_text(encoding="utf-8"))
        assert state["status"] == "started"
        dataset_dir = Path(command[command.index("--train_data_dir") + 1])
        assert (dataset_dir / "0001.png").is_file()
        assert (dataset_dir / "metadata.jsonl").is_file()
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr("app.cli.lora_train.subprocess.run", fake_run)
    assert run_training(
        archive, model, trainer, Path(sys.executable), destination, 100, execute=True
    ) == 0
    assert observed["check"] is False
    assert observed["env"]["HF_HUB_OFFLINE"] == "1"
    assert observed["env"]["WANDB_MODE"] == "disabled"
    assert observed["env"]["HF_HUB_DISABLE_TELEMETRY"] == "1"
    assert "--push_to_hub" not in observed["command"]
    assert "--gradient_checkpointing" in observed["command"]
    plan = json.loads((destination / "run-plan.json").read_text(encoding="utf-8"))
    assert plan["dataset_sha256"] == hashlib.sha256(archive.read_bytes()).hexdigest()
    assert plan["trainer_runtime"]["gpu_name"] == "Test GPU"
    state = json.loads((destination / "run-state.json").read_text(encoding="utf-8"))
    assert state == {"format_version": 1, "status": "process_completed", "exit_code": 0}


def test_failed_trainer_process_keeps_output_and_records_exit_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = dataset_zip(tmp_path)
    model = base_model(tmp_path)
    trainer = tmp_path / "train_text_to_image_lora.py"
    trainer.write_text("pass\n", encoding="utf-8")
    destination = tmp_path / "training-output"

    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if "-c" in command:
            return subprocess.CompletedProcess(command, 0, stdout=json.dumps({
                "packages": {}, "cuda_available": True, "gpu_name": "Test GPU",
            }))
        return subprocess.CompletedProcess(command, 7)

    monkeypatch.setattr("app.cli.lora_train.subprocess.run", fake_run)
    assert run_training(
        archive, model, trainer, Path(sys.executable), destination, 100, execute=True
    ) == 7
    assert (destination / "run-plan.json").is_file()
    state = json.loads((destination / "run-state.json").read_text(encoding="utf-8"))
    assert state == {"format_version": 1, "status": "process_failed", "exit_code": 7}


def test_launcher_error_records_failure_without_erasing_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = dataset_zip(tmp_path)
    model = base_model(tmp_path)
    trainer = tmp_path / "train_text_to_image_lora.py"
    trainer.write_text("pass\n", encoding="utf-8")
    destination = tmp_path / "training-output"

    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if "-c" in command:
            return subprocess.CompletedProcess(command, 0, stdout=json.dumps({
                "packages": {}, "cuda_available": True, "gpu_name": "Test GPU",
            }))
        raise OSError("launcher unavailable")

    monkeypatch.setattr("app.cli.lora_train.subprocess.run", fake_run)
    with pytest.raises(ValueError, match="could not be started"):
        run_training(
            archive, model, trainer, Path(sys.executable), destination, 100,
            execute=True,
        )
    state = json.loads((destination / "run-state.json").read_text(encoding="utf-8"))
    assert state == {"format_version": 1, "status": "launch_failed", "exit_code": None}


def test_runtime_probe_failure_does_not_create_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = dataset_zip(tmp_path)
    model = base_model(tmp_path)
    trainer = tmp_path / "train_text_to_image_lora.py"
    trainer.write_text("pass\n", encoding="utf-8")
    destination = tmp_path / "training-output"

    def missing_packages(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 1, stderr="No module named torch")

    monkeypatch.setattr("app.cli.lora_train.subprocess.run", missing_packages)
    with pytest.raises(ValueError, match="environment needs local"):
        run_training(
            archive, model, trainer, Path(sys.executable), destination, 100,
            execute=True,
        )
    assert not destination.exists()


def test_runtime_probe_rejects_cpu_only_trainer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = dataset_zip(tmp_path)
    model = base_model(tmp_path)
    trainer = tmp_path / "train_text_to_image_lora.py"
    trainer.write_text("pass\n", encoding="utf-8")
    destination = tmp_path / "training-output"

    def cpu_only(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps({
            "packages": {}, "cuda_available": False, "gpu_name": None,
        }))

    monkeypatch.setattr("app.cli.lora_train.subprocess.run", cpu_only)
    with pytest.raises(ValueError, match="cannot access a CUDA GPU"):
        run_training(
            archive, model, trainer, Path(sys.executable), destination, 100,
            execute=False, check_runtime=True,
        )
    assert not destination.exists()


def test_preflight_rejects_tampered_archive_and_wrong_model(tmp_path: Path) -> None:
    archive = dataset_zip(tmp_path)
    with zipfile.ZipFile(archive, "a") as writer:
        writer.writestr("../escape.png", b"unsafe")
    with pytest.raises(ValueError, match="unsafe path"):
        inspect_dataset(archive)
    archive = dataset_zip(tmp_path)
    model = base_model(tmp_path)
    (model / "model_index.json").write_text(
        '{"_class_name":"StableDiffusionXLPipeline"}', encoding="utf-8"
    )
    trainer = tmp_path / "train_text_to_image_lora.py"
    trainer.write_text("pass\n", encoding="utf-8")
    with pytest.raises(ValueError, match="StableDiffusionPipeline"):
        run_training(
            archive, model, trainer, Path(sys.executable), tmp_path / "out", 20,
            execute=False,
        )
