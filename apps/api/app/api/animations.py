from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.assets import asset_service
from app.db.session import get_session
from app.services.animations import AnimationNotFoundError, AnimationService
from app.services.assets import AssetNotFoundError, AssetService

router = APIRouter(tags=["animations"])


class AnimationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    direction: str = Field(default="down", min_length=1, max_length=32)
    fps: int = Field(default=8, ge=1, le=60)
    loop_mode: Literal["loop", "once", "ping_pong"] = "loop"


class AnimationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    direction: str | None = Field(default=None, min_length=1, max_length=32)
    fps: int | None = Field(default=None, ge=1, le=60)
    loop_mode: Literal["loop", "once", "ping_pong"] | None = None


class AnimationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    asset_id: str
    name: str
    direction: str
    fps: int
    loop_mode: str
    canvas_width: int
    canvas_height: int
    created_at: datetime
    updated_at: datetime


class FrameCreate(BaseModel):
    asset_version_id: str
    duration_ms: int | None = Field(default=None, ge=1, le=60_000)


class FrameUpdate(BaseModel):
    duration_ms: int | None = Field(default=None, ge=1, le=60_000)
    offset_x: int | None = Field(default=None, ge=-4096, le=4096)
    offset_y: int | None = Field(default=None, ge=-4096, le=4096)
    pivot_x: int | None = Field(default=None, ge=-4096, le=4096)
    pivot_y: int | None = Field(default=None, ge=-4096, le=4096)
    event_name: str | None = Field(default=None, max_length=80)


class FrameResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    animation_id: str
    asset_version_id: str
    frame_index: int
    duration_ms: int
    offset_x: int
    offset_y: int
    pivot_x: int
    pivot_y: int
    event_name: str | None


class FrameOrder(BaseModel):
    frame_ids: list[str]


def animation_service(
    session: Annotated[Session, Depends(get_session)],
    assets: Annotated[AssetService, Depends(asset_service)],
) -> AnimationService:
    return AnimationService(session, assets)


AnimationDependency = Annotated[AnimationService, Depends(animation_service)]


def animation_error(error: ValueError) -> HTTPException:
    code = 404 if isinstance(error, (AnimationNotFoundError, AssetNotFoundError)) else 422
    return HTTPException(status_code=code, detail=str(error))


@router.get("/assets/{asset_id}/animations", response_model=list[AnimationResponse])
def list_animations(asset_id: str, service: AnimationDependency) -> list[AnimationResponse]:
    try:
        return [
            AnimationResponse.model_validate(item)
            for item in service.list_animations(asset_id)
        ]
    except ValueError as error:
        raise animation_error(error) from error


@router.post("/assets/{asset_id}/animations", response_model=AnimationResponse, status_code=201)
def create_animation(
    asset_id: str, payload: AnimationCreate, service: AnimationDependency
) -> AnimationResponse:
    try:
        animation = service.create_animation(asset_id, **payload.model_dump())
        return AnimationResponse.model_validate(animation)
    except ValueError as error:
        raise animation_error(error) from error


@router.get("/animations/{animation_id}", response_model=AnimationResponse)
def get_animation(animation_id: str, service: AnimationDependency) -> AnimationResponse:
    try:
        return AnimationResponse.model_validate(service.get_animation(animation_id))
    except ValueError as error:
        raise animation_error(error) from error


@router.patch("/animations/{animation_id}", response_model=AnimationResponse)
def update_animation(
    animation_id: str, payload: AnimationUpdate, service: AnimationDependency
) -> AnimationResponse:
    try:
        changes = payload.model_dump(exclude_unset=True, exclude_none=True)
        return AnimationResponse.model_validate(service.update_animation(animation_id, changes))
    except ValueError as error:
        raise animation_error(error) from error


@router.delete("/animations/{animation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_animation(animation_id: str, service: AnimationDependency) -> Response:
    try:
        service.delete_animation(animation_id)
        return Response(status_code=204)
    except ValueError as error:
        raise animation_error(error) from error


@router.get("/animations/{animation_id}/frames", response_model=list[FrameResponse])
def list_frames(animation_id: str, service: AnimationDependency) -> list[FrameResponse]:
    try:
        return [FrameResponse.model_validate(frame) for frame in service.list_frames(animation_id)]
    except ValueError as error:
        raise animation_error(error) from error


@router.post("/animations/{animation_id}/frames", response_model=FrameResponse, status_code=201)
def add_frame(
    animation_id: str, payload: FrameCreate, service: AnimationDependency
) -> FrameResponse:
    try:
        frame = service.add_frame(animation_id, payload.asset_version_id, payload.duration_ms)
        return FrameResponse.model_validate(frame)
    except ValueError as error:
        raise animation_error(error) from error


@router.post(
    "/animation-frames/{frame_id}/duplicate", response_model=FrameResponse, status_code=201
)
def duplicate_frame(frame_id: str, service: AnimationDependency) -> FrameResponse:
    try:
        return FrameResponse.model_validate(service.duplicate_frame(frame_id))
    except ValueError as error:
        raise animation_error(error) from error


@router.patch("/animation-frames/{frame_id}", response_model=FrameResponse)
def update_frame(
    frame_id: str, payload: FrameUpdate, service: AnimationDependency
) -> FrameResponse:
    try:
        changes = payload.model_dump(exclude_unset=True)
        if "event_name" not in changes:
            changes = {key: value for key, value in changes.items() if value is not None}
        else:
            changes = {
                key: value for key, value in changes.items()
                if value is not None or key == "event_name"
            }
        return FrameResponse.model_validate(service.update_frame(frame_id, changes))
    except ValueError as error:
        raise animation_error(error) from error


@router.delete("/animation-frames/{frame_id}", status_code=204)
def delete_frame(frame_id: str, service: AnimationDependency) -> Response:
    try:
        service.delete_frame(frame_id)
        return Response(status_code=204)
    except ValueError as error:
        raise animation_error(error) from error


@router.post("/animations/{animation_id}/frames/reorder", response_model=list[FrameResponse])
def reorder_frames(
    animation_id: str, payload: FrameOrder, service: AnimationDependency
) -> list[FrameResponse]:
    try:
        return [
            FrameResponse.model_validate(frame)
            for frame in service.reorder_frames(animation_id, payload.frame_ids)
        ]
    except ValueError as error:
        raise animation_error(error) from error
