from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import get_settings
from app.db.session import get_engine
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


def png_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGBA", (16, 24), (103, 183, 178, 255)).save(output, format="PNG")
    return output.getvalue()


def create_project(client: TestClient) -> dict[str, object]:
    response = client.post("/api/v1/projects", json={"name": "Asset Test"})
    assert response.status_code == 201
    return response.json()


def test_import_png_and_restore_version(client: TestClient) -> None:
    project = create_project(client)
    imported = client.post(
        f"/api/v1/projects/{project['id']}/assets/import",
        data={"name": "Sky Knight", "asset_type": "character", "style": "eight_bit"},
        files={"file": ("hero.png", png_bytes(), "image/png")},
    )

    assert imported.status_code == 201
    asset = imported.json()
    assert asset["width"] == 16
    assert asset["height"] == 24
    assert asset["active_version_id"] is not None
    project_root = Path(str(project["root_path"]))
    assert (project_root / asset["thumbnail_path"]).is_file()

    listed = client.get(f"/api/v1/projects/{project['id']}/assets")
    assert [item["id"] for item in listed.json()] == [asset["id"]]

    versions = client.get(f"/api/v1/assets/{asset['id']}/versions")
    assert versions.status_code == 200
    first_version = versions.json()[0]
    assert len(first_version["checksum"]) == 64

    restored = client.post(
        f"/api/v1/assets/{asset['id']}/versions/{first_version['id']}/restore"
    )
    assert restored.status_code == 200
    assert restored.json()["version_number"] == 2
    assert restored.json()["source"] == "restore"
    assert restored.json()["parent_version_id"] == first_version["id"]


def test_corrupt_or_unsupported_import_is_rejected(client: TestClient) -> None:
    project = create_project(client)
    response = client.post(
        f"/api/v1/projects/{project['id']}/assets/import",
        data={"name": "Broken", "asset_type": "item", "style": "micro_pixel"},
        files={"file": ("broken.png", b"not a png", "image/png")},
    )

    assert response.status_code == 422
    assert client.get(f"/api/v1/projects/{project['id']}/assets").json() == []
