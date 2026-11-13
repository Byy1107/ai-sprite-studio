import json
import time
from copy import deepcopy
from pathlib import Path

import httpx

from app.adapters.ai.catalogue import (
    controlnet_models,
    edit_nodes_available,
    ipadapter_models,
    lora_models,
    read_node_catalogue,
)
from app.adapters.ai.controlnet import add_controlnet, upload_input_image
from app.adapters.ai.edit import add_image_edit, mask_image
from app.adapters.ai.ipadapter import add_ipadapter
from app.domain.generation import GenerationRequest, ProviderResult


class ComfyUIError(RuntimeError):
    pass


def inference_dimensions(width: int, height: int) -> tuple[int, int]:
    longest_side = max(width, height)

    def scale(dimension: int) -> int:
        return max(64, min(512, ((dimension * 512 // longest_side + 32) // 64) * 64))

    return scale(width), scale(height)


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
        inference_width, inference_height = inference_dimensions(request.width, request.height)
        workflow["5"]["inputs"].update(
            {"width": inference_width, "height": inference_height}
        )
        workflow["11"] = {
            "class_type": "ImageScale",
            "inputs": {
                "image": ["8", 0],
                "upscale_method": "nearest-exact",
                "width": request.width,
                "height": request.height,
                "crop": "disabled",
            },
        }
        workflow["9"]["inputs"]["images"] = ["11", 0]
        try:
            nodes = (
                read_node_catalogue(self.base_url)
                if (request.lora_name or request.controlnet_name or request.ipadapter_model
                    or request.operation != "text_to_sprite") else {}
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
            if request.ipadapter_model is not None:
                adapters, vision_models = ipadapter_models(nodes)
                if (request.ipadapter_model not in adapters
                    or request.clip_vision_model not in vision_models):
                    raise ComfyUIError(
                        "Selected IP-Adapter or CLIP vision model is unavailable. "
                        "Refresh models or disable IP-Adapter."
                    )
            if (request.controlnet_name is not None
                and request.controlnet_name not in controlnet_models(nodes)):
                raise ComfyUIError(
                    "Selected ControlNet model or required nodes are unavailable. "
                    "Refresh models or choose No ControlNet."
                )
            if (
                request.operation != "text_to_sprite"
                and not edit_nodes_available(nodes, request.operation)
            ):
                raise ComfyUIError("Required local image edit nodes are unavailable")
            needs_reference = bool(
                request.controlnet_name or request.ipadapter_model
                or request.operation != "text_to_sprite"
            )
            if needs_reference:
                if not reference_image:
                    raise ComfyUIError("Optional AI workflow requires a pinned reference image")
                source_path = upload_input_image(reference_image, self.base_url)
                if request.controlnet_name:
                    add_controlnet(workflow, request, source_path)
                if request.ipadapter_model:
                    add_ipadapter(workflow, request, source_path)
                if request.operation != "text_to_sprite":
                    selected_mask = (
                        upload_input_image(
                            mask_image(request, inference_width, inference_height),
                            self.base_url,
                        )
                        if request.operation == "inpaint" else None
                    )
                    add_image_edit(
                        workflow, request, source_path,
                        inference_width, inference_height, selected_mask,
                    )
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
                    status = payload.get("status", {})
                    if status.get("status_str") in {"error", "interrupted"}:
                        detail = next(
                            (
                                message[1].get("exception_message")
                                for message in status.get("messages", [])
                                if isinstance(message, list)
                                and len(message) > 1
                                and message[0] == "execution_error"
                                and isinstance(message[1], dict)
                            ),
                            None,
                        )
                        raise ComfyUIError(
                            f"ComfyUI job {status['status_str']}: "
                            f"{str(detail)[:300] if detail else 'check the local ComfyUI log'}"
                        )
                    images = payload.get("outputs", {}).get("9", {}).get("images", [])
                    if not images:
                        if status.get("completed") is False:
                            time.sleep(0.25)
                            continue
                        raise ComfyUIError("ComfyUI job finished without a saved image")
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
                                + ("-controlnet" if request.controlnet_name else "")
                                + ("-ipadapter" if request.ipadapter_model else "")
                                + (
                                    f"-{request.operation}"
                                    if request.operation != "text_to_sprite" else ""
                                )
                                + "-v2"
                            ),
                            "inference_width": inference_width,
                            "inference_height": inference_height,
                            "output_width": request.width,
                            "output_height": request.height,
                            "lora_name": request.lora_name,
                            "lora_weight": request.lora_weight if request.lora_name else None,
                            "lora_node_wired": request.lora_name is not None,
                            "lora_applied": None if request.lora_name else False,
                            "controlnet_applied": request.controlnet_name is not None,
                            "controlnet_name": request.controlnet_name,
                            "controlnet_strength": request.controlnet_strength,
                            "controlnet_start": request.controlnet_start,
                            "controlnet_end": request.controlnet_end,
                            "ipadapter_applied": request.ipadapter_model is not None,
                            "ipadapter_model": request.ipadapter_model,
                            "clip_vision_model": request.clip_vision_model,
                            "reference_weight": request.reference_weight,
                            "edit_applied": request.operation != "text_to_sprite",
                            "operation": request.operation,
                            "mask": (
                                [
                                    request.mask_x, request.mask_y,
                                    request.mask_width, request.mask_height,
                                ]
                                if request.operation == "inpaint" else None
                            ),
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
