import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw
from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from app.adapters.ai import ComfyUIProvider, FakeAIProvider
from app.core.config import get_settings
from app.db.models import (
    AssetRecord,
    AssetVersionRecord,
    GenerationJobRecord,
    GenerationResultRecord,
    ProjectRecord,
    utc_now,
)
from app.domain.generation import (
    AIProviderAdapter,
    GenerationRequest,
    GenerationStatus,
    UnsupportedGenerationOption,
)
from app.services.asset_storage import MAX_IMPORT_BYTES, AssetStorage

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="sprite-generation")


def configured_provider() -> AIProviderAdapter:
    settings = get_settings()
    if settings.ai_provider == "comfyui":
        return ComfyUIProvider(
            settings.comfyui_http_url,
            settings.comfyui_checkpoint,
            settings.ai_timeout_seconds,
        )
    return FakeAIProvider()


def enqueue_generation(job_id: str) -> None:
    _executor.submit(_run_generation_job, job_id)


def _run_generation_job(job_id: str) -> None:
    from app.db.session import get_engine

    factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    with factory() as session:
        try:
            GenerationService(session, configured_provider()).run(job_id)
        except Exception:
            return


class GenerationService:
    def __init__(self, session: Session, provider: AIProviderAdapter | None = None) -> None:
        self.session = session
        self.provider = provider or FakeAIProvider()

    def recover_interrupted(self) -> None:
        self.session.execute(
            update(GenerationJobRecord)
            .where(
                GenerationJobRecord.status.in_(
                    [GenerationStatus.QUEUED.value, GenerationStatus.RUNNING.value]
                )
            )
            .values(
                status=GenerationStatus.FAILED.value,
                error_code="app_restarted",
                error_message="The local app stopped before this job completed.",
                finished_at=utc_now(),
            )
        )
        self.session.commit()

    def create(self, request: GenerationRequest) -> GenerationJobRecord:
        project = self.session.get(ProjectRecord, request.project_id)
        if project is None or project.deleted_at is not None:
            raise ValueError("Project not found")
        if request.lora_name is not None and self.provider.provider_id != "comfyui":
            raise UnsupportedGenerationOption("LoRA requires the ComfyUI provider")
        if request.ipadapter_model is not None or request.clip_vision_model is not None:
            if self.provider.provider_id != "comfyui":
                raise UnsupportedGenerationOption("IP-Adapter requires the ComfyUI provider")
            if not request.ipadapter_model or not request.clip_vision_model:
                raise UnsupportedGenerationOption(
                    "IP-Adapter requires both an adapter and a CLIP vision model"
                )
            if request.reference_asset_id is None:
                raise UnsupportedGenerationOption("IP-Adapter requires a reference asset")
        if request.operation not in {"text_to_sprite", "variation", "inpaint"}:
            raise UnsupportedGenerationOption("Unknown generation operation")
        if request.operation != "text_to_sprite":
            if self.provider.provider_id != "comfyui":
                raise UnsupportedGenerationOption("AI edit requires the ComfyUI provider")
            if not request.asset_id or request.reference_asset_id != request.asset_id:
                raise UnsupportedGenerationOption("AI edit requires the target asset as its source")
        bounds = (request.mask_x, request.mask_y, request.mask_width, request.mask_height)
        if request.operation == "inpaint":
            if any(value is None for value in bounds):
                raise UnsupportedGenerationOption("Inpainting requires a rectangle selection")
            x, y, width, height = bounds
            assert x is not None and y is not None and width is not None and height is not None
            if min(x, y) < 0 or min(width, height) < 1:
                raise UnsupportedGenerationOption("Invalid inpaint selection")
            if x + width > request.width or y + height > request.height:
                raise UnsupportedGenerationOption("Inpaint selection exceeds the asset canvas")
        elif any(value is not None for value in bounds):
            raise UnsupportedGenerationOption("Selection is only supported for inpainting")
        if request.controlnet_name is not None:
            if self.provider.provider_id != "comfyui":
                raise UnsupportedGenerationOption("ControlNet requires the ComfyUI provider")
            if request.reference_asset_id is None:
                raise UnsupportedGenerationOption("ControlNet requires a reference asset")
            if request.controlnet_start >= request.controlnet_end:
                raise UnsupportedGenerationOption("ControlNet start must be before end")
        for asset_id in (request.asset_id, request.reference_asset_id):
            if asset_id is not None:
                asset = self.session.get(AssetRecord, asset_id)
                if (
                    asset is None
                    or asset.deleted_at is not None
                    or asset.project_id != request.project_id
                ):
                    raise ValueError("Asset not found in this project")
        if request.reference_version_id is not None and request.reference_asset_id is None:
            raise ValueError("Reference version requires a reference asset")
        if request.reference_asset_id is not None:
            reference = self.session.get(AssetRecord, request.reference_asset_id)
            assert reference is not None
            version_id = request.reference_version_id or reference.active_version_id
            version = self.session.get(AssetVersionRecord, version_id) if version_id else None
            if version is None or version.asset_id != reference.id:
                raise ValueError("Reference version not found for this asset")
            request = replace(request, reference_version_id=version.id)
            if (
                request.operation != "text_to_sprite"
                and (request.width, request.height) != (version.width, version.height)
            ):
                raise UnsupportedGenerationOption("AI edit must match the source dimensions")
        record = GenerationJobRecord(
            project_id=request.project_id,
            asset_id=request.asset_id,
            provider=self.provider.provider_id,
            workflow_id=(
                "sd15-text-to-sprite"
                + ("-lora" if request.lora_name else "")
                + ("-controlnet" if request.controlnet_name else "")
                + ("-ipadapter" if request.ipadapter_model else "")
                + (f"-{request.operation}" if request.operation != "text_to_sprite" else "")
                if self.provider.provider_id == "comfyui" else "fake-text-to-sprite"
            ),
            workflow_version="2" if self.provider.provider_id == "comfyui" else "1",
            status=GenerationStatus.QUEUED.value,
            request_json=json.dumps(request.__dict__, sort_keys=True),
        )
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def run(self, job_id: str) -> GenerationJobRecord:
        job = self.get(job_id)
        if job.status == GenerationStatus.CANCELED.value:
            return job
        job.status = GenerationStatus.RUNNING.value
        job.progress = 0.25
        job.started_at = utc_now()
        self.session.commit()
        try:
            request = GenerationRequest(**json.loads(job.request_json))
            if (
                request.controlnet_name or request.ipadapter_model
                or request.operation != "text_to_sprite"
            ):
                provider_result = self.provider.generate(
                    request, reference_image=self._reference_content(request)
                )
            else:
                provider_result = self.provider.generate(request)
            metadata = dict(provider_result.metadata)
            if request.operation == "inpaint":
                provider_result = replace(
                    provider_result,
                    image_bytes=self._composite_inpaint(
                        request, self._reference_content(request), provider_result.image_bytes
                    ),
                )
            if request.operation != "text_to_sprite":
                image = AssetStorage().inspect_png(provider_result.image_bytes)
                if (image.width, image.height) != (request.width, request.height):
                    raise ValueError("AI edit result dimensions differ from the source")
            if request.reference_asset_id is not None:
                applied = bool(
                    metadata.get("controlnet_applied") or metadata.get("ipadapter_applied")
                    or metadata.get("edit_applied")
                )
                metadata["reference_conditioning_applied"] = applied
                if not applied:
                    metadata["warnings"] = [
                        "Reference stored only; this workflow does not apply "
                        "reference conditioning."
                    ]
            self.session.refresh(job)
            if job.status == GenerationStatus.CANCELED.value:
                return job
            project = self.session.get(ProjectRecord, request.project_id)
            if project is None:
                raise ValueError("Project not found")
            relative_path = Path("candidates") / job.id / "result.png"
            output_path = Path(project.root_path) / relative_path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = output_path.with_suffix(".tmp")
            temporary_path.write_bytes(provider_result.image_bytes)
            temporary_path.replace(output_path)
            result = GenerationResultRecord(
                job_id=job.id,
                file_path=relative_path.as_posix(),
                thumbnail_path=relative_path.as_posix(),
                seed=provider_result.seed,
                metadata_json=json.dumps(metadata, sort_keys=True),
            )
            self.session.add(result)
            job.status = GenerationStatus.SUCCEEDED.value
            job.progress = 1.0
            job.finished_at = utc_now()
            self.session.commit()
            self.session.refresh(job)
            return job
        except Exception as error:
            job.status = GenerationStatus.FAILED.value
            job.error_code = "provider_error"
            job.error_message = str(error)
            job.finished_at = utc_now()
            self.session.commit()
            raise

    def _reference_content(self, request: GenerationRequest) -> bytes:
        version = (
            self.session.get(AssetVersionRecord, request.reference_version_id)
            if request.reference_version_id else None
        )
        asset = (
            self.session.get(AssetRecord, request.reference_asset_id)
            if request.reference_asset_id else None
        )
        project = self.session.get(ProjectRecord, request.project_id)
        if (
            version is None or asset is None or project is None
            or asset.deleted_at is not None or project.deleted_at is not None
            or version.asset_id != asset.id or asset.project_id != project.id
        ):
            raise ValueError("Pinned reference is no longer available in this project")
        root = Path(project.root_path).resolve()
        path = (root / version.file_path).resolve()
        if not path.is_relative_to(root):
            raise ValueError("Reference file is outside the project")
        with path.open("rb") as reference_file:
            content = reference_file.read(MAX_IMPORT_BYTES + 1)
        AssetStorage().inspect_png(content)
        if sha256(content).hexdigest() != version.checksum:
            raise ValueError("Pinned reference file has changed")
        return content

    @staticmethod
    def _composite_inpaint(request: GenerationRequest, source: bytes, candidate: bytes) -> bytes:
        AssetStorage().inspect_png(candidate)
        with (
            Image.open(BytesIO(source)) as original_image,
            Image.open(BytesIO(candidate)) as edit_image,
        ):
            if original_image.size != edit_image.size:
                raise ValueError("Inpaint result dimensions differ from the source")
            original = original_image.convert("RGBA")
            edit = edit_image.convert("RGBA")
            mask = Image.new("L", original.size, 0)
            assert request.mask_x is not None and request.mask_y is not None
            assert request.mask_width is not None and request.mask_height is not None
            ImageDraw.Draw(mask).rectangle(
                (request.mask_x, request.mask_y,
                 request.mask_x + request.mask_width - 1,
                 request.mask_y + request.mask_height - 1), fill=255,
            )
            output = BytesIO()
            Image.composite(edit, original, mask).save(output, format="PNG")
            return output.getvalue()

    def cancel(self, job_id: str) -> GenerationJobRecord:
        job = self.get(job_id)
        if job.status not in {GenerationStatus.SUCCEEDED.value, GenerationStatus.FAILED.value}:
            if job.status == GenerationStatus.RUNNING.value:
                self.provider.cancel()
            job.status = GenerationStatus.CANCELED.value
            job.finished_at = utc_now()
            self.session.commit()
            self.session.refresh(job)
        return job

    def get(self, job_id: str) -> GenerationJobRecord:
        job = self.session.get(GenerationJobRecord, job_id)
        if job is None:
            raise ValueError("Generation job not found")
        return job

    def list_jobs(self, project_id: str | None = None) -> list[GenerationJobRecord]:
        query = select(GenerationJobRecord).order_by(GenerationJobRecord.created_at.desc())
        if project_id is not None:
            query = query.where(GenerationJobRecord.project_id == project_id)
        return list(self.session.scalars(query))

    def results(self, job_id: str) -> list[GenerationResultRecord]:
        self.get(job_id)
        query = select(GenerationResultRecord).where(GenerationResultRecord.job_id == job_id)
        return list(self.session.scalars(query))
