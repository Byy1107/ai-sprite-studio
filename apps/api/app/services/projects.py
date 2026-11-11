from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import ProjectRecord
from app.domain.projects import ProjectDraft, slugify_project_name
from app.services.project_storage import ProjectStorage


class DuplicateProjectError(ValueError):
    pass


class ProjectNotFoundError(ValueError):
    pass


class ProjectService:
    def __init__(self, session: Session, workspace_dir: Path) -> None:
        self.session = session
        self.storage = ProjectStorage(workspace_dir)

    def list_projects(self) -> list[ProjectRecord]:
        statement = (
            select(ProjectRecord)
            .where(ProjectRecord.deleted_at.is_(None))
            .order_by(ProjectRecord.last_opened_at.desc(), ProjectRecord.updated_at.desc())
        )
        return list(self.session.scalars(statement))

    def get_project(self, project_id: str) -> ProjectRecord:
        project = self.session.get(ProjectRecord, project_id)
        if project is None or project.deleted_at is not None:
            raise ProjectNotFoundError("Project was not found.")
        return project

    def create_project(self, draft: ProjectDraft) -> ProjectRecord:
        slug = slugify_project_name(draft.name)
        project = ProjectRecord(
            name=draft.name.strip(),
            slug=slug,
            description=draft.description.strip(),
            root_path=str(self.storage.project_path(slug)),
        )
        self.session.add(project)
        try:
            self.session.flush()
            self.storage.create(slug, self._metadata(project))
            self.session.commit()
        except (IntegrityError, FileExistsError) as error:
            self.session.rollback()
            message = "A project with this name or slug already exists."
            raise DuplicateProjectError(message) from error
        return project

    def update_project(
        self, project_id: str, name: str | None, description: str | None
    ) -> ProjectRecord:
        project = self.get_project(project_id)
        if name is not None:
            slugify_project_name(name)
            project.name = name.strip()
        if description is not None:
            project.description = description.strip()
        try:
            self.storage.write_metadata(Path(project.root_path), self._metadata(project))
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise DuplicateProjectError("A project with this name already exists.") from error
        return project

    def open_project(self, project_id: str) -> ProjectRecord:
        project = self.get_project(project_id)
        project.last_opened_at = datetime.now(UTC)
        self.session.commit()
        return project

    def delete_project(self, project_id: str) -> None:
        project = self.get_project(project_id)
        path = Path(project.root_path)
        if path.exists():
            self.storage.move_to_trash(path, project.id)
        project.deleted_at = datetime.now(UTC)
        self.session.commit()

    @staticmethod
    def _metadata(project: ProjectRecord) -> dict[str, object]:
        return {
            "schema_version": project.schema_version,
            "id": project.id,
            "name": project.name,
            "slug": project.slug,
            "description": project.description,
            "created_at": project.created_at.isoformat(),
            "updated_at": project.updated_at.isoformat(),
        }
