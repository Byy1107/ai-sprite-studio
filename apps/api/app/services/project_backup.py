import hashlib
import json
import os
import shutil
import stat
from datetime import datetime
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import cast
from uuid import uuid4
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

from sqlalchemy import DateTime, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import (
    AnimationFrameRecord,
    AnimationRecord,
    AssetRecord,
    AssetVersionRecord,
    ExportRecord,
    GenerationJobRecord,
    GenerationResultRecord,
    ProjectRecord,
)
from app.domain.projects import slugify_project_name
from app.services.projects import ProjectService

MAX_BACKUP_BYTES = 128 * 1024 * 1024
MAX_BACKUP_FILES = 5000
TABLES = (
    ProjectRecord, AssetRecord, GenerationJobRecord, AssetVersionRecord,
    GenerationResultRecord, AnimationRecord, AnimationFrameRecord, ExportRecord,
)


def safe_relative_path(value: str) -> Path:
    path = PurePosixPath(value)
    if (not value or "\\" in value or ":" in value or "\x00" in value
            or path.is_absolute() or path.as_posix() != value
            or any(part in {".", ".."} or part.rstrip(" .") != part
                   or part.split(".")[0].upper() in {
                       "CON", "PRN", "AUX", "NUL", *(f"COM{number}" for number in range(1, 10)),
                       *(f"LPT{number}" for number in range(1, 10)),
                   } for part in path.parts)):
        raise ValueError("Backup contains an unsafe file path.")
    return Path(*path.parts)


def record_path(value: object) -> str:
    normalized = Path(str(value)).as_posix()
    safe_relative_path(normalized)
    return normalized


def serialize_row(record: object) -> dict[str, object]:
    values: dict[str, object] = {}
    for column in cast(Base, record).__table__.columns:
        value = getattr(record, column.name)
        values[column.name] = value.isoformat() if isinstance(value, datetime) else value
    return values


def required_files(rows: dict[str, list[dict[str, object]]]) -> set[str]:
    required = {"project.json"}
    required.update(
        record_path(row["thumbnail_path"]) for row in rows[AssetRecord.__tablename__]
    )
    required.update(
        record_path(row["file_path"]) for row in rows[AssetVersionRecord.__tablename__]
    )
    for row in rows[GenerationResultRecord.__tablename__]:
        required.update((record_path(row["file_path"]), record_path(row["thumbnail_path"])))
    for row in rows[ExportRecord.__tablename__]:
        output = record_path(row["output_path"])
        required.add(output)
        if row["format"] == "spritesheet":
            required.add(PurePosixPath(output).with_suffix(".json").as_posix())
    return required


class ProjectBackupService:
    def __init__(self, session: Session, workspace_dir: Path) -> None:
        self.session = session
        self.projects = ProjectService(session, workspace_dir)

    def create_backup(self, project_id: str) -> bytes:
        project = self.projects.get_project(project_id)
        issues = self.projects.inspect_integrity(project_id)
        if issues:
            raise ValueError("Project has missing or unsafe files; repair them before backup.")
        root = Path(project.root_path).resolve()
        assets = self.session.scalars(select(AssetRecord).where(
            AssetRecord.project_id == project_id
        )).all()
        asset_ids = {asset.id for asset in assets}
        jobs = self.session.scalars(select(GenerationJobRecord).where(
            GenerationJobRecord.project_id == project_id
        )).all()
        records: dict[str, list[dict[str, object]]] = {
            ProjectRecord.__tablename__: [serialize_row(project)],
            AssetRecord.__tablename__: [serialize_row(asset) for asset in assets],
            GenerationJobRecord.__tablename__: [serialize_row(job) for job in jobs],
        }
        related = {
            AssetVersionRecord: select(AssetVersionRecord).where(
                AssetVersionRecord.asset_id.in_(asset_ids)
            ),
            GenerationResultRecord: select(GenerationResultRecord).join(
                GenerationJobRecord
            ).where(GenerationJobRecord.project_id == project_id),
            AnimationRecord: select(AnimationRecord).where(AnimationRecord.asset_id.in_(asset_ids)),
            AnimationFrameRecord: select(AnimationFrameRecord).join(AnimationRecord).where(
                AnimationRecord.asset_id.in_(asset_ids)
            ),
            ExportRecord: select(ExportRecord).where(ExportRecord.project_id == project_id),
        }
        for model, query in related.items():
            records[model.__tablename__] = [
                serialize_row(row) for row in self.session.scalars(query)
            ]

        output = BytesIO()
        checksums: dict[str, str] = {}
        total_bytes = 0
        with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
            for path in sorted(root.rglob("*")):
                if path.is_symlink() or not path.resolve().is_relative_to(root):
                    raise ValueError("Project contains a link outside its root; backup stopped.")
                if not path.is_file():
                    continue
                relative = path.relative_to(root)
                if relative.parts[0] in {"cache", "trash"} or path.suffix == ".tmp":
                    continue
                if len(checksums) >= MAX_BACKUP_FILES:
                    raise ValueError("Project exceeds the backup file limit.")
                content = path.read_bytes()
                total_bytes += len(content)
                if total_bytes > MAX_BACKUP_BYTES:
                    raise ValueError("Project exceeds the 128 MB backup limit.")
                name = relative.as_posix()
                safe_relative_path(name)
                checksums[name] = hashlib.sha256(content).hexdigest()
                archive.writestr(f"files/{name}", content)
            if not required_files(records).issubset(checksums):
                raise ValueError("Project is missing a file required for backup.")
            archive.writestr("manifest.json", json.dumps({
                "backup_version": 1, "records": records, "checksums": checksums,
            }, sort_keys=True))
        if output.tell() > MAX_BACKUP_BYTES:
            raise ValueError("Backup archive exceeds the 128 MB limit.")
        return output.getvalue()

    def restore_backup(self, content: bytes) -> ProjectRecord:
        if not content or len(content) > MAX_BACKUP_BYTES:
            raise ValueError("Backup must be between 1 byte and 128 MB.")
        try:
            with ZipFile(BytesIO(content)) as archive:
                return self._restore_archive(archive)
        except (OSError, KeyError, BadZipFile, json.JSONDecodeError) as error:
            raise ValueError("Backup is unreadable or incomplete.") from error

    def _restore_archive(self, archive: ZipFile) -> ProjectRecord:
        entries = archive.infolist()
        if (len(entries) > MAX_BACKUP_FILES + 1
                or len({entry.filename for entry in entries}) != len(entries)):
            raise ValueError("Backup has too many or duplicate entries.")
        if sum(entry.file_size for entry in entries) > MAX_BACKUP_BYTES:
            raise ValueError("Backup expands beyond the 128 MB limit.")
        if any(entry.is_dir() or entry.flag_bits & 1
               or (entry.external_attr >> 16) & 0o170000 == stat.S_IFLNK
               for entry in entries):
            raise ValueError("Backup contains a directory, encrypted file, or link entry.")
        names = {entry.filename for entry in entries}
        if "manifest.json" not in names:
            raise ValueError("Backup manifest is missing.")
        manifest = json.loads(archive.read("manifest.json"))
        if not isinstance(manifest, dict) or manifest.get("backup_version") != 1:
            raise ValueError("Backup format is unsupported.")
        raw_records = manifest.get("records")
        checksums = manifest.get("checksums")
        if not isinstance(raw_records, dict) or not isinstance(checksums, dict):
            raise ValueError("Backup manifest is invalid.")
        if set(raw_records) != {model.__tablename__ for model in TABLES}:
            raise ValueError("Backup record set is incomplete.")
        if names != {"manifest.json"} | {f"files/{name}" for name in checksums}:
            raise ValueError("Backup file list does not match its manifest.")
        for name, checksum in checksums.items():
            if not isinstance(name, str) or not isinstance(checksum, str):
                raise ValueError("Backup checksum list is invalid.")
            safe_relative_path(name)
            if hashlib.sha256(archive.read(f"files/{name}")).hexdigest() != checksum:
                raise ValueError("Backup file checksum does not match.")
        rows: dict[str, list[dict[str, object]]] = {}
        for model in TABLES:
            raw = raw_records[model.__tablename__]
            expected = {column.name for column in model.__table__.columns}
            if not isinstance(raw, list) or len(raw) > MAX_BACKUP_FILES:
                raise ValueError("Backup rows are invalid.")
            if any(not isinstance(row, dict) or set(row) != expected for row in raw):
                raise ValueError("Backup row columns are invalid.")
            rows[model.__tablename__] = raw
        projects = rows[ProjectRecord.__tablename__]
        if len(projects) != 1:
            raise ValueError("Backup must contain exactly one project.")
        project_row = projects[0]
        project_id = project_row["id"]
        name = project_row["name"]
        slug = project_row["slug"]
        if not all(isinstance(value, str) for value in (project_id, name, slug)):
            raise ValueError("Backup project identity is invalid.")
        if slugify_project_name(cast(str, name)) != slug:
            raise ValueError("Backup project slug is invalid.")
        asset_ids = {row["id"] for row in rows[AssetRecord.__tablename__]}
        job_ids = {row["id"] for row in rows[GenerationJobRecord.__tablename__]}
        animation_ids = {row["id"] for row in rows[AnimationRecord.__tablename__]}
        version_ids = {row["id"] for row in rows[AssetVersionRecord.__tablename__]}
        if any(row["project_id"] != project_id for row in rows[AssetRecord.__tablename__]
               + rows[GenerationJobRecord.__tablename__] + rows[ExportRecord.__tablename__]):
            raise ValueError("Backup contains records from another project.")
        relationships = (
            (AssetVersionRecord, "asset_id", asset_ids),
            (GenerationResultRecord, "job_id", job_ids),
            (AnimationRecord, "asset_id", asset_ids),
            (AnimationFrameRecord, "animation_id", animation_ids),
            (AnimationFrameRecord, "asset_version_id", version_ids),
            (ExportRecord, "asset_id", asset_ids),
        )
        for model, field, allowed in relationships:
            if any(row[field] not in allowed for row in rows[model.__tablename__]):
                raise ValueError("Backup contains a foreign project reference.")
        for row in rows[GenerationJobRecord.__tablename__]:
            if row["asset_id"] is not None and row["asset_id"] not in asset_ids:
                raise ValueError("Backup job references a foreign asset.")
        for row in rows[AssetVersionRecord.__tablename__]:
            if row["generation_id"] is not None and row["generation_id"] not in job_ids:
                raise ValueError("Backup version references a foreign generation job.")
        if not required_files(rows).issubset(checksums):
            raise ValueError("Backup omits a referenced project file.")
        target = self.projects.storage.project_path(slug)
        if target.exists() or self.session.get(ProjectRecord, project_id) is not None:
            raise ValueError("Project already exists; restore requires a new workspace.")
        staging = self.projects.storage.workspace_dir / f".restore-{uuid4()}"
        staging.mkdir(parents=True, exist_ok=False)
        moved = False
        try:
            for name in checksums:
                destination = staging / safe_relative_path(name)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(archive.read(f"files/{name}"))
            for directory in ("assets", "animations", "exports", "cache", "trash"):
                (staging / directory).mkdir(exist_ok=True)
            project_row["root_path"] = str(target)
            restored: ProjectRecord | None = None
            for model in TABLES:
                for row in rows[model.__tablename__]:
                    values = dict(row)
                    for column in model.__table__.columns:
                        if isinstance(column.type, DateTime) and values[column.name] is not None:
                            values[column.name] = datetime.fromisoformat(str(values[column.name]))
                    record = model(**values)
                    self.session.add(record)
                    if model is ProjectRecord:
                        restored = cast(ProjectRecord, record)
                self.session.flush()
            if restored is None:
                raise ValueError("Backup project is missing.")
            os.replace(staging, target)
            moved = True
            self.session.commit()
            return restored
        except Exception:
            self.session.rollback()
            if moved:
                os.replace(target, staging)
            shutil.rmtree(staging)
            raise
