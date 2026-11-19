from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.domain.projects import InvalidProjectNameError, ProjectDraft
from app.services.project_backup import MAX_BACKUP_BYTES, ProjectBackupService
from app.services.projects import DuplicateProjectError, ProjectNotFoundError, ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    description: str
    root_path: str
    schema_version: int
    created_at: datetime
    updated_at: datetime
    last_opened_at: datetime | None


class ProjectIntegrityResponse(BaseModel):
    project_id: str
    status: str
    issues: list[dict[str, str]]


def project_service(
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ProjectService:
    return ProjectService(session, settings.workspace_dir)


ProjectServiceDependency = Annotated[ProjectService, Depends(project_service)]


def translate_project_error(error: ValueError) -> HTTPException:
    if isinstance(error, ProjectNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    if isinstance(error, DuplicateProjectError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error))


@router.get("", response_model=list[ProjectResponse])
def list_projects(service: ProjectServiceDependency) -> list[ProjectResponse]:
    return [ProjectResponse.model_validate(project) for project in service.list_projects()]


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, service: ProjectServiceDependency) -> ProjectResponse:
    try:
        project = service.create_project(
            ProjectDraft(name=payload.name, slug="", description=payload.description)
        )
    except (DuplicateProjectError, InvalidProjectNameError) as error:
        raise translate_project_error(error) from error
    return ProjectResponse.model_validate(project)


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, service: ProjectServiceDependency) -> ProjectResponse:
    try:
        return ProjectResponse.model_validate(service.get_project(project_id))
    except ProjectNotFoundError as error:
        raise translate_project_error(error) from error


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: str, payload: ProjectUpdate, service: ProjectServiceDependency
) -> ProjectResponse:
    try:
        project = service.update_project(project_id, payload.name, payload.description)
    except (DuplicateProjectError, InvalidProjectNameError, ProjectNotFoundError) as error:
        raise translate_project_error(error) from error
    return ProjectResponse.model_validate(project)


@router.post("/{project_id}/open", response_model=ProjectResponse)
def open_project(project_id: str, service: ProjectServiceDependency) -> ProjectResponse:
    try:
        return ProjectResponse.model_validate(service.open_project(project_id))
    except ProjectNotFoundError as error:
        raise translate_project_error(error) from error


@router.get("/{project_id}/integrity", response_model=ProjectIntegrityResponse)
def inspect_project_integrity(
    project_id: str, service: ProjectServiceDependency
) -> ProjectIntegrityResponse:
    try:
        issues = service.inspect_integrity(project_id)
    except ProjectNotFoundError as error:
        raise translate_project_error(error) from error
    return ProjectIntegrityResponse(
        project_id=project_id, status="issues" if issues else "ok", issues=issues,
    )


@router.get("/{project_id}/backup")
def backup_project(project_id: str, service: ProjectServiceDependency) -> Response:
    try:
        project = service.get_project(project_id)
        content = ProjectBackupService(
            service.session, service.storage.workspace_dir
        ).create_backup(project_id)
    except ProjectNotFoundError as error:
        raise translate_project_error(error) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return Response(
        content=content, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{project.slug}.zip"'},
    )


@router.post("/restore", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def restore_project(
    service: ProjectServiceDependency, file: Annotated[UploadFile, File()]
) -> ProjectResponse:
    content = await file.read(MAX_BACKUP_BYTES + 1)
    try:
        project = ProjectBackupService(
            service.session, service.storage.workspace_dir
        ).restore_backup(content)
    except IntegrityError as error:
        raise HTTPException(status_code=409, detail="Project or record already exists.") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}/cache")
def clear_project_cache(project_id: str, service: ProjectServiceDependency) -> dict[str, int]:
    try:
        return {"removed_files": service.clear_cache(project_id)}
    except (ProjectNotFoundError, ValueError) as error:
        raise translate_project_error(error) from error


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: str, service: ProjectServiceDependency) -> Response:
    try:
        service.delete_project(project_id)
    except ProjectNotFoundError as error:
        raise translate_project_error(error) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
