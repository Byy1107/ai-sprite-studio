from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class GenerationPreset:
    id: str
    label: str
    asset_type: str
    description: str
    prompt: str
    negative_prompt: str
    style: str
    width: int
    height: int
    version: str = "1.0"


COMMON_NEGATIVE = "blur, anti-aliasing, gradients, text, watermark, cropped, noisy"

GENERATION_PRESETS = (
    GenerationPreset(
        "character-hero",
        "Hero",
        "character",
        "Readable single-character game sprite.",
        "full body game character, centered, neutral pose, transparent background",
        COMMON_NEGATIVE,
        "eight_bit",
        48,
        48,
    ),
    GenerationPreset(
        "character-akar-langit",
        "Akar Langit",
        "character",
        "Optional dark-fantasy guardian palette.",
        "dark fantasy sky-root guardian, weathered bronze, deep indigo, "
        "teal spirit glow, centered full body sprite",
        COMMON_NEGATIVE,
        "eight_bit",
        48,
        48,
    ),
    GenerationPreset(
        "item-inventory",
        "Inventory item",
        "item",
        "Centered collectible with a clear silhouette.",
        "single game inventory item, centered, strong silhouette, transparent background",
        COMMON_NEGATIVE,
        "micro_pixel",
        32,
        32,
    ),
    GenerationPreset(
        "item-relic",
        "Dark relic",
        "item",
        "Ancient dark-fantasy equipment or treasure.",
        "ancient dark fantasy relic, worn metal, subtle magical glow, centered",
        COMMON_NEGATIVE,
        "eight_bit",
        32,
        32,
    ),
    GenerationPreset(
        "environment-prop",
        "Environment prop",
        "environment",
        "Isolated prop for scene composition.",
        "single environment prop, game-ready, consistent perspective, transparent background",
        COMMON_NEGATIVE,
        "eight_bit",
        64,
        64,
    ),
    GenerationPreset(
        "environment-backdrop",
        "Backdrop",
        "environment",
        "Compact atmospheric scene plate.",
        "compact game environment backdrop, layered depth, readable landmarks",
        COMMON_NEGATIVE,
        "eight_bit",
        128,
        96,
    ),
    GenerationPreset(
        "tileset-ground",
        "Ground tiles",
        "tileset",
        "Seam-aware ground tile source.",
        "orthographic ground tileset, repeatable edges, consistent lighting, tile grid",
        COMMON_NEGATIVE,
        "micro_pixel",
        128,
        128,
    ),
    GenerationPreset(
        "tileset-dungeon",
        "Dungeon tiles",
        "tileset",
        "Dark stone walls and floors.",
        "dark fantasy dungeon tileset, stone floor and wall modules, repeatable edges, tile grid",
        COMMON_NEGATIVE,
        "eight_bit",
        128,
        128,
    ),
)


def preset_by_id(preset_id: str) -> GenerationPreset | None:
    return next((preset for preset in GENERATION_PRESETS if preset.id == preset_id), None)


def serialized_presets() -> list[dict[str, object]]:
    return [asdict(preset) for preset in GENERATION_PRESETS]
