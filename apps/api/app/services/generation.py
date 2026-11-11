import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from app.adapters.ai import FakeAIProvider
from app.db.models import (
    GenerationJobRecord,
    GenerationResultRecord,
    ProjectRecord,
    utc_now,
)
from app.domain.generation import AIProviderAdapter, GenerationRequest, GenerationStatus

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="sprite-generation")


def enqueue_generation(job_id: str) -> None:
    _executor.submit(_run_generation_job, job_id)


def _run_generation_job(job_id: str) -> None:
    from app.db.session import get_engine

    factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    with factory() as session:
        try:
            GenerationService(session).run(job_id)
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
        record = GenerationJobRecord(
            project_id=request.project_id,
            asset_id=request.asset_id,
            provider=self.provider.provider_id,
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
            provider_result = self.provider.generate(request)
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
                metadata_json=json.dumps(provider_result.metadata, sort_keys=True),
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

    def cancel(self, job_id: str) -> GenerationJobRecord:
        job = self.get(job_id)
        if job.status not in {GenerationStatus.SUCCEEDED.value, GenerationStatus.FAILED.value}:
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
