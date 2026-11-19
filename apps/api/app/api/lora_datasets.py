from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.assets import asset_service
from app.db.session import get_session
from app.services.assets import AssetNotFoundError, AssetService
from app.services.lora_datasets import LoraDatasetService, LoraSample
from app.services.projects import ProjectNotFoundError

router = APIRouter(tags=["lora-datasets"])


class DatasetSample(BaseModel):
    version_id: str
    caption: str = Field(min_length=1, max_length=240)


class DatasetCreate(BaseModel):
    samples: list[DatasetSample] = Field(min_length=1, max_length=64)
    resolution: int = 512
    background: str = "FFFFFF"


def dataset_service(
    session: Annotated[Session, Depends(get_session)],
    assets: Annotated[AssetService, Depends(asset_service)],
) -> LoraDatasetService:
    return LoraDatasetService(session, assets)


@router.post("/projects/{project_id}/lora-dataset")
def create_dataset(
    project_id: str,
    payload: DatasetCreate,
    service: Annotated[LoraDatasetService, Depends(dataset_service)],
) -> Response:
    try:
        content = service.build_archive(
            project_id,
            [LoraSample(sample.version_id, sample.caption) for sample in payload.samples],
            payload.resolution,
            payload.background,
        )
    except (AssetNotFoundError, ProjectNotFoundError, ValueError) as error:
        code = 404 if isinstance(error, (AssetNotFoundError, ProjectNotFoundError)) else 422
        raise HTTPException(status_code=code, detail=str(error)) from error
    return Response(
        content,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="lora-dataset.zip"'},
        status_code=status.HTTP_200_OK,
    )
