from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint() -> None:
    response = TestClient(app).get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "ai-sprite-studio-api",
        "version": "0.1.0",
        "environment": "development",
        "workspace_configured": True,
        "database_configured": True,
        "comfyui_configured": True,
    }


def test_health_docs_are_available() -> None:
    response = TestClient(app).get("/api/docs")

    assert response.status_code == 200

