import json
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.assets import asset_service
from app.db.models import ExportRecord
from app.db.session import get_session
from app.services.animations import AnimationNotFoundError
from app.services.assets import AssetNotFoundError, AssetService
from app.services.exports import ExportNotFoundError, ExportService
from app.services.projects import ProjectNotFoundError

router = APIRouter(tags=["exports"])


class ExportCreate(BaseModel):
    asset_id: str
    format: Literal["png", "spritesheet", "gif"]
    version_id: str | None = None
    animation_id: str | None = None
    scale: Literal[1, 2, 4, 8] = 1
    columns: int = Field(default=8, ge=1, le=64)
    spacing: int = Field(default=0, ge=0, le=64)
    padding: int = Field(default=0, ge=0, le=64)


class ExportResponse(BaseModel):
    id: str
    project_id: str
    asset_id: str
    format: str
    config: dict[str, object]
    output_path: str
    checksum: str
    status: str
    created_at: datetime


def export_service(
    session: Annotated[Session, Depends(get_session)],
    assets: Annotated[AssetService, Depends(asset_service)],
) -> ExportService:
    return ExportService(session, assets)


ExportDependency = Annotated[ExportService, Depends(export_service)]


def export_response(record: ExportRecord) -> ExportResponse:
    return ExportResponse(
        id=record.id, project_id=record.project_id, asset_id=record.asset_id,
        format=record.format, config=json.loads(record.config_json),
        output_path=record.output_path, checksum=record.checksum,
        status=record.status, created_at=record.created_at,
    )


def export_error(error: ValueError) -> HTTPException:
    code = (
        status.HTTP_404_NOT_FOUND
        if isinstance(error, (ExportNotFoundError, AssetNotFoundError,
                              AnimationNotFoundError, ProjectNotFoundError))
        else status.HTTP_422_UNPROCESSABLE_CONTENT
    )
    return HTTPException(status_code=code, detail=str(error))


@router.get("/projects/{project_id}/exports", response_model=list[ExportResponse])
def list_exports(project_id: str, service: ExportDependency) -> list[ExportResponse]:
    try:
        return [export_response(record) for record in service.list_exports(project_id)]
    except ValueError as error:
        raise export_error(error) from error


@router.post("/exports", response_model=ExportResponse, status_code=201)
def create_export(payload: ExportCreate, service: ExportDependency) -> ExportResponse:
    try:
        if payload.format == "png":
            if payload.animation_id is not None:
                raise ValueError("PNG export does not use an animation.")
            record = service.create_png(payload.asset_id, payload.version_id, payload.scale)
        elif payload.format == "spritesheet":
            if payload.animation_id is None or payload.version_id is not None:
                raise ValueError("Spritesheet export requires an animation, not a version.")
            record = service.create_spritesheet(
                payload.asset_id, payload.animation_id, payload.scale,
                payload.columns, payload.spacing, payload.padding,
            )
        else:
            if payload.animation_id is None or payload.version_id is not None:
                raise ValueError("GIF export requires an animation, not a version.")
            record = service.create_gif(payload.asset_id, payload.animation_id, payload.scale)
        return export_response(record)
    except ValueError as error:
        raise export_error(error) from error


@router.get("/exports/{export_id}", response_model=ExportResponse)
def get_export(export_id: str, service: ExportDependency) -> ExportResponse:
    try:
        return export_response(service.get_export(export_id))
    except ValueError as error:
        raise export_error(error) from error


@router.get("/exports/{export_id}/files/{kind}", response_class=FileResponse)
def download_export(
    export_id: str, kind: Literal["png", "json", "gif"], service: ExportDependency
) -> FileResponse:
    try:
        path = service.get_file(export_id, kind)
        media_type = {
            "png": "image/png", "json": "application/json", "gif": "image/gif",
        }[kind]
        return FileResponse(path, media_type=media_type, filename=f"sprite-{export_id}.{kind}")
    except ValueError as error:
        raise export_error(error) from error


@router.get("/exports/{export_id}/download", response_class=FileResponse)
def download_primary(export_id: str, service: ExportDependency) -> FileResponse:
    try:
        record = service.get_export(export_id)
        kind: Literal["png", "gif"] = "gif" if record.format == "gif" else "png"
        return download_export(export_id, kind, service)
    except ValueError as error:
        raise export_error(error) from error
