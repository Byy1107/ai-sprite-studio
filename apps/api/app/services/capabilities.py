import httpx

from app.adapters.ai.catalogue import (
    controlnet_models,
    edit_nodes_available,
    ipadapter_models,
    lora_models,
    read_node_catalogue,
)


def discover_capabilities(provider: str, base_url: str) -> dict[str, object]:
    features = {name: False for name in (
        "reference", "lora", "controlnet", "ipadapter", "variation", "inpaint"
    )}
    result: dict[str, object] = {
        "provider": provider,
        "status": "ready",
        "enabled_features": features,
        "detected_nodes": [],
        "lora_models": [],
        "controlnet_models": [],
        "ipadapter_models": [],
        "clip_vision_models": [],
        "message": "No local LoRA or ControlNet models available.",
    }
    if provider != "comfyui":
        result["message"] = "Offline mock provider. Optional AI features are not available."
        return result
    try:
        nodes = read_node_catalogue(base_url)
        known_nodes = {
            "LoraLoader", "ControlNetLoader", "ControlNetApplyAdvanced",
            "IPAdapterAdvanced", "IPAdapterModelLoader", "CLIPVisionLoader",
            "VAEEncodeForInpaint", "VAEEncode", "LoadImage",
        }
        result["detected_nodes"] = sorted(known_nodes.intersection(nodes))
        models = lora_models(nodes)
        result["lora_models"] = models
        features["lora"] = bool(models)
        controls = controlnet_models(nodes)
        result["controlnet_models"] = controls
        features["controlnet"] = bool(controls)
        adapter_models, vision_models = ipadapter_models(nodes)
        result["ipadapter_models"] = adapter_models
        result["clip_vision_models"] = vision_models
        features["ipadapter"] = features["reference"] = bool(adapter_models and vision_models)
        features["variation"] = edit_nodes_available(nodes, "variation")
        features["inpaint"] = edit_nodes_available(nodes, "inpaint")
        if any(features.values()):
            result["message"] = (
                "Optional local nodes detected. Model compatibility and output quality "
                "require a generation test. ControlNet uses a prepared control image."
            )
    except (httpx.HTTPError, ValueError):
        result["status"] = "unavailable"
        result["message"] = "Cannot read ComfyUI nodes. Optional features remain disabled."
    return result
