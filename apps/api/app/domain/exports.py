from dataclasses import dataclass


@dataclass(frozen=True)
class SheetLayout:
    width: int
    height: int
    rects: tuple[tuple[int, int, int, int], ...]


def grid_layout(
    frame_count: int, frame_width: int, frame_height: int,
    columns: int, spacing: int, padding: int,
) -> SheetLayout:
    if frame_count < 1 or frame_width < 1 or frame_height < 1:
        raise ValueError("An export needs at least one nonempty frame.")
    if columns < 1 or spacing < 0 or padding < 0:
        raise ValueError("Invalid spritesheet layout settings.")
    used_columns = min(columns, frame_count)
    rows = (frame_count + used_columns - 1) // used_columns
    width = 2 * padding + used_columns * frame_width + (used_columns - 1) * spacing
    height = 2 * padding + rows * frame_height + (rows - 1) * spacing
    rects = tuple(
        (
            padding + (index % used_columns) * (frame_width + spacing),
            padding + (index // used_columns) * (frame_height + spacing),
            frame_width,
            frame_height,
        )
        for index in range(frame_count)
    )
    return SheetLayout(width, height, rects)
