from io import BytesIO
from pathlib import Path
from time import perf_counter, sleep

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import get_settings
from app.db.session import get_engine
from app.main import create_app
from app.services.asset_storage import AssetStorage


def test_thumbnail_pipeline_profile(tmp_path: Path) -> None:
    output = BytesIO()
    Image.new("RGBA", (512, 512), (47, 108, 112, 255)).save(output, "PNG")
    storage = AssetStorage()
    started = perf_counter()
    for index in range(20):
        _, thumbnail = storage.write_initial_version(
            tmp_path, f"asset-{index}", "version-1", output.getvalue()
        )
        assert thumbnail.is_file()
    elapsed = perf_counter() - started
    with Image.open(thumbnail) as image:
        assert image.size == (192, 192)
    print(f"Sprint 10 thumbnail profile: 20 imports of 512x512 in {elapsed:.3f}s")


def test_fake_queue_profile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_SPRITE_WORKSPACE_DIR", str(tmp_path / "workspace"))
    monkeypatch.setenv("AI_SPRITE_DATABASE_URL", f"sqlite:///{tmp_path / 'studio.db'}")
    monkeypatch.setenv("AI_SPRITE_AI_PROVIDER", "fake")
    get_settings.cache_clear()
    get_engine.cache_clear()
    try:
        with TestClient(create_app()) as client:
            project = client.post("/api/v1/projects", json={"name": "Queue Profile"}).json()
            started = perf_counter()
            job_ids = []
            for index in range(10):
                response = client.post("/api/v1/generation-jobs", json={
                    "project_id": project["id"], "asset_id": None,
                    "prompt": f"profile sprite {index}", "asset_type": "item",
                    "style": "eight_bit", "width": 32, "height": 32, "seed": index,
                })
                assert response.status_code == 201
                job_ids.append(response.json()["id"])
            for _ in range(200):
                jobs = client.get(f"/api/v1/generation-jobs?project_id={project['id']}").json()
                if all(job["status"] == "succeeded" for job in jobs) and len(jobs) == 10:
                    break
                sleep(0.01)
            else:
                pytest.fail("Fake queue did not complete ten jobs")
            elapsed = perf_counter() - started
            assert {job["id"] for job in jobs} == set(job_ids)
            print(f"Sprint 10 fake queue profile: 10 jobs in {elapsed:.3f}s")
    finally:
        get_engine.cache_clear()
        get_settings.cache_clear()
