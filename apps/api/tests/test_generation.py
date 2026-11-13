import time
from dataclasses import replace
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.ai import ComfyUIProvider, FakeAIProvider
from app.core.config import get_settings
from app.db.models import AssetVersionRecord, GenerationJobRecord
from app.db.session import get_engine
from app.domain.generation import GenerationRequest, GenerationStatus, ProviderResult
from app.main import create_app
from app.services.generation import GenerationService


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("AI_SPRITE_WORKSPACE_DIR", str(tmp_path / "workspace"))
    monkeypatch.setenv("AI_SPRITE_DATABASE_URL", f"sqlite:///{tmp_path / 'studio.db'}")
    get_settings.cache_clear()
    get_engine.cache_clear()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_engine.cache_clear()
    get_settings.cache_clear()


def create_project(client: TestClient) -> dict[str, object]:
    response = client.post("/api/v1/projects", json={"name": "Generation Test"})
    assert response.status_code == 201
    return response.json()


def generation_payload(project_id: object) -> dict[str, object]:
    return {
        "project_id": project_id,
        "asset_id": None,
        "prompt": "dark fantasy sky guardian",
        "asset_type": "character",
        "style": "eight_bit",
        "width": 32,
        "height": 32,
        "seed": 42,
    }


def wait_for_job(client: TestClient, job_id: str) -> dict[str, object]:
    for _ in range(100):
        payload = client.get(f"/api/v1/generation-jobs/{job_id}").json()
        if payload["status"] in {"succeeded", "failed", "canceled"}:
            return payload
        time.sleep(0.01)
    raise AssertionError("Fake generation did not finish")


def png_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGBA", (32, 32), (0, 0, 0, 0)).save(output, format="PNG")
    return output.getvalue()


def test_fake_job_succeeds_and_is_deterministic(client: TestClient) -> None:
    project = create_project(client)
    created = client.post(
        "/api/v1/generation-jobs", json=generation_payload(project["id"])
    )
    assert created.status_code == 201
    assert created.json()["status"] == "queued"
    completed = wait_for_job(client, created.json()["id"])
    assert completed["status"] == "succeeded"
    assert completed["progress"] == 1.0

    results = client.get(f"/api/v1/generation-jobs/{completed['id']}/results").json()
    assert len(results) == 1
    assert results[0]["seed"] == 42
    assert results[0]["metadata"] == {
        "deterministic": True,
        "preset_id": None,
        "provider": "fake",
    }
    assert (Path(str(project["root_path"])) / results[0]["file_path"]).is_file()


def test_queued_job_can_be_canceled(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = create_project(client)
    monkeypatch.setattr("app.api.generation.enqueue_generation", lambda _job_id: None)
    created = client.post(
        "/api/v1/generation-jobs", json=generation_payload(project["id"])
    ).json()
    canceled = client.post(f"/api/v1/generation-jobs/{created['id']}/cancel")
    assert canceled.status_code == 200
    assert canceled.json()["status"] == "canceled"


def test_restart_recovery_marks_interrupted_jobs_failed(client: TestClient) -> None:
    project = create_project(client)
    with Session(get_engine()) as session:
        job = GenerationJobRecord(
            project_id=str(project["id"]),
            provider="fake",
            status=GenerationStatus.RUNNING.value,
            request_json="{}",
        )
        session.add(job)
        session.commit()
        GenerationService(session).recover_interrupted()
        session.refresh(job)
        assert job.status == "failed"
        assert job.error_code == "app_restarted"


def test_cancel_while_provider_runs_does_not_publish_result(client: TestClient) -> None:
    project = create_project(client)

    class CancelingProvider(FakeAIProvider):
        def generate(self, request: GenerationRequest) -> ProviderResult:
            with Session(get_engine()) as cancel_session:
                running_job = cancel_session.scalar(
                    select(GenerationJobRecord).where(
                        GenerationJobRecord.status == GenerationStatus.RUNNING.value
                    )
                )
                assert running_job is not None
                running_job.status = GenerationStatus.CANCELED.value
                cancel_session.commit()
            return super().generate(request)

    with Session(get_engine()) as session:
        service = GenerationService(session, CancelingProvider())
        job = service.create(GenerationRequest(**generation_payload(project["id"])))
        completed = service.run(job.id)
        assert completed.status == "canceled"
        assert service.results(job.id) == []


def test_invalid_project_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/v1/generation-jobs", json=generation_payload("missing-project")
    )
    assert response.status_code == 404


def test_presets_are_listed_and_type_checked(client: TestClient) -> None:
    presets = client.get("/api/v1/generation-presets")
    assert presets.status_code == 200
    assert {preset["asset_type"] for preset in presets.json()} == {
        "character",
        "item",
        "environment",
        "tileset",
    }
    project = create_project(client)
    payload = generation_payload(project["id"])
    payload["asset_type"] = "item"
    payload["preset_id"] = "character-hero"
    response = client.post("/api/v1/generation-jobs", json=payload)
    assert response.status_code == 422
    assert response.json()["detail"] == "Preset does not match asset type"


def test_generated_candidate_can_be_accepted_as_asset_version(client: TestClient) -> None:
    project = create_project(client)
    asset = client.post(
        f"/api/v1/projects/{project['id']}/assets/import",
        data={"name": "Hero", "asset_type": "character", "style": "eight_bit"},
        files={"file": ("hero.png", png_bytes(), "image/png")},
    ).json()
    payload = generation_payload(project["id"])
    payload["asset_id"] = asset["id"]
    created = client.post("/api/v1/generation-jobs", json=payload).json()
    completed = wait_for_job(client, created["id"])
    result = client.get(f"/api/v1/generation-jobs/{completed['id']}/results").json()[0]

    accepted = client.post(f"/api/v1/generation-results/{result['id']}/accept")
    assert accepted.status_code == 201
    assert accepted.json()["source"] == "generated"
    versions = client.get(f"/api/v1/assets/{asset['id']}/versions").json()
    assert versions[0]["source"] == "generated"


def test_reference_is_pinned_and_baseline_discloses_limitation(client: TestClient) -> None:
    project = create_project(client)
    asset = client.post(
        f"/api/v1/projects/{project['id']}/assets/import",
        data={"name": "Reference", "asset_type": "character", "style": "eight_bit"},
        files={"file": ("reference.png", png_bytes(), "image/png")},
    ).json()
    payload = generation_payload(project["id"])
    payload["reference_asset_id"] = asset["id"]
    payload["reference_weight"] = 0.75
    created = client.post("/api/v1/generation-jobs", json=payload)
    assert created.status_code == 201
    request = created.json()["request"]
    assert request["reference_version_id"] == asset["active_version_id"]
    assert request["reference_weight"] == 0.75
    completed = wait_for_job(client, created.json()["id"])
    assert completed["status"] == "succeeded"
    result = client.get(f"/api/v1/generation-jobs/{completed['id']}/results").json()[0]
    assert result["metadata"]["reference_conditioning_applied"] is False
    assert result["metadata"]["warnings"]
    assert len(client.get(f"/api/v1/assets/{asset['id']}/versions").json()) == 1


def test_historical_reference_stays_pinned_after_new_version(client: TestClient) -> None:
    project = create_project(client)
    asset = client.post(
        f"/api/v1/projects/{project['id']}/assets/import",
        data={"name": "Reference", "asset_type": "character", "style": "eight_bit"},
        files={"file": ("reference.png", png_bytes(), "image/png")},
    ).json()
    old_version = asset["active_version_id"]
    published = client.post(
        f"/api/v1/assets/{asset['id']}/versions",
        files={"file": ("edit.png", png_bytes(), "image/png")},
    )
    assert published.status_code == 201
    payload = generation_payload(project["id"])
    payload.update(reference_asset_id=asset["id"], reference_version_id=old_version)
    queued = client.post("/api/v1/generation-jobs", json=payload)
    assert queued.status_code == 201
    completed = wait_for_job(client, queued.json()["id"])
    assert completed["status"] == "succeeded"
    assert completed["request"]["reference_version_id"] == old_version
    listed = client.get(f"/api/v1/projects/{project['id']}/assets").json()
    assert listed[0]["active_version_id"] == published.json()["id"]


@pytest.mark.parametrize("field", ["asset_id", "reference_asset_id"])
def test_foreign_project_assets_are_rejected(client: TestClient, field: str) -> None:
    project = create_project(client)
    other = client.post("/api/v1/projects", json={"name": "Other project"}).json()
    asset = client.post(
        f"/api/v1/projects/{other['id']}/assets/import",
        data={"name": "Other", "asset_type": "character", "style": "eight_bit"},
        files={"file": ("other.png", png_bytes(), "image/png")},
    ).json()
    payload = generation_payload(project["id"])
    payload[field] = asset["id"]
    assert client.post("/api/v1/generation-jobs", json=payload).status_code == 404


@pytest.mark.parametrize("weight", [-0.1, 2.1])
def test_invalid_reference_weight_is_rejected(client: TestClient, weight: float) -> None:
    payload = generation_payload(create_project(client)["id"])
    payload["reference_weight"] = weight
    assert client.post("/api/v1/generation-jobs", json=payload).status_code == 422


def test_orphan_reference_version_is_rejected(client: TestClient) -> None:
    payload = generation_payload(create_project(client)["id"])
    payload["reference_version_id"] = "missing"
    assert client.post("/api/v1/generation-jobs", json=payload).status_code == 404


def test_lora_settings_are_persisted_without_changing_assets(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.api.generation.configured_provider",
        lambda: ComfyUIProvider("http://localhost:8188", "sd15.safetensors", 2),
    )
    monkeypatch.setattr("app.api.generation.enqueue_generation", lambda _job_id: None)
    project = create_project(client)
    payload = generation_payload(project["id"])
    payload.update(lora_name="pixel.safetensors", lora_weight=0.65)
    response = client.post("/api/v1/generation-jobs", json=payload)
    assert response.status_code == 201
    stored = client.get(f"/api/v1/generation-jobs/{response.json()['id']}").json()
    assert stored["request"]["lora_name"] == "pixel.safetensors"
    assert stored["request"]["lora_weight"] == 0.65
    assert stored["workflow_id"] == "sd15-text-to-sprite-lora"
    assert stored["workflow_version"] == "2"
    assert client.get(f"/api/v1/projects/{project['id']}/assets").json() == []


def test_mock_provider_rejects_lora_without_creating_job(client: TestClient) -> None:
    project = create_project(client)
    payload = generation_payload(project["id"])
    payload["lora_name"] = "pixel.safetensors"
    response = client.post("/api/v1/generation-jobs", json=payload)
    assert response.status_code == 422
    assert "requires the ComfyUI provider" in response.json()["detail"]
    assert client.get("/api/v1/generation-jobs").json() == []


@pytest.mark.parametrize("weight", [-0.1, 2.1, "NaN", "Infinity"])
def test_lora_weight_is_bounded_and_finite(client: TestClient, weight: object) -> None:
    payload = generation_payload(create_project(client)["id"])
    payload["lora_weight"] = weight
    assert client.post("/api/v1/generation-jobs", json=payload).status_code == 422


@pytest.mark.parametrize("tamper", [False, True])
def test_controlnet_uses_pinned_bytes_and_preserves_active_asset(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tamper: bool
) -> None:
    calls: list[bytes | None] = []

    class ControlProvider(FakeAIProvider):
        provider_id = "comfyui"

        def generate(
            self, request: GenerationRequest, *, reference_image: bytes | None = None
        ) -> ProviderResult:
            calls.append(reference_image)
            generated = super().generate(replace(request, controlnet_name=None))
            return replace(generated, metadata={"controlnet_applied": True})

    monkeypatch.setattr("app.api.generation.configured_provider", ControlProvider)
    monkeypatch.setattr("app.api.generation.enqueue_generation", lambda _job_id: None)
    project = create_project(client)
    asset = client.post(
        f"/api/v1/projects/{project['id']}/assets/import",
        data={"name": "Control", "asset_type": "character", "style": "eight_bit"},
        files={"file": ("control.png", png_bytes(), "image/png")},
    ).json()
    payload = generation_payload(project["id"])
    payload.update(
        asset_id=asset["id"], reference_asset_id=asset["id"],
        controlnet_name="edge.safetensors", controlnet_strength=0.65,
        controlnet_start=0.1, controlnet_end=0.8,
    )
    queued = client.post("/api/v1/generation-jobs", json=payload)
    assert queued.status_code == 201
    assert queued.json()["workflow_id"] == "sd15-text-to-sprite-controlnet"
    assert queued.json()["request"]["controlnet_strength"] == 0.65
    assert queued.json()["request"]["controlnet_start"] == 0.1
    assert queued.json()["request"]["controlnet_end"] == 0.8
    updated = BytesIO()
    Image.new("RGBA", (32, 32), (255, 0, 0, 255)).save(updated, format="PNG")
    published = client.post(
        f"/api/v1/assets/{asset['id']}/versions",
        files={"file": ("edited.png", updated.getvalue(), "image/png")},
    )
    assert published.status_code == 201
    with Session(get_engine()) as session:
        service = GenerationService(session, ControlProvider())
        if tamper:
            version = session.get(AssetVersionRecord, asset["active_version_id"])
            assert version is not None
            (Path(str(project["root_path"])) / version.file_path).write_bytes(updated.getvalue())
            with pytest.raises(ValueError, match="has changed"):
                service.run(queued.json()["id"])
            assert service.get(queued.json()["id"]).status == "failed"
            assert service.results(queued.json()["id"]) == []
            assert calls == []
        else:
            assert service.run(queued.json()["id"]).status == "succeeded"
            assert calls == [png_bytes()]
            results = client.get(
                f"/api/v1/generation-jobs/{queued.json()['id']}/results"
            ).json()
            assert results[0]["metadata"]["reference_conditioning_applied"] is True
            assert "warnings" not in results[0]["metadata"]
    assert client.get(f"/api/v1/assets/{asset['id']}").json()["active_version_id"] == (
        published.json()["id"]
    )
    assert len(client.get(f"/api/v1/assets/{asset['id']}/versions").json()) == 2


def test_controlnet_rejects_missing_reference_and_invalid_interval(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.api.generation.configured_provider",
        lambda: ComfyUIProvider("http://localhost:8188", "sd15.safetensors", 2),
    )
    payload = generation_payload(create_project(client)["id"])
    payload["controlnet_name"] = "edge.safetensors"
    response = client.post("/api/v1/generation-jobs", json=payload)
    assert response.status_code == 422
    assert "requires a reference asset" in response.json()["detail"]
    payload.update(reference_asset_id="reference", controlnet_start=0.8, controlnet_end=0.2)
    response = client.post("/api/v1/generation-jobs", json=payload)
    assert response.status_code == 422
    assert "start must be before end" in response.json()["detail"]


def test_controlnet_is_rejected_by_fake_provider(client: TestClient) -> None:
    payload = generation_payload(create_project(client)["id"])
    payload["controlnet_name"] = "edge.safetensors"
    response = client.post("/api/v1/generation-jobs", json=payload)
    assert response.status_code == 422
    assert client.get("/api/v1/generation-jobs").json() == []


@pytest.mark.parametrize("field,value", [
    ("controlnet_strength", -0.1), ("controlnet_strength", 2.1),
    ("controlnet_strength", "NaN"), ("controlnet_start", -0.1),
    ("controlnet_end", 1.1), ("controlnet_end", "Infinity"),
])
def test_invalid_controlnet_settings(client: TestClient, field: str, value: object) -> None:
    payload = generation_payload(create_project(client)["id"])
    payload[field] = value
    assert client.post("/api/v1/generation-jobs", json=payload).status_code == 422


@pytest.mark.parametrize("operation", ["variation", "inpaint"])
def test_ai_edit_uses_pinned_source_and_preserves_active_version(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    seen: list[bytes | None] = []

    class EditProvider:
        provider_id = "comfyui"

        def cancel(self) -> None:
            return None

        def generate(
            self, request: GenerationRequest, *, reference_image: bytes | None = None
        ) -> ProviderResult:
            seen.append(reference_image)
            candidate = BytesIO()
            Image.new("RGBA", (32, 32), (255, 0, 0, 255)).save(candidate, "PNG")
            return ProviderResult(candidate.getvalue(), request.seed, {"edit_applied": True})

    monkeypatch.setattr("app.api.generation.configured_provider", EditProvider)
    monkeypatch.setattr("app.api.generation.enqueue_generation", lambda _job_id: None)
    project = create_project(client)
    asset = client.post(
        f"/api/v1/projects/{project['id']}/assets/import",
        data={"name": "Edit source", "asset_type": "character", "style": "eight_bit"},
        files={"file": ("source.png", png_bytes(), "image/png")},
    ).json()
    payload = generation_payload(project["id"])
    payload.update(
        asset_id=asset["id"], reference_asset_id=asset["id"],
        reference_version_id=asset["active_version_id"], operation=operation,
    )
    if operation == "inpaint":
        payload.update(mask_x=3, mask_y=4, mask_width=5, mask_height=6)
    queued = client.post("/api/v1/generation-jobs", json=payload)
    assert queued.status_code == 201
    assert queued.json()["request"]["reference_version_id"] == asset["active_version_id"]
    assert operation in queued.json()["workflow_id"]
    assert queued.json()["workflow_version"] == "2"
    updated = BytesIO()
    Image.new("RGBA", (32, 32), (0, 0, 255, 255)).save(updated, "PNG")
    published = client.post(
        f"/api/v1/assets/{asset['id']}/versions",
        files={"file": ("later.png", updated.getvalue(), "image/png")},
    ).json()
    with Session(get_engine()) as session:
        service = GenerationService(session, EditProvider())
        assert service.run(queued.json()["id"]).status == "succeeded"
        result = service.results(queued.json()["id"])[0]
        content = (Path(str(project["root_path"])) / result.file_path).read_bytes()
        with Image.open(BytesIO(content)) as candidate:
            assert candidate.getpixel((4, 5)) == (255, 0, 0, 255)
            if operation == "inpaint":
                assert candidate.getpixel((2, 5)) == (0, 0, 0, 0)
                assert candidate.getpixel((8, 5)) == (0, 0, 0, 0)
            else:
                assert candidate.getpixel((2, 5)) == (255, 0, 0, 255)
    assert seen == [png_bytes()]
    current_asset = client.get(f"/api/v1/assets/{asset['id']}").json()
    assert current_asset["active_version_id"] == published["id"]
    assert len(client.get(f"/api/v1/assets/{asset['id']}/versions").json()) == 2


@pytest.mark.parametrize("changes", [
    {"operation": "inpaint"},
    {"operation": "inpaint", "mask_x": 31, "mask_y": 0,
     "mask_width": 2, "mask_height": 2},
    {"operation": "variation", "mask_x": 0},
    {"ipadapter_model": "adapter.safetensors"},
    {"clip_vision_model": "vision.safetensors"},
])
def test_invalid_ai_edit_options_rejected_before_queue(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, changes: dict[str, object]
) -> None:
    monkeypatch.setattr(
        "app.api.generation.configured_provider",
        lambda: ComfyUIProvider("http://localhost:8188", "sd15.safetensors", 2),
    )
    project = create_project(client)
    asset = client.post(
        f"/api/v1/projects/{project['id']}/assets/import",
        data={"name": "Edit source", "asset_type": "character", "style": "eight_bit"},
        files={"file": ("source.png", png_bytes(), "image/png")},
    ).json()
    payload = generation_payload(project["id"])
    payload.update(asset_id=asset["id"], reference_asset_id=asset["id"], **changes)
    assert client.post("/api/v1/generation-jobs", json=payload).status_code == 422
    assert client.get("/api/v1/generation-jobs").json() == []


def test_fake_provider_rejects_ai_edit(client: TestClient) -> None:
    project = create_project(client)
    asset = client.post(
        f"/api/v1/projects/{project['id']}/assets/import",
        data={"name": "Edit source", "asset_type": "character", "style": "eight_bit"},
        files={"file": ("source.png", png_bytes(), "image/png")},
    ).json()
    payload = generation_payload(project["id"])
    payload.update(
        asset_id=asset["id"], reference_asset_id=asset["id"], operation="variation",
    )
    assert client.post("/api/v1/generation-jobs", json=payload).status_code == 422


def test_variation_rejects_wrong_output_size_without_changing_asset(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class WrongSizeProvider:
        provider_id = "comfyui"

        def cancel(self) -> None:
            return None

        def generate(
            self, request: GenerationRequest, *, reference_image: bytes | None = None
        ) -> ProviderResult:
            output = BytesIO()
            Image.new("RGBA", (16, 16), (255, 0, 0, 255)).save(output, "PNG")
            return ProviderResult(output.getvalue(), request.seed, {"edit_applied": True})

    monkeypatch.setattr("app.api.generation.configured_provider", WrongSizeProvider)
    monkeypatch.setattr("app.api.generation.enqueue_generation", lambda _job_id: None)
    project = create_project(client)
    asset = client.post(
        f"/api/v1/projects/{project['id']}/assets/import",
        data={"name": "Edit source", "asset_type": "character", "style": "eight_bit"},
        files={"file": ("source.png", png_bytes(), "image/png")},
    ).json()
    payload = generation_payload(project["id"])
    payload.update(
        asset_id=asset["id"], reference_asset_id=asset["id"], operation="variation",
    )
    queued = client.post("/api/v1/generation-jobs", json=payload).json()
    with Session(get_engine()) as session:
        service = GenerationService(session, WrongSizeProvider())
        with pytest.raises(ValueError, match="dimensions differ"):
            service.run(queued["id"])
        assert service.get(queued["id"]).status == "failed"
        assert service.results(queued["id"]) == []
    current_asset = client.get(f"/api/v1/assets/{asset['id']}").json()
    assert current_asset["active_version_id"] == asset["active_version_id"]
