import hashlib
import json
from io import BytesIO
from pathlib import Path
from time import perf_counter
from unittest.mock import patch
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import AssetRecord
from app.db.session import get_engine
from app.domain.projects import InvalidProjectNameError, slugify_project_name
from app.main import create_app, logger
from app.services.project_storage import ProjectStorage


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


def test_integrity_reports_missing_version_without_changing_database(client: TestClient) -> None:
    project = client.post("/api/v1/projects", json={"name": "Recovery"}).json()
    output = BytesIO()
    Image.new("RGBA", (8, 8), (255, 0, 0, 255)).save(output, format="PNG")
    asset = client.post(
        f"/api/v1/projects/{project['id']}/assets/import",
        data={"name": "Hero", "asset_type": "character", "style": "eight_bit"},
        files={"file": ("hero.png", output.getvalue(), "image/png")},
    ).json()
    version = client.get(f"/api/v1/assets/{asset['id']}/versions").json()[0]
    endpoint = f"/api/v1/projects/{project['id']}/integrity"
    assert client.get(endpoint).json() == {
        "project_id": project["id"], "status": "ok", "issues": [],
    }
    (Path(project["root_path"]) / version["file_path"]).unlink()
    response = client.get(endpoint)
    assert response.status_code == 200
    assert response.json()["issues"] == [{
        "kind": "missing_asset_version", "reference_id": version["id"],
        "path": version["file_path"],
    }]
    assert client.get(f"/api/v1/assets/{asset['id']}/versions").json()[0]["id"] == version["id"]
    assert client.get("/api/v1/projects/missing/integrity").status_code == 404


def test_startup_reports_missing_project_file(client: TestClient) -> None:
    project = client.post("/api/v1/projects", json={"name": "Startup Recovery"}).json()
    (Path(project["root_path"]) / "project.json").unlink()
    with patch.object(logger, "warning") as warning, TestClient(create_app()) as restarted:
        result = restarted.get(f"/api/v1/projects/{project['id']}/integrity").json()
    assert result["issues"][0]["kind"] == "missing_project_metadata"
    warning.assert_called_once_with(
        "Project %s has %d missing or unsafe files.", project["id"], 1
    )


def test_project_backup_restores_into_fresh_workspace(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = client.post("/api/v1/projects", json={"name": "Backup Hero"}).json()
    output = BytesIO()
    Image.new("RGBA", (8, 8), (5, 10, 15, 255)).save(output, format="PNG")
    imported = client.post(
        f"/api/v1/projects/{project['id']}/assets/import",
        data={"name": "Hero", "asset_type": "character", "style": "micro_pixel"},
        files={"file": ("hero.png", output.getvalue(), "image/png")},
    ).json()
    version = client.get(f"/api/v1/assets/{imported['id']}/versions").json()[0]
    manual = client.post(
        f"/api/v1/assets/{imported['id']}/versions",
        files={"file": ("edit.png", output.getvalue(), "image/png")},
    )
    assert manual.status_code == 201
    clip = client.post(f"/api/v1/assets/{imported['id']}/animations", json={
        "name": "idle", "direction": "down", "fps": 8,
    }).json()
    frame = client.post(f"/api/v1/animations/{clip['id']}/frames", json={
        "asset_version_id": manual.json()["id"],
    })
    assert frame.status_code == 201
    exported = client.post("/api/v1/exports", json={
        "asset_id": imported["id"], "format": "spritesheet", "animation_id": clip["id"],
    })
    assert exported.status_code == 201
    export_id = exported.json()["id"]
    export_png = client.get(f"/api/v1/exports/{export_id}/files/png").content
    export_json = client.get(f"/api/v1/exports/{export_id}/files/json").content
    backup = client.get(f"/api/v1/projects/{project['id']}/backup")
    assert backup.status_code == 200
    assert backup.headers["content-type"] == "application/zip"
    assert client.post("/api/v1/projects/restore", files={
        "file": ("backup.zip", backup.content, "application/zip"),
    }).status_code == 422

    monkeypatch.setenv("AI_SPRITE_WORKSPACE_DIR", str(tmp_path / "new-workspace"))
    monkeypatch.setenv("AI_SPRITE_DATABASE_URL", f"sqlite:///{tmp_path / 'new-studio.db'}")
    get_settings.cache_clear()
    get_engine.cache_clear()
    with TestClient(create_app()) as fresh:
        restored = fresh.post("/api/v1/projects/restore", files={
            "file": ("backup.zip", backup.content, "application/zip"),
        })
        assert restored.status_code == 201, restored.text
        assert restored.json()["id"] == project["id"]
        assert restored.json()["root_path"] != project["root_path"]
        assert fresh.get(f"/api/v1/projects/{project['id']}/integrity").json()["status"] == "ok"
        versions = fresh.get(f"/api/v1/assets/{imported['id']}/versions").json()
        assert {item["id"] for item in versions} == {version["id"], manual.json()["id"]}
        content = fresh.get(f"/api/v1/asset-versions/{version['id']}/content").content
        assert content == output.getvalue()
        restored_frames = fresh.get(f"/api/v1/animations/{clip['id']}/frames").json()
        assert restored_frames[0]["id"] == frame.json()["id"]
        assert fresh.get(f"/api/v1/exports/{export_id}/files/png").content == export_png
        assert fresh.get(f"/api/v1/exports/{export_id}/files/json").content == export_json


def test_restore_rejects_archive_path_traversal(client: TestClient, tmp_path: Path) -> None:
    project = client.post("/api/v1/projects", json={"name": "Unsafe Archive"}).json()
    backup = client.get(f"/api/v1/projects/{project['id']}/backup").content
    with ZipFile(BytesIO(backup)) as source:
        manifest = json.loads(source.read("manifest.json"))
        files = {name: source.read(name) for name in source.namelist() if name != "manifest.json"}
    manifest["checksums"]["../escape.txt"] = hashlib.sha256(b"unsafe").hexdigest()
    malicious = BytesIO()
    with ZipFile(malicious, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
        archive.writestr("files/../escape.txt", b"unsafe")
        archive.writestr("manifest.json", json.dumps(manifest))
    response = client.post("/api/v1/projects/restore", files={
        "file": ("malicious.zip", malicious.getvalue(), "application/zip"),
    })
    assert response.status_code == 422
    assert "unsafe file path" in response.json()["detail"]
    assert not (tmp_path / "escape.txt").exists()


def test_restore_rejects_corrupt_file_without_creating_project(client: TestClient) -> None:
    project = client.post("/api/v1/projects", json={"name": "Checksum Source"}).json()
    backup = client.get(f"/api/v1/projects/{project['id']}/backup").content
    with ZipFile(BytesIO(backup)) as source:
        manifest = source.read("manifest.json")
    corrupt = BytesIO()
    with ZipFile(corrupt, "w") as archive:
        archive.writestr("files/project.json", b"corrupt")
        archive.writestr("manifest.json", manifest)
    response = client.post("/api/v1/projects/restore", files={
        "file": ("corrupt.zip", corrupt.getvalue(), "application/zip"),
    })
    assert response.status_code == 422
    assert "checksum" in response.json()["detail"]
    assert [item["id"] for item in client.get("/api/v1/projects").json()] == [project["id"]]


def test_trash_collision_keeps_both_copies(tmp_path: Path) -> None:
    storage = ProjectStorage(tmp_path)
    source = storage.create("hero", {"name": "Hero"})
    existing = tmp_path / ".trash" / "project-1"
    existing.mkdir(parents=True)
    (existing / "keep.txt").write_text("original", encoding="utf-8")

    with pytest.raises(FileExistsError):
        storage.move_to_trash(source, "project-1")

    assert source.is_dir()
    assert (existing / "keep.txt").read_text(encoding="utf-8") == "original"


def test_cache_cleanup_removes_only_unreferenced_cache_files(client: TestClient) -> None:
    project = client.post("/api/v1/projects", json={"name": "Cache Owner"}).json()
    root = Path(project["root_path"])
    nested = root / "cache" / "previews"
    nested.mkdir()
    (nested / "stale.png").write_bytes(b"cached")
    (root / "assets" / "keep.png").write_bytes(b"published")
    (root / "trash" / "keep.txt").write_text("retained", encoding="utf-8")

    response = client.delete(f"/api/v1/projects/{project['id']}/cache")

    assert response.status_code == 200
    assert response.json() == {"removed_files": 1}
    assert not nested.exists()
    assert (root / "assets" / "keep.png").read_bytes() == b"published"
    assert (root / "trash" / "keep.txt").read_text(encoding="utf-8") == "retained"
    assert client.delete(f"/api/v1/projects/{project['id']}/cache").json() == {"removed_files": 0}


def test_cache_cleanup_refuses_database_referenced_files(client: TestClient) -> None:
    project = client.post("/api/v1/projects", json={"name": "Referenced Cache"}).json()
    output = BytesIO()
    Image.new("RGBA", (8, 8), (5, 10, 15, 255)).save(output, format="PNG")
    asset = client.post(
        f"/api/v1/projects/{project['id']}/assets/import",
        data={"name": "Hero", "asset_type": "character", "style": "micro_pixel"},
        files={"file": ("hero.png", output.getvalue(), "image/png")},
    ).json()
    cache_file = Path(project["root_path"]) / "cache" / "keep.png"
    cache_file.write_bytes(b"referenced")
    with Session(get_engine()) as session:
        record = session.get(AssetRecord, asset["id"])
        assert record is not None
        record.thumbnail_path = "cache/keep.png"
        session.commit()

    response = client.delete(f"/api/v1/projects/{project['id']}/cache")

    assert response.status_code == 422
    assert cache_file.read_bytes() == b"referenced"


def test_large_project_fixture_opens_within_local_target(client: TestClient) -> None:
    project = client.post("/api/v1/projects", json={"name": "Large Fixture"}).json()
    output = BytesIO()
    Image.new("RGBA", (8, 8), (5, 10, 15, 255)).save(output, format="PNG")
    for index in range(200):
        imported = client.post(
            f"/api/v1/projects/{project['id']}/assets/import",
            data={"name": f"Sprite {index}", "asset_type": "item", "style": "eight_bit"},
            files={"file": ("sprite.png", output.getvalue(), "image/png")},
        )
        assert imported.status_code == 201

    started = perf_counter()
    opened = client.post(f"/api/v1/projects/{project['id']}/open")
    listed = client.get(f"/api/v1/projects/{project['id']}/assets")
    elapsed = perf_counter() - started

    assert opened.status_code == 200
    assert listed.status_code == 200
    assert len(listed.json()) == 200
    assert elapsed < 5.0, f"Opening and listing 200 assets took {elapsed:.2f}s"


@pytest.mark.parametrize("name", ["CON", "bad/name", "trailing.", "   "])
def test_windows_invalid_project_names(name: str) -> None:
    with pytest.raises(InvalidProjectNameError):
        slugify_project_name(name)
