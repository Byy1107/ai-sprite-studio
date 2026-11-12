import time
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.ai import FakeAIProvider
from app.core.config import get_settings
from app.db.models import GenerationJobRecord
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
