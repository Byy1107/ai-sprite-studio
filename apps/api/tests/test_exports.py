import hashlib
import json
from io import BytesIO
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from PIL import Image
from sqlalchemy import create_engine, inspect

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


def png(color: tuple[int, int, int, int]) -> bytes:
    output = BytesIO()
    image = Image.new("RGBA", (4, 4), color)
    image.putpixel((0, 0), (0, 0, 0, 0))
    image.save(output, "PNG")
    return output.getvalue()


def validate_sheet_metadata(metadata: dict[str, object]) -> None:
    schema_path = Path(__file__).resolve().parents[3] / "docs/schemas/spritesheet-v1.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(metadata)


def make_asset(client: TestClient, name: str) -> tuple[dict[str, object], dict[str, object]]:
    project = client.post("/api/v1/projects", json={"name": name}).json()
    response = client.post(
        f"/api/v1/projects/{project['id']}/assets/import",
        data={"name": name, "asset_type": "character", "style": "eight_bit"},
        files={"file": ("sprite.png", png((255, 0, 0, 255)), "image/png")},
    )
    assert response.status_code == 201
    return project, response.json()


def test_png_export_is_crisp_version_pinned_and_non_overwriting(client: TestClient) -> None:
    project, asset = make_asset(client, "Export Hero")
    first = client.post("/api/v1/exports", json={
        "asset_id": asset["id"], "format": "png", "scale": 4,
    })
    assert first.status_code == 201
    exported = first.json()
    content = client.get(f"/api/v1/exports/{exported['id']}/files/png")
    assert content.status_code == 200
    assert exported["checksum"] == hashlib.sha256(content.content).hexdigest()
    assert client.get(f"/api/v1/exports/{exported['id']}/download").content == content.content
    with Image.open(BytesIO(content.content)) as image:
        assert image.size == (16, 16)
        assert image.mode == "RGBA"
        assert image.getpixel((0, 0)) == (0, 0, 0, 0)
        assert image.getpixel((4, 4)) == (255, 0, 0, 255)
    changed = client.post(
        f"/api/v1/assets/{asset['id']}/versions",
        files={"file": ("blue.png", png((0, 0, 255, 255)), "image/png")},
    )
    assert changed.status_code == 201
    second = client.post("/api/v1/exports", json={
        "asset_id": asset["id"], "format": "png", "scale": 4,
    }).json()
    assert second["id"] != exported["id"]
    assert second["output_path"] != exported["output_path"]
    assert client.get(f"/api/v1/exports/{exported['id']}/files/png").content == content.content
    assert client.get(f"/api/v1/exports/{exported['id']}/files/json").status_code == 404
    record = client.get(f"/api/v1/exports/{exported['id']}").json()
    assert record["config"]["asset_version_id"] == asset["active_version_id"]
    assert len(client.get(f"/api/v1/projects/{project['id']}/exports").json()) == 2


def test_spritesheet_rects_metadata_and_rejections(client: TestClient) -> None:
    project, asset = make_asset(client, "Sheet Hero")
    _, other = make_asset(client, "Other Hero")
    clip = client.post(
        f"/api/v1/assets/{asset['id']}/animations",
        json={"name": "walk", "direction": "down", "fps": 10, "loop_mode": "ping_pong"},
    ).json()
    first = client.post(f"/api/v1/animations/{clip['id']}/frames", json={
        "asset_version_id": asset["active_version_id"],
    }).json()
    second = client.post(f"/api/v1/animation-frames/{first['id']}/duplicate").json()
    assert client.patch(f"/api/v1/animation-frames/{second['id']}", json={
        "duration_ms": 250, "pivot_x": 2, "offset_y": -1, "event_name": "footstep",
    }).status_code == 200
    payload = {
        "asset_id": asset["id"], "format": "spritesheet",
        "animation_id": clip["id"], "scale": 2, "columns": 2,
        "spacing": 3, "padding": 1,
    }
    response = client.post("/api/v1/exports", json=payload)
    assert response.status_code == 201
    export_id = response.json()["id"]
    image_bytes = client.get(f"/api/v1/exports/{export_id}/files/png").content
    metadata_bytes = client.get(f"/api/v1/exports/{export_id}/files/json").content
    with Image.open(BytesIO(image_bytes)) as image:
        assert image.size == (21, 10)
        assert image.getpixel((1, 1)) == (0, 0, 0, 0)
        assert image.getpixel((3, 3)) == (255, 0, 0, 255)
        assert image.getpixel((9, 2)) == (0, 0, 0, 0)
        assert image.getpixel((14, 3)) == (255, 0, 0, 255)
    metadata = json.loads(metadata_bytes)
    validate_sheet_metadata(metadata)
    assert metadata["meta"]["schema_version"] == 1
    frames = metadata["animations"]["walk_down"]["frames"]
    assert [frame["rect"] for frame in frames] == [
        {"x": 1, "y": 1, "w": 8, "h": 8},
        {"x": 12, "y": 1, "w": 8, "h": 8},
    ]
    assert frames[1]["duration_ms"] == 250
    assert frames[1]["pivot"]["x"] == 2
    assert frames[1]["offset"]["y"] == -1
    assert frames[1]["events"] == ["footstep"]
    repeated = client.post("/api/v1/exports", json=payload).json()
    assert client.get(f"/api/v1/exports/{repeated['id']}/files/png").content == image_bytes
    assert client.get(f"/api/v1/exports/{repeated['id']}/files/json").content == metadata_bytes
    assert client.post("/api/v1/exports", json={
        **payload, "asset_id": other["id"],
    }).status_code == 422
    assert client.post("/api/v1/exports", json={
        "asset_id": asset["id"], "format": "png", "version_id": other["active_version_id"],
    }).status_code == 422
    assert client.post("/api/v1/exports", json={
        **payload, "scale": 3,
    }).status_code == 422
    get_engine().dispose()
    get_engine.cache_clear()
    assert len(client.get(f"/api/v1/projects/{project['id']}/exports").json()) == 2


def test_godot4_preset_keeps_sheet_contract_and_records_target(client: TestClient) -> None:
    _, asset = make_asset(client, "Godot Hero")
    clip = client.post(f"/api/v1/assets/{asset['id']}/animations", json={
        "name": "idle", "direction": "down", "fps": 8, "loop_mode": "once",
    }).json()
    frame = client.post(f"/api/v1/animations/{clip['id']}/frames", json={
        "asset_version_id": asset["active_version_id"], "duration_ms": 250,
    })
    assert frame.status_code == 201
    payload = {
        "asset_id": asset["id"], "format": "spritesheet", "animation_id": clip["id"],
        "scale": 2, "preset_id": "godot4",
    }
    response = client.post("/api/v1/exports", json=payload)
    assert response.status_code == 201
    record = response.json()
    assert record["preset_id"] == "godot4"
    assert record["config"]["preset_id"] == "godot4"
    metadata = client.get(f"/api/v1/exports/{record['id']}/files/json").json()
    validate_sheet_metadata(metadata)
    assert metadata["meta"]["preset_id"] == "godot4"
    assert metadata["meta"]["image"] == "sprite.png"
    assert metadata["animations"]["idle_down"]["frames"][0]["duration_ms"] == 250
    png_content = client.get(f"/api/v1/exports/{record['id']}/files/png").content
    with Image.open(BytesIO(png_content)) as image:
        assert image.size == (8, 8)
    assert client.post("/api/v1/exports", json={
        **payload, "preset_id": "unknown",
    }).status_code == 422
    assert client.post("/api/v1/exports", json={
        "asset_id": asset["id"], "format": "png", "preset_id": "godot4",
    }).status_code == 422


def test_gif_preview_uses_timeline_durations_and_loop(client: TestClient) -> None:
    _, asset = make_asset(client, "GIF Hero")
    blue = client.post(
        f"/api/v1/assets/{asset['id']}/versions",
        files={"file": ("blue.png", png((0, 0, 255, 255)), "image/png")},
    ).json()
    green = client.post(
        f"/api/v1/assets/{asset['id']}/versions",
        files={"file": ("green.png", png((0, 255, 0, 255)), "image/png")},
    ).json()
    clip = client.post(f"/api/v1/assets/{asset['id']}/animations", json={
        "name": "walk", "loop_mode": "ping_pong",
    }).json()
    for version_id, duration in (
        (asset["active_version_id"], 100), (blue["id"], 230), (green["id"], 150)
    ):
        response = client.post(f"/api/v1/animations/{clip['id']}/frames", json={
            "asset_version_id": version_id, "duration_ms": duration,
        })
        assert response.status_code == 201
    response = client.post("/api/v1/exports", json={
        "asset_id": asset["id"], "animation_id": clip["id"],
        "format": "gif", "scale": 2,
    })
    assert response.status_code == 201
    export_id = response.json()["id"]
    content = client.get(f"/api/v1/exports/{export_id}/files/gif")
    assert content.status_code == 200
    assert content.headers["content-type"] == "image/gif"
    assert client.get(f"/api/v1/exports/{export_id}/download").content == content.content
    with Image.open(BytesIO(content.content)) as image:
        assert image.size == (8, 8)
        assert image.n_frames == 4
        assert image.info["loop"] == 0
        assert image.info["duration"] == 100
        image.seek(1)
        assert image.info["duration"] == 230
        assert image.convert("RGBA").getpixel((4, 4))[:3] == (0, 0, 255)
        assert image.convert("RGBA").getpixel((0, 0))[3] == 0
        image.seek(2)
        assert image.info["duration"] == 150
        image.seek(3)
        assert image.info["duration"] == 230
    assert client.get(f"/api/v1/exports/{export_id}/files/png").status_code == 404

    client.patch(f"/api/v1/animations/{clip['id']}", json={"loop_mode": "once"})
    once = client.post("/api/v1/exports", json={
        "asset_id": asset["id"], "animation_id": clip["id"], "format": "gif",
    }).json()
    once_content = client.get(f"/api/v1/exports/{once['id']}/files/gif").content
    with Image.open(BytesIO(once_content)) as image:
        assert "loop" not in image.info


def test_changed_source_refuses_export_without_record(client: TestClient) -> None:
    project, asset = make_asset(client, "Changed Source")
    version = client.get(f"/api/v1/assets/{asset['id']}/versions").json()[0]
    source_path = Path(str(project["root_path"])) / version["file_path"]
    source_path.write_bytes(png((0, 255, 0, 255)))
    response = client.post("/api/v1/exports", json={
        "asset_id": asset["id"], "format": "png",
    })
    assert response.status_code == 422
    assert "changed after publication" in response.json()["detail"]
    assert client.get(f"/api/v1/projects/{project['id']}/exports").json() == []


def test_export_migration_up_and_down(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'migration.db'}"
    monkeypatch.setenv("AI_SPRITE_DATABASE_URL", database_url)
    get_settings.cache_clear()
    configuration = Config("alembic.ini")
    command.upgrade(configuration, "head")
    engine = create_engine(database_url)
    assert "export_records" in inspect(engine).get_table_names()
    command.downgrade(configuration, "0005")
    assert "export_records" not in inspect(engine).get_table_names()
    engine.dispose()
    get_settings.cache_clear()
