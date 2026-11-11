from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.config import Settings, get_settings

router = APIRouter(prefix="/api/v1")


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    environment: str
    workspace_configured: bool
    database_configured: bool
    comfyui_configured: bool


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="ai-sprite-studio-api",
        version="0.1.0",
        environment=settings.environment,
        workspace_configured=bool(settings.workspace_dir),
        database_configured=settings.database_url.startswith("sqlite"),
        comfyui_configured=bool(settings.comfyui_http_url),
    )
