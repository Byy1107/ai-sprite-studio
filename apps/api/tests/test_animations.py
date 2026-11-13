from io import BytesIO
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
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


def make_asset(client: TestClient, name: str, asset_type: str = "character") -> dict[str, object]:
    project = client.post("/api/v1/projects", json={"name": name}).json()
    image = BytesIO()
    Image.new("RGBA", (16, 16), (120, 30, 30, 255)).save(image, "PNG")
    response = client.post(
        f"/api/v1/projects/{project['id']}/assets/import",
        data={"name": name, "asset_type": asset_type, "style": "eight_bit"},
        files={"file": ("sprite.png", image.getvalue(), "image/png")},
    )
    assert response.status_code == 201
    return response.json()


def test_animation_timeline_persists_and_rejects_foreign_frames(client: TestClient) -> None:
    asset = make_asset(client, "Hero")
    foreign = make_asset(client, "Other")
    item = make_asset(client, "Potion", "item")
    rejected = client.post(f"/api/v1/assets/{item['id']}/animations", json={"name": "idle"})
    assert rejected.status_code == 422
    created = client.post(
        f"/api/v1/assets/{asset['id']}/animations", json={"name": "walk", "fps": 10}
    )
    assert created.status_code == 201
    clip = created.json()
    assert (clip["canvas_width"], clip["canvas_height"]) == (16, 16)
    first = client.post(
        f"/api/v1/animations/{clip['id']}/frames",
        json={"asset_version_id": asset["active_version_id"]},
    )
    assert first.status_code == 201
    assert first.json()["duration_ms"] == 100
    assert client.post(
        f"/api/v1/animations/{clip['id']}/frames",
        json={"asset_version_id": foreign["active_version_id"]},
    ).status_code == 422
    duplicate = client.post(f"/api/v1/animation-frames/{first.json()['id']}/duplicate")
    assert duplicate.status_code == 201
    second_id = duplicate.json()["id"]
    edited = client.patch(
        f"/api/v1/animation-frames/{second_id}",
        json={"duration_ms": 270, "pivot_x": 8, "offset_y": -2, "event_name": "footstep"},
    )
    assert edited.status_code == 200
    reordered = client.post(
        f"/api/v1/animations/{clip['id']}/frames/reorder",
        json={"frame_ids": [second_id, first.json()["id"]]},
    )
    assert reordered.status_code == 200
    assert [frame["frame_index"] for frame in reordered.json()] == [0, 1]
    assert client.post(
        f"/api/v1/animations/{clip['id']}/frames/reorder",
        json={"frame_ids": [second_id, second_id]},
    ).status_code == 422
    assert client.get(f"/api/v1/animations/{clip['id']}/frames").json()[0]["id"] == second_id
    assert client.get(f"/api/v1/animations/{clip['id']}/frames").json()[0]["pivot_x"] == 8
    assert client.get(f"/api/v1/animations/{clip['id']}/frames").json()[0]["duration_ms"] == 270
    assert client.patch(
        f"/api/v1/animation-frames/{second_id}", json={"event_name": None}
    ).json()["event_name"] is None
    get_engine().dispose()
    get_engine.cache_clear()
    assert client.get(f"/api/v1/animations/{clip['id']}/frames").json()[0]["id"] == second_id
    assert client.get(f"/api/v1/animations/{clip['id']}/frames").json()[0]["offset_y"] == -2
    assert client.delete(f"/api/v1/animation-frames/{second_id}").status_code == 204
    assert client.get(f"/api/v1/animations/{clip['id']}/frames").json()[0]["frame_index"] == 0
    assert client.delete(f"/api/v1/animations/{clip['id']}").status_code == 204
    assert client.get(f"/api/v1/animations/{clip['id']}").status_code == 404


def test_animation_migration_up_and_down(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'migration.db'}"
    monkeypatch.setenv("AI_SPRITE_DATABASE_URL", database_url)
    get_settings.cache_clear()
    configuration = Config("alembic.ini")
    command.upgrade(configuration, "head")
    engine = create_engine(database_url)
    assert {"animations", "animation_frames"} <= set(inspect(engine).get_table_names())
    command.downgrade(configuration, "0004")
    assert "animations" not in inspect(engine).get_table_names()
    engine.dispose()
    get_settings.cache_clear()
