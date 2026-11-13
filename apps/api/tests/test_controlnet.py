from typing import Any
from unittest.mock import patch

import httpx
import pytest

from app.adapters.ai.comfyui import ComfyUIError, ComfyUIProvider
from app.domain.generation import GenerationRequest
from app.services.capabilities import discover_capabilities


def catalogue() -> dict[str, Any]:
    return {
        "LoadImage": {"input": {"required": {"image": [["input.png"]]}}},
        "ControlNetLoader": {"input": {"required": {
            "control_net_name": [["edge.safetensors"]],
        }}},
        "ControlNetApplyAdvanced": {"input": {"required": {
            name: ["TYPE"] for name in (
                "positive", "negative", "control_net", "image", "strength",
                "start_percent", "end_percent",
            )
        }}},
        "LoraLoader": {"input": {"required": {
            "model": ["MODEL"], "clip": ["CLIP"],
            "lora_name": [["style.safetensors"]],
            "strength_model": ["FLOAT"], "strength_clip": ["FLOAT"],
        }}},
    }


def generation_request(lora: bool = False) -> GenerationRequest:
    return GenerationRequest(
        project_id="project", asset_id=None, prompt="edge guided sprite",
        asset_type="character", style="eight_bit", width=32, height=32, seed=1,
        reference_asset_id="reference", reference_version_id="version",
        controlnet_name="edge.safetensors", controlnet_strength=0.65,
        controlnet_start=0.1, controlnet_end=0.8,
        lora_name="style.safetensors" if lora else None,
    )


@pytest.mark.parametrize("lora", [False, True])
def test_controlnet_upload_and_conditioning_preserve_baseline(lora: bool) -> None:
    submitted: dict[str, Any] = {}
    uploads: list[bytes] = []

    def post(url: str, **kwargs: Any) -> httpx.Response:
        if url.endswith("/upload/image"):
            uploads.append(kwargs["files"]["image"][1])
            assert kwargs["data"]["overwrite"] == "false"
            body = {"name": "uploaded.png", "subfolder": "ai-sprite-studio", "type": "input"}
        else:
            submitted.update(kwargs["json"]["prompt"])
            body = {"prompt_id": "job"}
        return httpx.Response(200, json=body, request=httpx.Request("POST", url))

    def get(url: str, **_kwargs: Any) -> httpx.Response:
        if "/history/" in url:
            return httpx.Response(200, json={"job": {"outputs": {
                "9": {"images": [{"filename": "candidate.png"}]},
            }}}, request=httpx.Request("GET", url))
        return httpx.Response(200, content=b"candidate", request=httpx.Request("GET", url))

    provider = ComfyUIProvider("http://localhost:8188", "sd15.safetensors", 2)
    with (
        patch("app.adapters.ai.comfyui.read_node_catalogue", return_value=catalogue()),
        patch("httpx.post", side_effect=post),
        patch("httpx.get", side_effect=get),
    ):
        result = provider.generate(generation_request(lora), reference_image=b"pinned-png")
    assert uploads == [b"pinned-png"]
    assert submitted["11"]["inputs"]["image"] == "ai-sprite-studio/uploaded.png"
    assert submitted["12"]["inputs"]["control_net_name"] == "edge.safetensors"
    assert submitted["13"]["inputs"] == {
        "positive": ["6", 0], "negative": ["7", 0], "control_net": ["12", 0],
        "image": ["11", 0], "strength": 0.65, "start_percent": 0.1, "end_percent": 0.8,
    }
    assert submitted["3"]["inputs"]["positive"] == ["13", 0]
    assert submitted["3"]["inputs"]["negative"] == ["13", 1]
    assert submitted["3"]["inputs"]["model"] == (["10", 0] if lora else ["4", 0])
    assert result.metadata["controlnet_applied"] is True
    assert result.metadata["reference_version_id"] == "version"
    assert "13" not in provider.template
    assert provider.template["3"]["inputs"]["positive"] == ["6", 0]


@pytest.mark.parametrize(
    "missing", ["LoadImage", "ControlNetLoader", "ControlNetApplyAdvanced", "model"]
)
def test_missing_nodes_disable_controlnet_and_prevent_upload(missing: str) -> None:
    nodes = catalogue()
    if missing == "model":
        nodes["ControlNetLoader"]["input"]["required"]["control_net_name"] = [[]]
    else:
        del nodes[missing]
    with patch("app.services.capabilities.read_node_catalogue", return_value=nodes):
        capabilities = discover_capabilities("comfyui", "http://localhost:8188")
    assert capabilities["controlnet_models"] == []
    with (
        patch("app.adapters.ai.comfyui.read_node_catalogue", return_value=nodes),
        patch("httpx.post") as post,
        pytest.raises(ComfyUIError, match="unavailable"),
    ):
        ComfyUIProvider("http://localhost:8188", "sd15.safetensors", 2).generate(
            generation_request(), reference_image=b"png"
        )
    post.assert_not_called()


def test_controlnet_discovery_lists_local_models() -> None:
    with patch("app.services.capabilities.read_node_catalogue", return_value=catalogue()):
        result = discover_capabilities("comfyui", "http://localhost:8188")
    assert result["controlnet_models"] == ["edge.safetensors"]
    assert result["enabled_features"] == {
        "reference": False, "lora": True, "controlnet": True, "inpaint": False,
        "ipadapter": False, "variation": False,
    }


def test_upload_failure_does_not_submit_prompt() -> None:
    with (
        patch("app.adapters.ai.comfyui.read_node_catalogue", return_value=catalogue()),
        patch("httpx.post", side_effect=httpx.ConnectError("offline")) as post,
        pytest.raises(ComfyUIError, match="generation failed"),
    ):
        ComfyUIProvider("http://localhost:8188", "sd15.safetensors", 2).generate(
            generation_request(), reference_image=b"png"
        )
    assert post.call_count == 1
    assert post.call_args.args[0].endswith("/upload/image")


@pytest.mark.parametrize("payload", [
    [], {"name": "../outside.png", "type": "input"},
    {"name": "image.png", "subfolder": "../outside", "type": "input"},
    {"name": "image.png", "subfolder": "folder", "type": "output"},
])
def test_invalid_upload_response_never_submits_prompt(payload: object) -> None:
    response = httpx.Response(
        200, json=payload, request=httpx.Request("POST", "http://localhost/upload/image")
    )
    with (
        patch("app.adapters.ai.comfyui.read_node_catalogue", return_value=catalogue()),
        patch("httpx.post", return_value=response) as post,
        pytest.raises(ComfyUIError, match="Invalid reference upload"),
    ):
        ComfyUIProvider("http://localhost:8188", "sd15.safetensors", 2).generate(
            generation_request(), reference_image=b"png"
        )
    assert post.call_count == 1
    assert post.call_args.args[0].endswith("/upload/image")
