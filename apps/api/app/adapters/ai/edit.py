from io import BytesIO
from typing import Any

from PIL import Image

from app.domain.generation import GenerationRequest


def mask_image(request: GenerationRequest, width: int, height: int) -> bytes:
    if None in (request.mask_x, request.mask_y, request.mask_width, request.mask_height):
        raise ValueError("Inpainting requires a rectangle selection")
    assert request.mask_x is not None and request.mask_y is not None
    assert request.mask_width is not None and request.mask_height is not None
    left = request.mask_x * width // request.width
    top = request.mask_y * height // request.height
    right = (request.mask_x + request.mask_width) * width // request.width
    bottom = (request.mask_y + request.mask_height) * height // request.height
    image = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    image.paste(
        (0, 0, 0, 0),
        (left, top, right, bottom),
    )
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def add_image_edit(
    workflow: dict[str, Any], request: GenerationRequest, source_path: str,
    width: int, height: int, mask_path: str | None = None,
) -> None:
    workflow["20"] = {"class_type": "LoadImage", "inputs": {"image": source_path}}
    workflow["23"] = {
        "class_type": "ImageScale",
        "inputs": {
            "image": ["20", 0], "upscale_method": "nearest-exact",
            "width": width, "height": height, "crop": "disabled",
        },
    }
    if request.operation == "inpaint":
        if mask_path is None:
            raise ValueError("Inpainting requires a selection mask")
        workflow["22"] = {"class_type": "LoadImage", "inputs": {"image": mask_path}}
        workflow["21"] = {
            "class_type": "VAEEncodeForInpaint",
            "inputs": {
                "pixels": ["23", 0], "vae": ["4", 2],
                "mask": ["22", 1], "grow_mask_by": 0,
            },
        }
        workflow["3"]["inputs"]["denoise"] = 0.85
    else:
        workflow["21"] = {
            "class_type": "VAEEncode",
            "inputs": {"pixels": ["23", 0], "vae": ["4", 2]},
        }
        workflow["3"]["inputs"]["denoise"] = 0.55
    workflow["3"]["inputs"]["latent_image"] = ["21", 0]
