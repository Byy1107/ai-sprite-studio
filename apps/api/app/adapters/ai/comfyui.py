import json
import time
from copy import deepcopy
from pathlib import Path

import httpx

from app.adapters.ai.catalogue import controlnet_models, lora_models, read_node_catalogue
from app.adapters.ai.controlnet import add_controlnet
from app.domain.generation import GenerationRequest, ProviderResult


class ComfyUIError(RuntimeError):
    pass


class ComfyUIProvider:
    provider_id = "comfyui"

    def __init__(self, base_url: str, checkpoint: str, timeout_seconds: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.checkpoint = checkpoint
        self.timeout_seconds = timeout_seconds
        template_path = Path(__file__).parents[2] / "workflows" / "sd15-text-to-sprite-v1.json"
        self.template = json.loads(template_path.read_text(encoding="utf-8"))

    def health(self) -> dict[str, object]:
        try:
            response = httpx.get(f"{self.base_url}/system_stats", timeout=3)
            response.raise_for_status()
            return {"status": "ready", "provider": self.provider_id, "details": response.json()}
        except httpx.HTTPError as error:
            return {
                "status": "unavailable",
                "provider": self.provider_id,
                "message": f"ComfyUI is not reachable at {self.base_url}: {error}",
            }

    def cancel(self) -> None:
        try:
            response = httpx.post(f"{self.base_url}/interrupt", timeout=3)
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise ComfyUIError(f"ComfyUI could not interrupt the active job: {error}") from error

    def generate(
        self, request: GenerationRequest, *, reference_image: bytes | None = None
    ) -> ProviderResult:
        workflow = deepcopy(self.template)
        workflow["4"]["inputs"]["ckpt_name"] = self.checkpoint
        workflow["6"]["inputs"]["text"] = request.prompt
        workflow["7"]["inputs"]["text"] = request.negative_prompt
        workflow["3"]["inputs"]["seed"] = request.seed
        workflow["5"]["inputs"].update({"width": request.width, "height": request.height})
        try:
            nodes = (
                read_node_catalogue(self.base_url)
                if request.lora_name or request.controlnet_name else {}
            )
            if request.lora_name is not None:
                models = lora_models(nodes)
                if request.lora_name not in models:
                    raise ComfyUIError(
                        "Selected LoRA or its loader is unavailable. "
                        "Refresh models or choose No LoRA."
                    )
                workflow["10"] = {
                    "class_type": "LoraLoader",
                    "inputs": {
                        "model": ["4", 0],
                        "clip": ["4", 1],
                        "lora_name": request.lora_name,
                        "strength_model": request.lora_weight,
                        "strength_clip": request.lora_weight,
                    },
                }
                workflow["3"]["inputs"]["model"] = ["10", 0]
                workflow["6"]["inputs"]["clip"] = ["10", 1]
                workflow["7"]["inputs"]["clip"] = ["10", 1]
            if request.controlnet_name is not None:
                if request.controlnet_name not in controlnet_models(nodes):
                    raise ComfyUIError(
                        "Selected ControlNet model or required nodes are unavailable. "
                        "Refresh models or choose No ControlNet."
                    )
                if not reference_image:
                    raise ComfyUIError("ControlNet requires a pinned reference image")
                add_controlnet(workflow, request, reference_image, self.base_url)
            submitted = httpx.post(
                f"{self.base_url}/prompt", json={"prompt": workflow}, timeout=10
            )
            submitted.raise_for_status()
            prompt_id = submitted.json()["prompt_id"]
            deadline = time.monotonic() + self.timeout_seconds
            while time.monotonic() < deadline:
                history = httpx.get(f"{self.base_url}/history/{prompt_id}", timeout=10)
                history.raise_for_status()
                payload = history.json().get(prompt_id)
                if payload:
                    images = next(iter(payload["outputs"].values()))["images"]
                    image = images[0]
                    result = httpx.get(f"{self.base_url}/view", params=image, timeout=30)
                    result.raise_for_status()
                    return ProviderResult(
                        image_bytes=result.content,
                        seed=request.seed,
                        metadata={
                            "provider": self.provider_id,
                            "prompt_id": prompt_id,
                            "checkpoint": self.checkpoint,
                            "workflow": (
                                "sd15-text-to-sprite"
                                + ("-lora" if request.lora_name else "")
                                + ("-controlnet" if request.controlnet_name else "") + "-v1"
                            ),
                            "lora_name": request.lora_name,
                            "lora_weight": request.lora_weight if request.lora_name else None,
                            "lora_applied": request.lora_name is not None,
                            "controlnet_applied": request.controlnet_name is not None,
                            "controlnet_name": request.controlnet_name,
                            "controlnet_strength": request.controlnet_strength,
                            "controlnet_start": request.controlnet_start,
                            "controlnet_end": request.controlnet_end,
                            "reference_version_id": request.reference_version_id,
                            "preset_id": request.preset_id,
                        },
                    )
                time.sleep(0.25)
        except (httpx.HTTPError, KeyError, ValueError) as error:
            raise ComfyUIError(f"ComfyUI generation failed: {error}") from error
        raise ComfyUIError(
            "ComfyUI job timed out. Lower the resolution or verify the checkpoint and workflow."
        )
