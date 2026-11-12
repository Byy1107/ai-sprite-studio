from hashlib import sha256
from io import BytesIO
from random import Random

from PIL import Image, ImageDraw

from app.domain.generation import GenerationRequest, ProviderResult


class FakeAIProvider:
    provider_id = "fake"

    def cancel(self) -> None:
        return None

    def generate(self, request: GenerationRequest) -> ProviderResult:
        digest = sha256(
            f"{request.prompt}:{request.asset_type}:{request.style}:{request.seed}".encode()
        ).digest()
        random = Random(int.from_bytes(digest[:8], "big"))
        image = Image.new("RGBA", (request.width, request.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        palette = [
            (11, 13, 23, 255),
            (37, 43, 71, 255),
            (178, 138, 69, 255),
            (103, 183, 178, 255),
        ]
        block = max(1, min(request.width, request.height) // 8)
        for y in range(0, request.height, block):
            for x in range(0, request.width, block):
                if random.random() > 0.42:
                    color = palette[random.randrange(len(palette))]
                    draw.rectangle((x, y, x + block - 1, y + block - 1), fill=color)
        output = BytesIO()
        image.save(output, format="PNG")
        return ProviderResult(
            image_bytes=output.getvalue(),
            seed=request.seed,
            metadata={"provider": self.provider_id, "deterministic": True},
        )
