from dataclasses import replace
from io import BytesIO
from typing import Any
from unittest.mock import patch

import httpx
import pytest
from PIL import Image

from app.adapters.ai.comfyui import ComfyUIError, ComfyUIProvider
from app.adapters.ai.edit import mask_image
from app.domain.generation import GenerationRequest
from app.services.capabilities import discover_capabilities


def catalogue() -> dict[str, Any]:
    advanced = {
        name: ["TYPE"] for name in (
            "model", "ipadapter", "image", "weight", "weight_type", "combine_embeds",
            "start_at", "end_at", "embeds_scaling",
        )
    }
    return {
        "LoadImage": {"input": {"required": {"image": [["file.png"]]}}},
        "ImageScale": {"input": {"required": {
            "image": ["IMAGE"], "upscale_method": [["nearest-exact"]],
            "width": ["INT"], "height": ["INT"], "crop": [["disabled"]],
        }}},
        "IPAdapterModelLoader": {"input": {"required": {
            "ipadapter_file": [["sd15-adapter.safetensors"]],
        }}},
        "CLIPVisionLoader": {"input": {"required": {
            "clip_name": [["vision.safetensors"]],
        }}},
        "IPAdapterAdvanced": {"input": {
            "required": advanced, "optional": {"clip_vision": ["CLIP_VISION"]},
        }},
        "VAEEncode": {"input": {"required": {
            "pixels": ["IMAGE"], "vae": ["VAE"],
        }}},
        "VAEEncodeForInpaint": {"input": {"required": {
            "pixels": ["IMAGE"], "vae": ["VAE"], "mask": ["MASK"],
            "grow_mask_by": ["INT"],
        }}},
    }


def request() -> GenerationRequest:
    return GenerationRequest(
        project_id="project", asset_id="asset", prompt="sprite edit", asset_type="character",
        style="eight_bit", width=32, height=32, seed=7,
        reference_asset_id="asset", reference_version_id="version",
    )


def test_capabilities_require_models_and_complete_node_inputs() -> None:
    nodes = catalogue()
    with patch("app.services.capabilities.read_node_catalogue", return_value=nodes):
        capabilities = discover_capabilities("comfyui", "http://localhost:8188")
    assert capabilities["ipadapter_models"] == ["sd15-adapter.safetensors"]
    assert capabilities["clip_vision_models"] == ["vision.safetensors"]
    assert capabilities["enabled_features"]["ipadapter"] is True
    assert capabilities["enabled_features"]["variation"] is True
    assert capabilities["enabled_features"]["inpaint"] is True
    del nodes["CLIPVisionLoader"]
    with patch("app.services.capabilities.read_node_catalogue", return_value=nodes):
        missing = discover_capabilities("comfyui", "http://localhost:8188")
    assert missing["enabled_features"]["ipadapter"] is False
    del nodes["ImageScale"]
    with patch("app.services.capabilities.read_node_catalogue", return_value=nodes):
        missing_scale = discover_capabilities("comfyui", "http://localhost:8188")
    assert missing_scale["enabled_features"]["variation"] is False
    assert missing_scale["enabled_features"]["inpaint"] is False


def test_ipadapter_wires_pinned_reference_and_weight() -> None:
    submitted: dict[str, Any] = {}
    uploaded: list[bytes] = []

    def post(url: str, **kwargs: Any) -> httpx.Response:
        if url.endswith("/upload/image"):
            uploaded.append(kwargs["files"]["image"][1])
            body = {"name": "reference.png", "subfolder": "ai-sprite-studio", "type": "input"}
        else:
            submitted.update(kwargs["json"]["prompt"])
            body = {"prompt_id": "job"}
        return httpx.Response(200, json=body, request=httpx.Request("POST", url))

    def get(url: str, **_kwargs: Any) -> httpx.Response:
        if "/history/" in url:
            body = {"job": {"outputs": {"9": {"images": [{"filename": "result.png"}]}}}}
            return httpx.Response(200, json=body, request=httpx.Request("GET", url))
        return httpx.Response(200, content=b"candidate", request=httpx.Request("GET", url))

    configured = replace(
        request(), ipadapter_model="sd15-adapter.safetensors",
        clip_vision_model="vision.safetensors", reference_weight=0.7,
    )
    with (
        patch("app.adapters.ai.comfyui.read_node_catalogue", return_value=catalogue()),
        patch("httpx.post", side_effect=post), patch("httpx.get", side_effect=get),
    ):
        result = ComfyUIProvider("http://localhost:8188", "sd15.safetensors", 2).generate(
            configured, reference_image=b"pinned-reference"
        )
    assert uploaded == [b"pinned-reference"]
    assert submitted["14"]["inputs"]["ipadapter_file"] == "sd15-adapter.safetensors"
    assert submitted["15"]["inputs"]["clip_name"] == "vision.safetensors"
    assert submitted["16"]["inputs"]["image"] == "ai-sprite-studio/reference.png"
    assert submitted["17"]["inputs"]["weight"] == 0.7
    assert submitted["3"]["inputs"]["model"] == ["17", 0]
    assert result.metadata["ipadapter_applied"] is True


def test_missing_ipadapter_model_does_not_upload_or_submit() -> None:
    with (
        patch("app.adapters.ai.comfyui.read_node_catalogue", return_value=catalogue()),
        patch("httpx.post") as post,
        pytest.raises(ComfyUIError, match="unavailable"),
    ):
        ComfyUIProvider("http://localhost:8188", "sd15.safetensors", 2).generate(
            replace(request(), ipadapter_model="missing", clip_vision_model="vision.safetensors"),
            reference_image=b"png",
        )
    post.assert_not_called()


@pytest.mark.parametrize("operation", ["variation", "inpaint"])
def test_image_edit_graph_uses_pinned_image_and_selection(operation: str) -> None:
    submitted: dict[str, Any] = {}
    uploaded: list[bytes] = []

    def post(url: str, **kwargs: Any) -> httpx.Response:
        if url.endswith("/upload/image"):
            uploaded.append(kwargs["files"]["image"][1])
            body = {
                "name": f"input-{len(uploaded)}.png",
                "subfolder": "ai-sprite-studio", "type": "input",
            }
        else:
            submitted.update(kwargs["json"]["prompt"])
            body = {"prompt_id": "job"}
        return httpx.Response(200, json=body, request=httpx.Request("POST", url))

    def get(url: str, **_kwargs: Any) -> httpx.Response:
        if "/history/" in url:
            body = {"job": {"outputs": {"9": {"images": [{"filename": "result.png"}]}}}}
            return httpx.Response(200, json=body, request=httpx.Request("GET", url))
        return httpx.Response(200, content=b"candidate", request=httpx.Request("GET", url))

    configured = replace(
        request(), operation=operation,
        mask_x=4 if operation == "inpaint" else None,
        mask_y=5 if operation == "inpaint" else None,
        mask_width=6 if operation == "inpaint" else None,
        mask_height=7 if operation == "inpaint" else None,
    )
    with (
        patch("app.adapters.ai.comfyui.read_node_catalogue", return_value=catalogue()),
        patch("httpx.post", side_effect=post), patch("httpx.get", side_effect=get),
    ):
        ComfyUIProvider("http://localhost:8188", "sd15.safetensors", 2).generate(
            configured, reference_image=b"pinned-source"
        )
    assert uploaded[0] == b"pinned-source"
    assert submitted["20"]["inputs"]["image"] == "ai-sprite-studio/input-1.png"
    assert submitted["3"]["inputs"]["latent_image"] == ["21", 0]
    assert submitted["23"]["class_type"] == "ImageScale"
    assert submitted["23"]["inputs"]["image"] == ["20", 0]
    assert submitted["23"]["inputs"]["width"] == 512
    assert submitted["23"]["inputs"]["height"] == 512
    assert submitted["9"]["inputs"]["images"] == ["11", 0]
    assert submitted["11"]["inputs"]["width"] == 32
    assert submitted["5"]["inputs"]["width"] == 512
    assert submitted["21"]["inputs"]["pixels"] == ["23", 0]
    if operation == "inpaint":
        assert submitted["21"]["class_type"] == "VAEEncodeForInpaint"
        assert submitted["21"]["inputs"]["mask"] == ["22", 1]
        assert submitted["21"]["inputs"]["grow_mask_by"] == 0
        with Image.open(BytesIO(uploaded[1])) as mask:
            assert mask.size == (512, 512)
            assert mask.getpixel((64, 80))[3] == 0
            assert mask.getpixel((63, 80))[3] == 255
            assert mask.getpixel((159, 191))[3] == 0
            assert mask.getpixel((160, 191))[3] == 255
    else:
        assert submitted["21"]["class_type"] == "VAEEncode"
        assert len(uploaded) == 1


def test_mask_image_is_exact_rectangle() -> None:
    image = mask_image(replace(
        request(), operation="inpaint", mask_x=0, mask_y=0,
        mask_width=1, mask_height=1,
    ), 128, 128)
    with Image.open(BytesIO(image)) as mask:
        assert mask.size == (128, 128)
        assert mask.getpixel((0, 0))[3] == 0
        assert mask.getpixel((3, 3))[3] == 0
        assert mask.getpixel((4, 0))[3] == 255
