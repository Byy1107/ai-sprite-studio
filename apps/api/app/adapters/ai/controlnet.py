from pathlib import PurePosixPath
from typing import Any
from uuid import uuid4

import httpx

from app.domain.generation import GenerationRequest


def upload_input_image(content: bytes, base_url: str) -> str:
    response = httpx.post(
        f"{base_url}/upload/image",
        files={"image": (f"{uuid4()}.png", content, "image/png")},
        data={"type": "input", "subfolder": "ai-sprite-studio", "overwrite": "false"},
        timeout=10,
    )
    response.raise_for_status()
    uploaded = response.json()
    if not isinstance(uploaded, dict):
        raise ValueError("Invalid reference upload response")
    name, subfolder = uploaded.get("name"), uploaded.get("subfolder", "")
    if (
        not isinstance(name, str) or not name or "/" in name
        or not isinstance(subfolder, str) or uploaded.get("type") != "input"
    ):
        raise ValueError("Invalid reference upload location")
    image_path = f"{subfolder}/{name}" if subfolder else name
    if (
        PurePosixPath(image_path).is_absolute()
        or ".." in PurePosixPath(image_path).parts
        or "\\" in image_path or ":" in image_path
    ):
        raise ValueError("Invalid reference upload location")
    return image_path


def add_controlnet(
    workflow: dict[str, Any], request: GenerationRequest, image_path: str
) -> None:
    workflow["11"] = {
        "class_type": "LoadImage", "inputs": {"image": image_path},
    }
    workflow["12"] = {
        "class_type": "ControlNetLoader",
        "inputs": {"control_net_name": request.controlnet_name},
    }
    workflow["13"] = {
        "class_type": "ControlNetApplyAdvanced",
        "inputs": {
            "positive": ["6", 0], "negative": ["7", 0],
            "control_net": ["12", 0], "image": ["11", 0],
            "strength": request.controlnet_strength,
            "start_percent": request.controlnet_start,
            "end_percent": request.controlnet_end,
        },
    }
    workflow["3"]["inputs"]["positive"] = ["13", 0]
    workflow["3"]["inputs"]["negative"] = ["13", 1]
