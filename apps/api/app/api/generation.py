import json
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import GenerationJobRecord, GenerationResultRecord, ProjectRecord
from app.db.session import get_session
from app.domain.generation import GenerationRequest, UnsupportedGenerationOption
from app.domain.generation_presets import preset_by_id, serialized_presets
from app.services.assets import AssetService
from app.services.generation import GenerationService, configured_provider, enqueue_generation

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
    preset_id: str | None = None
    negative_prompt: str = Field(default="blur, anti-aliasing", max_length=1000)
    reference_asset_id: str | None = None
    reference_version_id: str | None = None
    reference_weight: float = Field(default=1.0, ge=0, le=2, allow_inf_nan=False)
    lora_name: str | None = Field(default=None, min_length=1, max_length=255)
    lora_weight: float = Field(default=1.0, ge=0, le=2, allow_inf_nan=False)
    controlnet_name: str | None = Field(default=None, min_length=1, max_length=255)
    controlnet_strength: float = Field(default=1.0, ge=0, le=2, allow_inf_nan=False)
    controlnet_start: float = Field(default=0.0, ge=0, le=1, allow_inf_nan=False)
    controlnet_end: float = Field(default=1.0, ge=0, le=1, allow_inf_nan=False)
    ipadapter_model: str | None = Field(default=None, min_length=1, max_length=255)
    clip_vision_model: str | None = Field(default=None, min_length=1, max_length=255)
    operation: Literal["text_to_sprite", "variation", "inpaint"] = "text_to_sprite"
    mask_x: int | None = Field(default=None, ge=0, le=255)
    mask_y: int | None = Field(default=None, ge=0, le=255)
    mask_width: int | None = Field(default=None, ge=1, le=256)
    mask_height: int | None = Field(default=None, ge=1, le=256)


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


@router.get("/generation-presets")
def list_generation_presets() -> list[dict[str, object]]:
    return serialized_presets()


@router.post(
    "/generation-jobs",
    response_model=GenerationJobResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_generation_job(payload: GenerationJobCreate, session: SessionDependency) -> object:
    if payload.preset_id:
        preset = preset_by_id(payload.preset_id)
        if preset is None:
            raise HTTPException(status_code=422, detail="Generation preset not found")
        if preset.asset_type != payload.asset_type:
            raise HTTPException(status_code=422, detail="Preset does not match asset type")
    service = GenerationService(session, configured_provider())
    try:
        record = service.create(GenerationRequest(**payload.model_dump()))
    except UnsupportedGenerationOption as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
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


@router.post("/generation-results/{result_id}/accept", status_code=status.HTTP_201_CREATED)
def accept_generation_result(
    result_id: str,
    session: SessionDependency,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    result = session.get(GenerationResultRecord, result_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Generation result not found")
    job = session.get(GenerationJobRecord, result.job_id)
    if job is None or job.asset_id is None:
        raise HTTPException(status_code=422, detail="The generation job is not linked to an asset")
    project = session.get(ProjectRecord, job.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        version = AssetService(session, settings.workspace_dir).create_generated_version(
            job.asset_id, (Path(project.root_path) / result.file_path).read_bytes(), job.id
        )
    except (ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    result.selected = 1
    session.commit()
    return {"asset_id": job.asset_id, "version_id": version.id, "source": version.source}
