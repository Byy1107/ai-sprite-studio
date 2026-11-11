from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.domain.assets import AssetStyle, AssetType, InvalidAssetError
from app.services.assets import AssetNotFoundError, AssetService
from app.services.projects import ProjectNotFoundError

router = APIRouter(tags=["assets"])


class AssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    name: str
    asset_type: str
    style: str
    width: int
    height: int
    color_mode: str
    active_version_id: str | None
    thumbnail_path: str
    created_at: datetime
    updated_at: datetime


class AssetVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    asset_id: str
    version_number: int
    parent_version_id: str | None
    file_path: str
    checksum: str
    width: int
    height: int
    source: str
    change_summary: str
    created_at: datetime


def asset_service(
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AssetService:
    return AssetService(session, settings.workspace_dir)


AssetServiceDependency = Annotated[AssetService, Depends(asset_service)]


def asset_error(error: ValueError) -> HTTPException:
    if isinstance(error, (AssetNotFoundError, ProjectNotFoundError)):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error))


@router.get("/projects/{project_id}/assets", response_model=list[AssetResponse])
def list_assets(project_id: str, service: AssetServiceDependency) -> list[AssetResponse]:
    try:
        return [AssetResponse.model_validate(asset) for asset in service.list_assets(project_id)]
    except ProjectNotFoundError as error:
        raise asset_error(error) from error


@router.post(
    "/projects/{project_id}/assets/import",
    response_model=AssetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_asset(
    project_id: str,
    service: AssetServiceDependency,
    name: Annotated[str, Form(min_length=1, max_length=120)],
    asset_type: Annotated[AssetType, Form()],
    style: Annotated[AssetStyle, Form()],
    file: Annotated[UploadFile, File()],
) -> AssetResponse:
    try:
        asset = service.import_png(
            project_id, name, asset_type, style, await file.read()
        )
        return AssetResponse.model_validate(asset)
    except (InvalidAssetError, ProjectNotFoundError) as error:
        raise asset_error(error) from error


@router.get("/assets/{asset_id}", response_model=AssetResponse)
def get_asset(asset_id: str, service: AssetServiceDependency) -> AssetResponse:
    try:
        return AssetResponse.model_validate(service.get_asset(asset_id))
    except AssetNotFoundError as error:
        raise asset_error(error) from error


@router.get("/assets/{asset_id}/versions", response_model=list[AssetVersionResponse])
def list_versions(
    asset_id: str, service: AssetServiceDependency
) -> list[AssetVersionResponse]:
    try:
        return [
            AssetVersionResponse.model_validate(version)
            for version in service.list_versions(asset_id)
        ]
    except AssetNotFoundError as error:
        raise asset_error(error) from error


@router.post(
    "/assets/{asset_id}/versions/{version_id}/restore",
    response_model=AssetVersionResponse,
)
def restore_version(
    asset_id: str, version_id: str, service: AssetServiceDependency
) -> AssetVersionResponse:
    try:
        return AssetVersionResponse.model_validate(service.restore_version(asset_id, version_id))
    except AssetNotFoundError as error:
        raise asset_error(error) from error
