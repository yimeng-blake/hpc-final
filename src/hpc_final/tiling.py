from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TileClass:
    name: str
    out_width: int
    out_height: int
    count: int

    @property
    def output_pixels(self) -> int:
        return self.out_width * self.out_height

    def input_pixels_with_halo(self, radius: int) -> int:
        if radius < 0:
            raise ValueError("radius must be non-negative")
        return (self.out_width + 2 * radius) * (self.out_height + 2 * radius)


def derive_tile_classes(frame_width: int, frame_height: int, tile_width: int, tile_height: int) -> list[TileClass]:
    """Return unique output tile classes and multiplicities for a frame."""
    if min(frame_width, frame_height, tile_width, tile_height) <= 0:
        raise ValueError("frame and tile dimensions must be positive")

    full_cols, rem_w = divmod(frame_width, tile_width)
    full_rows, rem_h = divmod(frame_height, tile_height)

    classes: list[TileClass] = []
    full_count = full_cols * full_rows
    if full_count:
        classes.append(TileClass("full", tile_width, tile_height, full_count))
    if rem_w and full_rows:
        classes.append(TileClass("right_edge", rem_w, tile_height, full_rows))
    if rem_h and full_cols:
        classes.append(TileClass("bottom_edge", tile_width, rem_h, full_cols))
    if rem_w and rem_h:
        classes.append(TileClass("corner", rem_w, rem_h, 1))

    return classes
