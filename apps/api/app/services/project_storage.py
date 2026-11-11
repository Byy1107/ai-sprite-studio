import json
import os
import shutil
from pathlib import Path
from typing import Any


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
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, target)

    def move_to_trash(self, path: Path, project_id: str) -> Path:
        trash_root = self.workspace_dir / ".trash"
        trash_root.mkdir(parents=True, exist_ok=True)
        destination = trash_root / project_id
        if destination.exists():
            shutil.rmtree(destination)
        return Path(shutil.move(str(path), str(destination)))
