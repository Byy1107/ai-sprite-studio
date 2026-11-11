import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.session import get_engine
from app.domain.projects import InvalidProjectNameError, slugify_project_name
from app.main import create_app


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


def test_project_crud_persists_database_and_project_file(client: TestClient) -> None:
    created = client.post(
        "/api/v1/projects",
        json={"name": "Sky Knight", "description": "A local character project."},
    )

    assert created.status_code == 201
    project = created.json()
    assert project["slug"] == "sky-knight"
    project_path = Path(project["root_path"])
    assert project_path.is_dir()
    metadata = json.loads((project_path / "project.json").read_text(encoding="utf-8"))
    assert metadata["id"] == project["id"]

    listed = client.get("/api/v1/projects")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [project["id"]]

    updated = client.patch(
        f"/api/v1/projects/{project['id']}", json={"description": "Updated locally."}
    )
    assert updated.status_code == 200
    assert updated.json()["description"] == "Updated locally."

    opened = client.post(f"/api/v1/projects/{project['id']}/open")
    assert opened.status_code == 200
    assert opened.json()["last_opened_at"] is not None

    deleted = client.delete(f"/api/v1/projects/{project['id']}")
    assert deleted.status_code == 204
    assert client.get("/api/v1/projects").json() == []
    assert not project_path.exists()


def test_duplicate_and_unsafe_names_are_rejected(client: TestClient) -> None:
    first = client.post("/api/v1/projects", json={"name": "Hero"})
    duplicate = client.post("/api/v1/projects", json={"name": "Hero"})
    unsafe = client.post("/api/v1/projects", json={"name": "../escape"})

    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert unsafe.status_code == 422


@pytest.mark.parametrize("name", ["CON", "bad/name", "trailing.", "   "])
def test_windows_invalid_project_names(name: str) -> None:
    with pytest.raises(InvalidProjectNameError):
        slugify_project_name(name)
