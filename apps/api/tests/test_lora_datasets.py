import hashlib
import json
import zipfile
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


def image_bytes() -> bytes:
    output = BytesIO()
    image = Image.new("RGBA", (2, 2), (255, 0, 0, 255))
    image.putpixel((0, 0), (0, 0, 0, 0))
    image.save(output, "PNG")
    return output.getvalue()


def make_asset(client: TestClient, name: str) -> tuple[dict[str, object], dict[str, object]]:
    project = client.post("/api/v1/projects", json={"name": name}).json()
    response = client.post(
        f"/api/v1/projects/{project['id']}/assets/import",
        data={"name": "Sprite", "asset_type": "character", "style": "micro_pixel"},
        files={"file": ("sprite.png", image_bytes(), "image/png")},
    )
    assert response.status_code == 201
    return project, response.json()


def test_dataset_exports_pinned_images_captions_and_provenance(client: TestClient) -> None:
    project, asset = make_asset(client, "LoRA Training Data")
    version_id = str(asset["active_version_id"])
    payload = {"samples": [{"version_id": version_id, "caption": " red sprite "}],
               "resolution": 256, "background": "001122"}
    response = client.post(f"/api/v1/projects/{project['id']}/lora-dataset", json=payload)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(BytesIO(response.content)) as archive:
        assert set(archive.namelist()) == {"0001.png", "metadata.jsonl", "manifest.json"}
        assert json.loads(archive.read("metadata.jsonl")) == {
            "file_name": "0001.png", "text": "red sprite"
        }
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["format_version"] == 1
        assert manifest["samples"][0]["version_id"] == version_id
        assert manifest["samples"][0]["prepared_sha256"] == hashlib.sha256(
            archive.read("0001.png")
        ).hexdigest()
        with Image.open(BytesIO(archive.read("0001.png"))) as prepared:
            assert prepared.size == (256, 256)
            assert prepared.mode == "RGB"
            assert prepared.getpixel((0, 0)) == (0, 17, 34)
            assert prepared.getpixel((200, 200)) == (255, 0, 0)
    assert client.get(f"/api/v1/assets/{asset['id']}").json()["active_version_id"] == version_id


def test_dataset_rejects_foreign_duplicate_and_modified_versions(client: TestClient) -> None:
    project, asset = make_asset(client, "LoRA Owner")
    other, foreign_asset = make_asset(client, "Other LoRA Owner")
    endpoint = f"/api/v1/projects/{project['id']}/lora-dataset"
    sample = {"version_id": asset["active_version_id"], "caption": "red sprite"}
    assert client.post(endpoint, json={"samples": [
        {"version_id": foreign_asset["active_version_id"], "caption": "foreign"}
    ]}).status_code == 422
    assert client.post(endpoint, json={"samples": [sample, sample]}).status_code == 422
    assert client.post(
        endpoint, json={"samples": [sample], "background": "../../"}
    ).status_code == 422
    assert client.post(endpoint, json={"samples": [sample], "resolution": 1024}).status_code == 422
    version = client.get(f"/api/v1/assets/{asset['id']}/versions").json()[0]
    source = Path(str(project["root_path"])) / version["file_path"]
    source.write_bytes(image_bytes() + b"changed")
    assert client.post(endpoint, json={"samples": [sample]}).status_code == 422
    assert client.get(f"/api/v1/projects/{other['id']}").status_code == 200
