from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class GenerationStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


@dataclass(frozen=True)
class GenerationRequest:
    project_id: str
    asset_id: str | None
    prompt: str
    asset_type: str
    style: str
    width: int
    height: int
    seed: int
    preset_id: str | None = None
    negative_prompt: str = "blur, anti-aliasing"
    reference_asset_id: str | None = None
    reference_version_id: str | None = None
    reference_weight: float = 1.0
    lora_name: str | None = None
    lora_weight: float = 1.0
    controlnet_name: str | None = None
    controlnet_strength: float = 1.0
    controlnet_start: float = 0.0
    controlnet_end: float = 1.0


class UnsupportedGenerationOption(ValueError):
    pass


@dataclass(frozen=True)
class ProviderResult:
    image_bytes: bytes
    seed: int
    metadata: dict[str, object]


class AIProviderAdapter(Protocol):
    provider_id: str

    def generate(
        self, request: GenerationRequest, *, reference_image: bytes | None = None
    ) -> ProviderResult: ...

    def cancel(self) -> None: ...
