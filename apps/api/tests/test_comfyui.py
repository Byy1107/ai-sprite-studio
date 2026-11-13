from dataclasses import replace
from typing import Any
from unittest.mock import patch

import httpx
import pytest

from app.adapters.ai.comfyui import ComfyUIError, ComfyUIProvider
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


@pytest.mark.parametrize("lora_name", [None, "styles/pixel.safetensors"])
def test_comfyui_generation_maps_workflow_and_retrieves_png(
    monkeypatch: pytest.MonkeyPatch,
    lora_name: str | None,
) -> None:
    submitted: dict[str, Any] = {}

    def post(url: str, **kwargs: Any) -> httpx.Response:
        submitted.update(kwargs["json"]["prompt"])
        return httpx.Response(
            200, json={"prompt_id": "prompt-1"}, request=httpx.Request("POST", url)
        )

    def get(url: str, **_kwargs: Any) -> httpx.Response:
        if url.endswith("/object_info"):
            return httpx.Response(
                200, json={"LoraLoader": {"input": {"required": {
                    "model": ["MODEL"], "clip": ["CLIP"],
                    "lora_name": [["styles/pixel.safetensors"]],
                    "strength_model": ["FLOAT"], "strength_clip": ["FLOAT"],
                }}}}, request=httpx.Request("GET", url),
            )
        if url.endswith("/history/prompt-1"):
            return httpx.Response(
                200,
                json={
                    "prompt-1": {
                        "outputs": {
                            "12": {"images": [{"filename": "not-result.png"}]},
                            "9": {"images": [{"filename": "result.png"}]},
                        }
                    }
                },
                request=httpx.Request("GET", url),
            )
        assert _kwargs["params"]["filename"] == "result.png"
        return httpx.Response(200, content=b"png-bytes", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "post", post)
    monkeypatch.setattr(httpx, "get", get)
    result = ComfyUIProvider("http://127.0.0.1:8188", "pixel.safetensors", 2).generate(
        replace(request(), lora_name=lora_name, lora_weight=0.75)
    )

    assert result.image_bytes == b"png-bytes"
    assert submitted["4"]["inputs"]["ckpt_name"] == "pixel.safetensors"
    assert submitted["5"]["inputs"] == {
        "width": 320, "height": 512, "batch_size": 1,
    }
    assert submitted["11"]["class_type"] == "ImageScale"
    assert submitted["11"]["inputs"]["upscale_method"] == "nearest-exact"
    assert submitted["11"]["inputs"]["width"] == 32
    assert submitted["11"]["inputs"]["height"] == 48
    assert submitted["9"]["inputs"]["images"] == ["11", 0]
    assert result.metadata["inference_width"] == 320
    assert result.metadata["inference_height"] == 512
    assert submitted["7"]["inputs"]["text"] == "blur, anti-aliasing"
    if lora_name:
        assert submitted["10"]["inputs"]["lora_name"] == lora_name
        assert submitted["10"]["inputs"]["strength_model"] == 0.75
        assert submitted["10"]["inputs"]["strength_clip"] == 0.75
        assert submitted["3"]["inputs"]["model"] == ["10", 0]
        assert submitted["6"]["inputs"]["clip"] == ["10", 1]
        assert submitted["7"]["inputs"]["clip"] == ["10", 1]
        assert result.metadata["workflow"] == "sd15-text-to-sprite-lora-v2"
        assert result.metadata["lora_node_wired"] is True
        assert result.metadata["lora_applied"] is None
    else:
        assert "10" not in submitted
        assert result.metadata["lora_node_wired"] is False
        assert result.metadata["lora_applied"] is False
        assert result.metadata["workflow"] == "sd15-text-to-sprite-v2"


@pytest.mark.parametrize(
    ("width", "height", "expected"),
    [(32, 32, (512, 512)), (128, 96, (512, 384)), (8, 256, (64, 512))],
)
def test_inference_dimensions_are_bounded_and_keep_aspect(
    width: int, height: int, expected: tuple[int, int]
) -> None:
    from app.adapters.ai.comfyui import inference_dimensions

    assert inference_dimensions(width, height) == expected


@pytest.mark.parametrize("catalogue", [{}, {"LoraLoader": {}}])
def test_missing_lora_never_submits_generation(catalogue: dict[str, object]) -> None:
    with (
        patch("app.adapters.ai.comfyui.read_node_catalogue", return_value=catalogue),
        patch("app.adapters.ai.comfyui.httpx.post") as post,
        pytest.raises(ComfyUIError, match="unavailable"),
    ):
        ComfyUIProvider("http://localhost:8188", "sd15.safetensors", 2).generate(
            replace(request(), lora_name="missing.safetensors")
        )
    post.assert_not_called()


def test_comfyui_health_reports_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    def offline(*_args: Any, **_kwargs: Any) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "get", offline)
    result = ComfyUIProvider("http://127.0.0.1:8188", "pixel.safetensors", 2).health()
    assert result["status"] == "unavailable"
    assert "not reachable" in str(result["message"])


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (
            {"status": {"status_str": "error", "completed": False,
                        "messages": [["execution_error", {
                            "exception_message": "model architecture mismatch"
                        }]]}, "outputs": {}},
            "model architecture mismatch",
        ),
        ({"status": {"status_str": "success", "completed": True}, "outputs": {}},
         "without a saved image"),
    ],
)
def test_comfyui_reports_failed_or_empty_optional_workflow(
    monkeypatch: pytest.MonkeyPatch, payload: dict[str, Any], message: str
) -> None:
    def post(url: str, **_kwargs: Any) -> httpx.Response:
        return httpx.Response(200, json={"prompt_id": "prompt-1"},
                              request=httpx.Request("POST", url))

    def get(url: str, **_kwargs: Any) -> httpx.Response:
        return httpx.Response(200, json={"prompt-1": payload},
                              request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "post", post)
    monkeypatch.setattr(httpx, "get", get)
    with pytest.raises(ComfyUIError, match=message):
        ComfyUIProvider("http://127.0.0.1:8188", "pixel.safetensors", 2).generate(request())


def test_comfyui_cancel_interrupts_active_job(monkeypatch: pytest.MonkeyPatch) -> None:
    requested_url = ""

    def post(url: str, **_kwargs: Any) -> httpx.Response:
        nonlocal requested_url
        requested_url = url
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", post)
    ComfyUIProvider("http://127.0.0.1:8188", "pixel.safetensors", 2).cancel()
    assert requested_url == "http://127.0.0.1:8188/interrupt"
