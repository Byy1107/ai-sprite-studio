import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any


def resolve_project_path(root: Path, relative_path: str | Path) -> Path:
    relative = Path(relative_path)
    if (not str(relative_path) or relative.is_absolute() or ":" in str(relative_path)
            or "\x00" in str(relative_path) or ".." in relative.parts):
        raise ValueError("Project file path is unsafe.")
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink() or getattr(current, "is_junction", lambda: False)():
            raise ValueError("Project file path is unsafe.")
    candidate = (root / relative).resolve()
    if candidate == root.resolve() or not candidate.is_relative_to(root.resolve()):
        raise ValueError("Project file path is unsafe.")
    return candidate


class ProjectStorage:
    def __init__(self, workspace_dir: Path) -> None:
        self.workspace_dir = workspace_dir.resolve()

    def project_path(self, slug: str) -> Path:
        candidate = (self.workspace_dir / slug).resolve()
        if candidate.parent != self.workspace_dir:
            raise ValueError("Project path must stay inside the workspace.")
        return candidate

    def create(self, slug: str, metadata: dict[str, Any]) -> Path:
        path = self.project_path(slug)
        path.mkdir(parents=True, exist_ok=False)
        for directory in ("assets", "animations", "exports", "cache", "trash"):
            (path / directory).mkdir()
        self.write_metadata(path, metadata)
        return path

    def write_metadata(self, path: Path, metadata: dict[str, Any]) -> None:
        target = path / "project.json"
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path, prefix=".project-", suffix=".tmp",
            delete=False,
        ) as output:
            temporary = Path(output.name)
            output.write(json.dumps(metadata, indent=2) + "\n")
        try:
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)

    def move_to_trash(self, path: Path, project_id: str) -> Path:
        trash_root = self.workspace_dir / ".trash"
        if trash_root.is_symlink() or (
            trash_root.exists() and trash_root.resolve().parent != self.workspace_dir
        ):
            raise ValueError("Workspace trash is unsafe; deletion stopped.")
        if not project_id or Path(project_id).name != project_id or project_id in {".", ".."}:
            raise ValueError("Project trash path is unsafe; deletion stopped.")
        trash_root.mkdir(parents=True, exist_ok=True)
        destination = trash_root / project_id
        if destination.exists():
            raise FileExistsError("A trash copy already exists for this project.")
        return Path(shutil.move(str(path), str(destination)))
