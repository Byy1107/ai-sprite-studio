from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.assets import router as assets_router
from app.api.generation import router as generation_router
from app.api.projects import router as projects_router
from app.core.config import Settings, get_settings

router = APIRouter(prefix="/api/v1")
router.include_router(assets_router)
router.include_router(generation_router)
router.include_router(projects_router)


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
