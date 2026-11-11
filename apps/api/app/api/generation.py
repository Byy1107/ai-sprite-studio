import json
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.models import GenerationJobRecord, GenerationResultRecord
from app.db.session import get_session
from app.domain.generation import GenerationRequest
from app.services.generation import GenerationService, enqueue_generation

router = APIRouter(tags=["generation"])
SessionDependency = Annotated[Session, Depends(get_session)]


class GenerationJobCreate(BaseModel):
    project_id: str
    asset_id: str | None = None
    prompt: str = Field(min_length=1, max_length=1000)
    asset_type: Literal["character", "item", "environment", "tileset"]
    style: Literal["micro_pixel", "eight_bit"]
    width: int = Field(default=32, ge=8, le=256)
    height: int = Field(default=32, ge=8, le=256)
    seed: int = Field(default=1, ge=0, le=2_147_483_647)


class GenerationJobResponse(BaseModel):
    id: str
    project_id: str
    asset_id: str | None
    provider: str
    workflow_id: str
    workflow_version: str
    status: str
    request: dict[str, object]
    progress: float
    error_code: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class GenerationResultResponse(BaseModel):
    id: str
    job_id: str
    file_path: str
    thumbnail_path: str
    seed: int
    metadata: dict[str, object]
    selected: bool
    created_at: datetime


def job_response(record: GenerationJobRecord) -> GenerationJobResponse:
    return GenerationJobResponse(
        id=record.id,
        project_id=record.project_id,
        asset_id=record.asset_id,
        provider=record.provider,
        workflow_id=record.workflow_id,
        workflow_version=record.workflow_version,
        status=record.status,
        request=json.loads(record.request_json),
        progress=record.progress,
        error_code=record.error_code,
        error_message=record.error_message,
        created_at=record.created_at,
        started_at=record.started_at,
        finished_at=record.finished_at,
    )


def result_response(record: GenerationResultRecord) -> GenerationResultResponse:
    return GenerationResultResponse(
        id=record.id,
        job_id=record.job_id,
        file_path=record.file_path,
        thumbnail_path=record.thumbnail_path,
        seed=record.seed,
        metadata=json.loads(record.metadata_json),
        selected=bool(record.selected),
        created_at=record.created_at,
    )


@router.post(
    "/generation-jobs",
    response_model=GenerationJobResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_generation_job(payload: GenerationJobCreate, session: SessionDependency) -> object:
    service = GenerationService(session)
    try:
        record = service.create(GenerationRequest(**payload.model_dump()))
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    response = job_response(record)
    enqueue_generation(record.id)
    return response


@router.get("/generation-jobs", response_model=list[GenerationJobResponse])
def list_generation_jobs(
    session: SessionDependency, project_id: Annotated[str | None, Query()] = None
) -> list[GenerationJobResponse]:
    return [job_response(record) for record in GenerationService(session).list_jobs(project_id)]


@router.get("/generation-jobs/{job_id}", response_model=GenerationJobResponse)
def get_generation_job(job_id: str, session: SessionDependency) -> GenerationJobResponse:
    try:
        return job_response(GenerationService(session).get(job_id))
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/generation-jobs/{job_id}/cancel", response_model=GenerationJobResponse)
def cancel_generation_job(job_id: str, session: SessionDependency) -> GenerationJobResponse:
    try:
        return job_response(GenerationService(session).cancel(job_id))
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get(
    "/generation-jobs/{job_id}/results", response_model=list[GenerationResultResponse]
)
def list_generation_results(
    job_id: str, session: SessionDependency
) -> list[GenerationResultResponse]:
    try:
        return [
            result_response(record) for record in GenerationService(session).results(job_id)
        ]
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
