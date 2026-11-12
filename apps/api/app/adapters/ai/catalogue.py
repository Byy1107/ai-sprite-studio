import httpx


def read_node_catalogue(base_url: str) -> dict[str, object]:
    response = httpx.get(f"{base_url.rstrip('/')}/object_info", timeout=3)
    response.raise_for_status()
    nodes = response.json()
    if not isinstance(nodes, dict) or any(not isinstance(value, dict) for value in nodes.values()):
        raise ValueError("Invalid node catalogue")
    return nodes


def lora_models(nodes: dict[str, object]) -> list[str]:
    loader = nodes.get("LoraLoader")
    if not isinstance(loader, dict):
        return []
    inputs = loader.get("input")
    if not isinstance(inputs, dict):
        return []
    required = inputs.get("required")
    if not isinstance(required, dict) or not {
        "model", "clip", "lora_name", "strength_model", "strength_clip"
    }.issubset(required):
        return []
    names = required["lora_name"]
    if not isinstance(names, list) or not names or not isinstance(names[0], list):
        return []
    return sorted({
        name for name in names[0]
        if isinstance(name, str) and name.strip()
    })


def required_inputs(nodes: dict[str, object], node_name: str) -> dict[str, object]:
    node = nodes.get(node_name)
    if not isinstance(node, dict):
        return {}
    inputs = node.get("input")
    if not isinstance(inputs, dict) or not isinstance(inputs.get("required"), dict):
        return {}
    return dict(inputs["required"])


def controlnet_models(nodes: dict[str, object]) -> list[str]:
    apply_inputs = required_inputs(nodes, "ControlNetApplyAdvanced")
    if not {
        "positive", "negative", "control_net", "image", "strength", "start_percent", "end_percent"
    }.issubset(apply_inputs) or "image" not in required_inputs(nodes, "LoadImage"):
        return []
    names = required_inputs(nodes, "ControlNetLoader").get("control_net_name")
    if not isinstance(names, list) or not names or not isinstance(names[0], list):
        return []
    return sorted({name for name in names[0] if isinstance(name, str) and name.strip()})
