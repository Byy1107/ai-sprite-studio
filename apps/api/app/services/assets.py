from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import AssetRecord, AssetVersionRecord
from app.domain.assets import AssetStyle, AssetType
from app.services.asset_storage import AssetStorage
from app.services.projects import ProjectService


class AssetNotFoundError(ValueError):
    pass


class AssetService:
    def __init__(self, session: Session, workspace_dir: Path) -> None:
        self.session = session
        self.projects = ProjectService(session, workspace_dir)
        self.storage = AssetStorage()

    def list_assets(self, project_id: str) -> list[AssetRecord]:
        self.projects.get_project(project_id)
        statement = (
            select(AssetRecord)
            .where(AssetRecord.project_id == project_id, AssetRecord.deleted_at.is_(None))
            .order_by(AssetRecord.updated_at.desc())
        )
        return list(self.session.scalars(statement))

    def get_asset(self, asset_id: str) -> AssetRecord:
        asset = self.session.get(AssetRecord, asset_id)
        if asset is None or asset.deleted_at is not None:
            raise AssetNotFoundError("Asset was not found.")
        return asset

    def import_png(
        self,
        project_id: str,
        name: str,
        asset_type: AssetType,
        style: AssetStyle,
        content: bytes,
    ) -> AssetRecord:
        project = self.projects.get_project(project_id)
        metadata = self.storage.inspect_png(content)
        asset_id = str(uuid4())
        version_id = str(uuid4())
        version_path, thumbnail_path = self.storage.write_initial_version(
            Path(project.root_path), asset_id, version_id, content
        )
        asset = AssetRecord(
            id=asset_id,
            project_id=project_id,
            name=name.strip(),
            asset_type=asset_type.value,
            style=style.value,
            width=metadata.width,
            height=metadata.height,
            color_mode=metadata.color_mode,
            active_version_id=version_id,
            thumbnail_path=str(thumbnail_path.relative_to(project.root_path)),
        )
        version = AssetVersionRecord(
            id=version_id,
            asset_id=asset_id,
            version_number=1,
            file_path=str(version_path.relative_to(project.root_path)),
            checksum=metadata.checksum,
            width=metadata.width,
            height=metadata.height,
            source="import",
            change_summary="Initial PNG import",
        )
        self.session.add_all((asset, version))
        self.session.commit()
        return asset

    def list_versions(self, asset_id: str) -> list[AssetVersionRecord]:
        self.get_asset(asset_id)
        statement = (
            select(AssetVersionRecord)
            .where(AssetVersionRecord.asset_id == asset_id)
            .order_by(AssetVersionRecord.version_number.desc())
        )
        return list(self.session.scalars(statement))

    def get_version_path(self, version_id: str) -> Path:
        version = self.session.get(AssetVersionRecord, version_id)
        if version is None:
            raise AssetNotFoundError("Asset version was not found.")
        asset = self.get_asset(version.asset_id)
        project = self.projects.get_project(asset.project_id)
        path = Path(project.root_path) / version.file_path
        if not path.is_file():
            raise AssetNotFoundError("Asset version file was not found.")
        return path

    def create_manual_version(
        self, asset_id: str, content: bytes, change_summary: str
    ) -> AssetVersionRecord:
        asset = self.get_asset(asset_id)
        metadata = self.storage.inspect_png(content)
        if (metadata.width, metadata.height) != (asset.width, asset.height):
            raise ValueError("Manual versions must preserve the asset dimensions.")
        project = self.projects.get_project(asset.project_id)
        next_number = self.session.scalar(
            select(func.max(AssetVersionRecord.version_number)).where(
                AssetVersionRecord.asset_id == asset_id
            )
        )
        version_id = str(uuid4())
        version_path, thumbnail_path = self.storage.write_version(
            Path(project.root_path), asset_id, version_id, content
        )
        version = AssetVersionRecord(
            id=version_id,
            asset_id=asset_id,
            version_number=int(next_number or 0) + 1,
            parent_version_id=asset.active_version_id,
            file_path=str(version_path.relative_to(project.root_path)),
            checksum=metadata.checksum,
            width=metadata.width,
            height=metadata.height,
            source="manual",
            change_summary=change_summary.strip() or "Manual pixel edit",
        )
        self.session.add(version)
        asset.active_version_id = version.id
        asset.color_mode = metadata.color_mode
        asset.thumbnail_path = str(thumbnail_path.relative_to(project.root_path))
        self.session.commit()
        return version

    def restore_version(self, asset_id: str, version_id: str) -> AssetVersionRecord:
        asset = self.get_asset(asset_id)
        source = self.session.get(AssetVersionRecord, version_id)
        if source is None or source.asset_id != asset_id:
            raise AssetNotFoundError("Asset version was not found.")
        project = self.projects.get_project(asset.project_id)
        next_number = self.session.scalar(
            select(func.max(AssetVersionRecord.version_number)).where(
                AssetVersionRecord.asset_id == asset_id
            )
        )
        restored_id = str(uuid4())
        source_path = Path(project.root_path) / source.file_path
        restored_path = self.storage.write_restored_version(
            Path(project.root_path), asset_id, restored_id, source_path
        )
        restored = AssetVersionRecord(
            id=restored_id,
            asset_id=asset_id,
            version_number=int(next_number or 0) + 1,
            parent_version_id=source.id,
            file_path=str(restored_path.relative_to(project.root_path)),
            checksum=source.checksum,
            width=source.width,
            height=source.height,
            source="restore",
            change_summary=f"Restored version {source.version_number}",
        )
        self.session.add(restored)
        asset.active_version_id = restored.id
        self.session.commit()
        return restored
