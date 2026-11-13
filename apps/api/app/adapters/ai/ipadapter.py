from typing import Any

from app.domain.generation import GenerationRequest


def add_ipadapter(
    workflow: dict[str, Any], request: GenerationRequest, image_path: str
) -> None:
    workflow["14"] = {
        "class_type": "IPAdapterModelLoader",
        "inputs": {"ipadapter_file": request.ipadapter_model},
    }
    workflow["15"] = {
        "class_type": "CLIPVisionLoader",
        "inputs": {"clip_name": request.clip_vision_model},
    }
    workflow["16"] = {"class_type": "LoadImage", "inputs": {"image": image_path}}
    workflow["17"] = {
        "class_type": "IPAdapterAdvanced",
        "inputs": {
            "model": workflow["3"]["inputs"]["model"],
            "ipadapter": ["14", 0],
            "clip_vision": ["15", 0],
            "image": ["16", 0],
            "weight": request.reference_weight,
            "weight_type": "linear",
            "combine_embeds": "concat",
            "start_at": 0.0,
            "end_at": 1.0,
            "embeds_scaling": "V only",
        },
    }
    workflow["3"]["inputs"]["model"] = ["17", 0]
