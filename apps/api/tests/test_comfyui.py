from typing import Any

import httpx
import pytest

from app.adapters.ai.comfyui import ComfyUIProvider
from app.domain.generation import GenerationRequest


def request() -> GenerationRequest:
    return GenerationRequest(
        project_id="project",
        asset_id=None,
        prompt="sky guardian pixel sprite",
        asset_type="character",
        style="eight_bit",
        width=32,
        height=48,
        seed=7,
    )


def test_comfyui_generation_maps_workflow_and_retrieves_png(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submitted: dict[str, Any] = {}

    def post(url: str, **kwargs: Any) -> httpx.Response:
        submitted.update(kwargs["json"]["prompt"])
        return httpx.Response(
            200, json={"prompt_id": "prompt-1"}, request=httpx.Request("POST", url)
        )

    def get(url: str, **_kwargs: Any) -> httpx.Response:
        if url.endswith("/history/prompt-1"):
            return httpx.Response(
                200,
                json={
                    "prompt-1": {
                        "outputs": {"9": {"images": [{"filename": "result.png"}]}}
                    }
                },
                request=httpx.Request("GET", url),
            )
        return httpx.Response(200, content=b"png-bytes", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "post", post)
    monkeypatch.setattr(httpx, "get", get)
    result = ComfyUIProvider("http://127.0.0.1:8188", "pixel.safetensors", 2).generate(
        request()
    )

    assert result.image_bytes == b"png-bytes"
    assert submitted["4"]["inputs"]["ckpt_name"] == "pixel.safetensors"
    assert submitted["5"]["inputs"]["height"] == 48
    assert result.metadata["workflow"] == "sd15-text-to-sprite-v1"


def test_comfyui_health_reports_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    def offline(*_args: Any, **_kwargs: Any) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "get", offline)
    result = ComfyUIProvider("http://127.0.0.1:8188", "pixel.safetensors", 2).health()
    assert result["status"] == "unavailable"
    assert "not reachable" in str(result["message"])


def test_comfyui_cancel_interrupts_active_job(monkeypatch: pytest.MonkeyPatch) -> None:
    requested_url = ""

    def post(url: str, **_kwargs: Any) -> httpx.Response:
        nonlocal requested_url
        requested_url = url
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", post)
    ComfyUIProvider("http://127.0.0.1:8188", "pixel.safetensors", 2).cancel()
    assert requested_url == "http://127.0.0.1:8188/interrupt"
