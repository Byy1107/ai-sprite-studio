import hashlib
import json
import os
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AssetVersionRecord, ExportRecord
from app.domain.exports import grid_layout
from app.services.animations import AnimationService
from app.services.asset_storage import MAX_IMPORT_BYTES
from app.services.assets import AssetService

MAX_SHEET_PIXELS = 32_000_000
MAX_FRAMES = 256


class ExportNotFoundError(ValueError):
    pass


class ExportService:
    def __init__(self, session: Session, assets: AssetService) -> None:
        self.session = session
        self.assets = assets
        self.animations = AnimationService(session, assets)

    def list_exports(self, project_id: str) -> list[ExportRecord]:
        self.assets.projects.get_project(project_id)
        return list(self.session.scalars(
            select(ExportRecord).where(ExportRecord.project_id == project_id)
            .order_by(ExportRecord.created_at.desc(), ExportRecord.id.desc())
        ))

    def get_export(self, export_id: str) -> ExportRecord:
        record = self.session.get(ExportRecord, export_id)
        if record is None:
            raise ExportNotFoundError("Export was not found.")
        self.assets.projects.get_project(record.project_id)
        return record

    def get_file(self, export_id: str, kind: str) -> Path:
        record = self.get_export(export_id)
        allowed = {"gif"} if record.format == "gif" else (
            {"png"} if record.format == "png" else {"png", "json"}
        )
        if kind not in allowed:
            raise ExportNotFoundError("Export file was not found.")
        project = self.assets.projects.get_project(record.project_id)
        root = Path(project.root_path).resolve()
        path = (root / record.output_path).with_suffix(f".{kind}").resolve()
        if not path.is_relative_to(root / "exports") or not path.is_file():
            raise ExportNotFoundError("Export file was not found.")
        return path

    def create_png(self, asset_id: str, version_id: str | None, scale: int) -> ExportRecord:
        asset = self.assets.get_asset(asset_id)
        selected_id = version_id or asset.active_version_id
        if selected_id is None:
            raise ValueError("Select a published asset version before exporting.")
        version = self.session.get(AssetVersionRecord, selected_id)
        if version is None or version.asset_id != asset_id:
            raise ValueError("Export version must belong to the selected asset.")
        if version.width * scale * version.height * scale > MAX_SHEET_PIXELS:
            raise ValueError("PNG export exceeds the 32-megapixel safety limit.")
        with self._open_version(selected_id) as source:
            image = source.resize(
                (source.width * scale, source.height * scale), Image.Resampling.NEAREST
            )
            content = self._png_bytes(image)
        return self._save(asset.project_id, asset_id, "png", {
            "schema_version": 1, "asset_version_id": selected_id, "scale": scale,
        }, content)

    def create_spritesheet(
        self, asset_id: str, animation_id: str, scale: int,
        columns: int, spacing: int, padding: int,
    ) -> ExportRecord:
        asset = self.assets.get_asset(asset_id)
        animation = self.animations.get_animation(animation_id)
        if animation.asset_id != asset_id:
            raise ValueError("Animation must belong to the selected asset.")
        frames = self.animations.list_frames(animation_id)
        if not frames or len(frames) > MAX_FRAMES:
            raise ValueError("Spritesheet needs between 1 and 256 frames.")
        frame_width = animation.canvas_width * scale
        frame_height = animation.canvas_height * scale
        layout = grid_layout(len(frames), frame_width, frame_height, columns, spacing, padding)
        if (layout.width > 8192 or layout.height > 8192
                or layout.width * layout.height > MAX_SHEET_PIXELS):
            raise ValueError("Spritesheet exceeds the 32-megapixel safety limit.")
        sheet = Image.new("RGBA", (layout.width, layout.height), (0, 0, 0, 0))
        metadata_frames: list[dict[str, object]] = []
        for frame, rect in zip(frames, layout.rects, strict=True):
            with self._open_version(frame.asset_version_id) as source:
                if source.size != (animation.canvas_width, animation.canvas_height):
                    raise ValueError("A pinned frame no longer matches the animation canvas.")
                scaled = source.resize((frame_width, frame_height), Image.Resampling.NEAREST)
                sheet.paste(scaled, rect[:2])
            metadata_frames.append({
                "asset_version_id": frame.asset_version_id,
                "rect": dict(zip(("x", "y", "w", "h"), rect, strict=True)),
                "duration_ms": frame.duration_ms,
                "pivot": {"x": frame.pivot_x, "y": frame.pivot_y},
                "offset": {"x": frame.offset_x, "y": frame.offset_y},
                "events": [frame.event_name] if frame.event_name else [],
            })
        metadata = {
            "meta": {
                "app": "AI Sprite Studio", "schema_version": 1, "image": "sprite.png",
                "size": {"w": layout.width, "h": layout.height}, "scale": scale,
                "spacing": spacing, "padding": padding,
            },
            "animations": {
                f"{animation.name}_{animation.direction}": {
                    "name": animation.name, "direction": animation.direction,
                    "fps": animation.fps, "loop_mode": animation.loop_mode,
                    "frames": metadata_frames,
                }
            },
        }
        return self._save(asset.project_id, asset_id, "spritesheet", {
            "schema_version": 1, "animation_id": animation_id, "scale": scale,
            "columns": columns, "spacing": spacing, "padding": padding,
        }, self._png_bytes(sheet), metadata)

    def create_gif(self, asset_id: str, animation_id: str, scale: int) -> ExportRecord:
        asset = self.assets.get_asset(asset_id)
        animation = self.animations.get_animation(animation_id)
        if animation.asset_id != asset_id:
            raise ValueError("Animation must belong to the selected asset.")
        frames = self.animations.list_frames(animation_id)
        if not frames or len(frames) > MAX_FRAMES:
            raise ValueError("GIF needs between 1 and 256 frames.")
        width = animation.canvas_width * scale
        height = animation.canvas_height * scale
        playback_count = len(frames) * 2 - 2 if animation.loop_mode == "ping_pong" else len(frames)
        if width * height * playback_count > MAX_SHEET_PIXELS:
            raise ValueError("GIF exceeds the 32-megapixel playback safety limit.")
        images: list[Image.Image] = []
        durations: list[int] = []
        for frame in frames:
            with self._open_version(frame.asset_version_id) as source:
                if source.size != (animation.canvas_width, animation.canvas_height):
                    raise ValueError("A pinned frame no longer matches the animation canvas.")
                composed = Image.new("RGBA", source.size, (0, 0, 0, 0))
                composed.alpha_composite(source, (frame.offset_x, frame.offset_y))
                images.append(composed.resize((width, height), Image.Resampling.NEAREST))
            durations.append(max(20, round(frame.duration_ms / 10) * 10))
        if animation.loop_mode == "ping_pong":
            images.extend(images[-2:0:-1])
            durations.extend(durations[-2:0:-1])
        output = BytesIO()
        if animation.loop_mode == "once":
            images[0].save(
                output, format="GIF", save_all=True, append_images=images[1:],
                duration=durations, disposal=2, optimize=False,
            )
        else:
            images[0].save(
                output, format="GIF", save_all=True, append_images=images[1:],
                duration=durations, disposal=2, optimize=False, loop=0,
            )
        return self._save(asset.project_id, asset_id, "gif", {
            "schema_version": 1, "animation_id": animation_id, "scale": scale,
            "loop_mode": animation.loop_mode,
        }, output.getvalue(), extension="gif")

    def _open_version(self, version_id: str) -> Image.Image:
        path = self.assets.get_version_path(version_id)
        version = self.session.get(AssetVersionRecord, version_id)
        if version is None:
            raise ValueError("A pinned source version is missing.")
        if path.stat().st_size > MAX_IMPORT_BYTES:
            raise ValueError("A pinned source PNG exceeds the 16 MB safety limit.")
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != version.checksum:
            raise ValueError("A pinned source PNG changed after publication.")
        try:
            with Image.open(BytesIO(content)) as image:
                image.load()
                return image.convert("RGBA")
        except (OSError, UnidentifiedImageError) as error:
            raise ValueError("A pinned source PNG is unreadable.") from error

    @staticmethod
    def _png_bytes(image: Image.Image) -> bytes:
        output = BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()

    def _save(
        self, project_id: str, asset_id: str, format_name: str,
        config: dict[str, object], content: bytes,
        metadata: dict[str, object] | None = None,
        extension: str = "png",
    ) -> ExportRecord:
        project = self.assets.projects.get_project(project_id)
        export_id = str(uuid4())
        output_dir = Path(project.root_path) / "exports" / export_id
        output_dir.mkdir(parents=True, exist_ok=False)
        output_path = output_dir / f"sprite.{extension}"
        self._write_new(output_path, content)
        if metadata is not None:
            json_content = (json.dumps(metadata, sort_keys=True, indent=2) + "\n").encode("utf-8")
            self._write_new(output_dir / "sprite.json", json_content)
        record = ExportRecord(
            id=export_id, project_id=project_id, asset_id=asset_id,
            format=format_name, preset_id=None,
            config_json=json.dumps(config, sort_keys=True),
            output_path=str(output_path.relative_to(project.root_path)),
            checksum=hashlib.sha256(content).hexdigest(), status="succeeded",
        )
        self.session.add(record)
        self.session.commit()
        return record

    @staticmethod
    def _write_new(path: Path, content: bytes) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        with temporary.open("xb") as output:
            output.write(content)
        os.replace(temporary, path)
