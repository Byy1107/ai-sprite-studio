import hashlib
import json
import zipfile
from dataclasses import dataclass
from io import BytesIO

from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.db.models import AssetVersionRecord
from app.services.asset_storage import MAX_IMPORT_BYTES
from app.services.assets import AssetService

MAX_SAMPLES = 64
MAX_SOURCE_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True)
class LoraSample:
    version_id: str
    caption: str


class LoraDatasetService:
    def __init__(self, session: Session, assets: AssetService) -> None:
        self.session = session
        self.assets = assets

    def build_archive(
        self, project_id: str, samples: list[LoraSample], resolution: int, background: str
    ) -> bytes:
        self.assets.projects.get_project(project_id)
        if not 1 <= len(samples) <= MAX_SAMPLES:
            raise ValueError("Select between 1 and 64 published versions.")
        if resolution not in (256, 512):
            raise ValueError("LoRA dataset resolution must be 256 or 512 pixels.")
        if len(background) != 6 or any(
            character not in "0123456789abcdefABCDEF" for character in background
        ):
            raise ValueError("Background must be a six-digit RGB hex color.")
        seen: set[str] = set()
        rows: list[dict[str, str]] = []
        provenance: list[dict[str, str]] = []
        output = BytesIO()
        source_bytes = 0
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for index, sample in enumerate(samples, start=1):
                caption = sample.caption.strip()
                if not caption or len(caption) > 240:
                    raise ValueError("Each selected version needs a caption of 1–240 characters.")
                if sample.version_id in seen:
                    raise ValueError("Each published version may be selected only once.")
                seen.add(sample.version_id)
                version = self.session.get(AssetVersionRecord, sample.version_id)
                if version is None:
                    raise ValueError("A selected asset version was not found.")
                asset = self.assets.get_asset(version.asset_id)
                if asset.project_id != project_id:
                    raise ValueError("Every selected version must belong to this project.")
                path = self.assets.get_version_path(version.id)
                size = path.stat().st_size
                source_bytes += size
                if size > MAX_IMPORT_BYTES or source_bytes > MAX_SOURCE_BYTES:
                    raise ValueError("LoRA dataset exceeds the source-file safety limit.")
                content = path.read_bytes()
                source_hash = hashlib.sha256(content).hexdigest()
                if source_hash != version.checksum:
                    raise ValueError("A selected PNG changed after publication.")
                try:
                    with Image.open(BytesIO(content)) as source:
                        source.load()
                        if source.format != "PNG" or source.size != (version.width, version.height):
                            raise ValueError(
                                "A selected PNG no longer matches its published metadata."
                            )
                        image = source.convert("RGBA")
                except (OSError, UnidentifiedImageError) as error:
                    raise ValueError("A selected PNG is unreadable.") from error
                scale = min(resolution / image.width, resolution / image.height)
                width = max(1, round(image.width * scale))
                height = max(1, round(image.height * scale))
                resized = image.resize((width, height), Image.Resampling.NEAREST)
                canvas = Image.new("RGBA", (resolution, resolution), f"#{background}")
                canvas.alpha_composite(
                    resized, ((resolution - width) // 2, (resolution - height) // 2)
                )
                image_output = BytesIO()
                canvas.convert("RGB").save(image_output, format="PNG")
                filename = f"{index:04d}.png"
                prepared = image_output.getvalue()
                archive.writestr(filename, prepared)
                rows.append({"file_name": filename, "text": caption})
                provenance.append({
                    "file_name": filename, "asset_id": asset.id, "version_id": version.id,
                    "source_sha256": source_hash,
                    "prepared_sha256": hashlib.sha256(prepared).hexdigest(),
                })
            archive.writestr(
                "metadata.jsonl",
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
            )
            archive.writestr(
                "manifest.json",
                json.dumps({
                    "format_version": 1, "project_id": project_id,
                    "resolution": resolution, "background": f"#{background.upper()}",
                    "samples": provenance,
                }, indent=2) + "\n",
            )
        return output.getvalue()
