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


@dataclass(frozen=True)
class ProviderResult:
    image_bytes: bytes
    seed: int
    metadata: dict[str, object]


class AIProviderAdapter(Protocol):
    provider_id: str

    def generate(self, request: GenerationRequest) -> ProviderResult: ...

    def cancel(self) -> None: ...
