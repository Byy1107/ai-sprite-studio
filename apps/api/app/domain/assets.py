from dataclasses import dataclass
from enum import StrEnum


class AssetType(StrEnum):
    CHARACTER = "character"
    ITEM = "item"
    ENVIRONMENT = "environment"
    TILESET = "tileset"


class AssetStyle(StrEnum):
    MICRO_PIXEL = "micro_pixel"
    EIGHT_BIT = "eight_bit"
    CUSTOM = "custom"


class InvalidAssetError(ValueError):
    pass


@dataclass(frozen=True)
class ImageMetadata:
    width: int
    height: int
    color_mode: str
    checksum: str
