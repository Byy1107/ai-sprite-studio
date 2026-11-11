from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.domain.projects import InvalidProjectNameError, ProjectDraft
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


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: str, service: ProjectServiceDependency) -> Response:
    try:
        service.delete_project(project_id)
    except ProjectNotFoundError as error:
        raise translate_project_error(error) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
