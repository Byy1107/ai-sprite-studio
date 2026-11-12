from unittest.mock import patch

import httpx
import pytest

from app.services.capabilities import discover_capabilities


def test_fake_discovery_never_connects() -> None:
    with patch("app.services.capabilities.httpx.get") as get:
        result = discover_capabilities("fake", "http://localhost:8188")
    get.assert_not_called()
    assert result["status"] == "ready"
    assert result["detected_nodes"] == []


@pytest.mark.parametrize("payload", [{}, {"LoraLoader": {}, "Unknown": {}}, [], {"bad": None}])
def test_discovery_does_not_enable_unintegrated_workflows(payload: object) -> None:
    response = httpx.Response(200, json=payload, request=httpx.Request("GET", "http://localhost"))
    with patch("app.services.capabilities.httpx.get", return_value=response):
        result = discover_capabilities("comfyui", "http://localhost:8188/")
    assert result["enabled_features"] == {
        "reference": False, "lora": False, "controlnet": False, "inpaint": False,
    }
    if payload == {"LoraLoader": {}, "Unknown": {}}:
        assert result["detected_nodes"] == ["LoraLoader"]
    if payload in ([], {"bad": None}):
        assert result["status"] == "unavailable"


def test_disconnected_server_is_nonfatal() -> None:
    with patch("app.services.capabilities.httpx.get", side_effect=httpx.ConnectError("offline")):
        result = discover_capabilities("comfyui", "http://localhost:8188")
    assert result["status"] == "unavailable"


def test_lora_is_selectable_only_with_loader_inputs_and_models() -> None:
    catalogue = {"LoraLoader": {"input": {"required": {
        "model": ["MODEL"], "clip": ["CLIP"],
        "strength_model": ["FLOAT"], "strength_clip": ["FLOAT"],
        "lora_name": [["pixel.safetensors", "", None, "pixel.safetensors"]],
    }}}}
    response = httpx.Response(
        200, json=catalogue, request=httpx.Request("GET", "http://localhost/object_info")
    )
    with patch("app.services.capabilities.httpx.get", return_value=response):
        result = discover_capabilities("comfyui", "http://localhost:8188")
    assert result["lora_models"] == ["pixel.safetensors"]
    assert result["enabled_features"] == {
        "reference": False, "lora": True, "controlnet": False, "inpaint": False,
    }
