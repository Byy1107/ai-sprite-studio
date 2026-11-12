import httpx

from app.adapters.ai.catalogue import controlnet_models, lora_models, read_node_catalogue


def discover_capabilities(provider: str, base_url: str) -> dict[str, object]:
    features = {name: False for name in ("reference", "lora", "controlnet", "inpaint")}
    result: dict[str, object] = {
        "provider": provider,
        "status": "ready",
        "enabled_features": features,
        "detected_nodes": [],
        "lora_models": [],
        "controlnet_models": [],
        "message": "No local LoRA or ControlNet models available.",
    }
    if provider != "comfyui":
        result["message"] = "Offline mock provider. Optional AI features are not available."
        return result
    try:
        nodes = read_node_catalogue(base_url)
        known_nodes = {
            "LoraLoader", "ControlNetLoader", "ControlNetApplyAdvanced",
            "IPAdapterAdvanced", "IPAdapterModelLoader", "VAEEncodeForInpaint",
            "LoadImage",
        }
        result["detected_nodes"] = sorted(known_nodes.intersection(nodes))
        models = lora_models(nodes)
        result["lora_models"] = models
        features["lora"] = bool(models)
        controls = controlnet_models(nodes)
        result["controlnet_models"] = controls
        features["controlnet"] = bool(controls)
        if models or controls:
            result["message"] = (
                "Local models can be selected. SD1.5 compatibility requires a generation test. "
                "ControlNet uses a prepared reference image; IP-Adapter and inpainting are pending."
            )
    except (httpx.HTTPError, ValueError):
        result["status"] = "unavailable"
        result["message"] = "Cannot read ComfyUI nodes. Optional features remain disabled."
    return result
