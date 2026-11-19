import hashlib
import os
from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from app.domain.assets import ImageMetadata, InvalidAssetError
from app.services.project_storage import resolve_project_path

MAX_IMPORT_BYTES = 16 * 1024 * 1024
MAX_IMAGE_DIMENSION = 4096


class AssetStorage:
    def inspect_png(self, content: bytes) -> ImageMetadata:
        if not content or len(content) > MAX_IMPORT_BYTES:
            raise InvalidAssetError("PNG must be between 1 byte and 16 MB.")
        try:
            with Image.open(BytesIO(content)) as image:
                image.verify()
            with Image.open(BytesIO(content)) as image:
                if image.format != "PNG":
                    raise InvalidAssetError("Only PNG files are supported.")
                if max(image.size) > MAX_IMAGE_DIMENSION:
                    raise InvalidAssetError("PNG dimensions cannot exceed 4096 pixels.")
                width, height = image.size
                mode = image.mode
        except (UnidentifiedImageError, OSError) as error:
            raise InvalidAssetError("The uploaded file is not a valid PNG.") from error
        return ImageMetadata(
            width=width,
            height=height,
            color_mode=mode,
            checksum=hashlib.sha256(content).hexdigest(),
        )

    def write_initial_version(
        self, project_root: Path, asset_id: str, version_id: str, content: bytes
    ) -> tuple[Path, Path]:
        versions = resolve_project_path(project_root, Path("assets") / asset_id / "versions")
        thumbnails = resolve_project_path(project_root, Path("assets") / asset_id / "thumbnails")
        versions.mkdir(parents=True, exist_ok=False)
        thumbnails.mkdir(parents=True, exist_ok=True)
        version_path = versions / f"{version_id}.png"
        self._atomic_write(version_path, content)
        thumbnail_path = thumbnails / "preview.png"
        self._write_thumbnail(thumbnail_path, content)
        return version_path, thumbnail_path

    def write_restored_version(
        self, project_root: Path, asset_id: str, version_id: str, source_path: Path
    ) -> Path:
        target = resolve_project_path(
            project_root, Path("assets") / asset_id / "versions" / f"{version_id}.png"
        )
        self._atomic_write(target, source_path.read_bytes())
        return target

    def write_version(
        self, project_root: Path, asset_id: str, version_id: str, content: bytes
    ) -> tuple[Path, Path]:
        version_path = resolve_project_path(
            project_root, Path("assets") / asset_id / "versions" / f"{version_id}.png"
        )
        thumbnail_path = resolve_project_path(
            project_root, Path("assets") / asset_id / "thumbnails" / "preview.png"
        )
        self._atomic_write(version_path, content)
        self._write_thumbnail(thumbnail_path, content)
        return version_path, thumbnail_path

    @staticmethod
    def _atomic_write(target: Path, content: bytes) -> None:
        temporary = target.with_suffix(".png.tmp")
        temporary.write_bytes(content)
        os.replace(temporary, target)

    @staticmethod
    def _write_thumbnail(target: Path, content: bytes) -> None:
        temporary = target.with_suffix(".png.tmp")
        with Image.open(BytesIO(content)) as image:
            image.thumbnail((192, 192), Image.Resampling.NEAREST)
            image.save(temporary, format="PNG")
        os.replace(temporary, target)
