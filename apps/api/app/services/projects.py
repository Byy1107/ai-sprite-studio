from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    AssetRecord,
    AssetVersionRecord,
    ExportRecord,
    GenerationJobRecord,
    GenerationResultRecord,
    ProjectRecord,
)
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

    def inspect_integrity(self, project_id: str) -> list[dict[str, str]]:
        project = self.get_project(project_id)
        root = Path(project.root_path).resolve()
        issues: list[dict[str, str]] = []
        if root.parent != self.storage.workspace_dir:
            return [{"kind": "unsafe_project_root", "reference_id": project.id,
                     "path": project.root_path}]
        if not root.is_dir():
            return [{"kind": "missing_project_root", "reference_id": project.id,
                     "path": project.root_path}]

        def check(relative_path: str, kind: str, reference_id: str) -> None:
            candidate = (root / relative_path).resolve()
            if not candidate.is_relative_to(root):
                issues.append({"kind": "unsafe_path", "reference_id": reference_id,
                               "path": relative_path})
            elif not candidate.is_file():
                issues.append({"kind": kind, "reference_id": reference_id,
                               "path": relative_path})

        check("project.json", "missing_project_metadata", project.id)
        assets = self.session.scalars(select(AssetRecord).where(
            AssetRecord.project_id == project_id, AssetRecord.deleted_at.is_(None)
        )).all()
        for asset in assets:
            check(asset.thumbnail_path, "missing_thumbnail", asset.id)
        versions = self.session.scalars(select(AssetVersionRecord).join(AssetRecord).where(
            AssetRecord.project_id == project_id, AssetRecord.deleted_at.is_(None)
        )).all()
        for version in versions:
            check(version.file_path, "missing_asset_version", version.id)
        results = self.session.scalars(select(GenerationResultRecord).join(
            GenerationJobRecord
        ).where(GenerationJobRecord.project_id == project_id)).all()
        for result in results:
            check(result.file_path, "missing_generation_result", result.id)
            if result.thumbnail_path != result.file_path:
                check(result.thumbnail_path, "missing_generation_thumbnail", result.id)
        exports = self.session.scalars(select(ExportRecord).where(
            ExportRecord.project_id == project_id
        )).all()
        for export in exports:
            check(export.output_path, "missing_export", export.id)
            if export.format == "spritesheet":
                check(str(Path(export.output_path).with_suffix(".json")),
                      "missing_export_metadata", export.id)
        return issues

    def delete_project(self, project_id: str) -> None:
        project = self.get_project(project_id)
        path = Path(project.root_path)
        if path.exists():
            self.storage.move_to_trash(path, project.id)
        project.deleted_at = datetime.now(UTC)
        self.session.commit()

    def clear_cache(self, project_id: str) -> int:
        project = self.get_project(project_id)
        root = Path(project.root_path)
        if (root.is_symlink() or not root.is_dir()
                or root.resolve() != self.storage.project_path(project.slug)):
            raise ValueError("Project root is unsafe; cache cleanup stopped.")
        cache = root / "cache"
        if cache.is_symlink():
            raise ValueError("Project cache is unsafe; cleanup stopped.")
        if not cache.exists():
            return 0
        cache_root = cache.resolve()
        if not cache.is_dir() or cache_root.parent != root.resolve():
            raise ValueError("Project cache is unsafe; cleanup stopped.")
        references: list[str] = []
        assets = self.session.scalars(select(AssetRecord).where(
            AssetRecord.project_id == project_id
        )).all()
        asset_ids = {asset.id for asset in assets}
        references.extend(asset.thumbnail_path for asset in assets)
        references.extend(version.file_path for version in self.session.scalars(
            select(AssetVersionRecord).where(AssetVersionRecord.asset_id.in_(asset_ids))
        ))
        for result in self.session.scalars(select(GenerationResultRecord).join(
            GenerationJobRecord
        ).where(GenerationJobRecord.project_id == project_id)):
            references.extend((result.file_path, result.thumbnail_path))
        references.extend(export.output_path for export in self.session.scalars(
            select(ExportRecord).where(ExportRecord.project_id == project_id)
        ))
        if any((root / reference).resolve().is_relative_to(cache_root)
               for reference in references):
            raise ValueError("Cache contains database-referenced files; cleanup stopped.")
        entries = list(cache.rglob("*"))
        if any(entry.is_symlink() or not entry.resolve().is_relative_to(cache_root)
               or not (entry.is_file() or entry.is_dir()) for entry in entries):
            raise ValueError("Cache contains an unsafe entry; cleanup stopped.")
        files = [entry for entry in entries if entry.is_file()]
        for file in files:
            file.unlink()
        for directory in sorted((entry for entry in entries if entry.is_dir()),
                                key=lambda entry: len(entry.parts), reverse=True):
            directory.rmdir()
        return len(files)

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
