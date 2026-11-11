import re
from dataclasses import dataclass

WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


class InvalidProjectNameError(ValueError):
    pass


def slugify_project_name(name: str) -> str:
    normalized = name.strip()
    if not normalized:
        raise InvalidProjectNameError("Project name cannot be empty.")
    if any(character in normalized for character in '<>:"/\\|?*'):
        raise InvalidProjectNameError("Project name contains characters Windows cannot use.")
    if normalized.endswith((".", " ")):
        raise InvalidProjectNameError("Project name cannot end with a dot or space.")

    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    if not slug or slug.upper() in WINDOWS_RESERVED_NAMES:
        raise InvalidProjectNameError("Project name is reserved by Windows.")
    return slug[:80].rstrip("-")


@dataclass(frozen=True)
class ProjectDraft:
    name: str
    slug: str
    description: str
