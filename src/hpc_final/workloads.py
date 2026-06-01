from __future__ import annotations

from dataclasses import dataclass

from .tiling import TileClass


@dataclass(frozen=True)
class StageSpec:
    name: str
    op: str
    m: int
    n: int
    k: int
    kernel_size: int
    radius: int
    macs: int
    output_pixels: int
    input_pixels_with_halo: int


def gaussian_stage(tile: TileClass, kernel_size: int) -> StageSpec:
    if kernel_size <= 0 or kernel_size % 2 == 0:
        raise ValueError("Gaussian kernel size must be a positive odd integer")
    m = tile.output_pixels
    k = kernel_size * kernel_size
    radius = kernel_size // 2
    return StageSpec(
        name=f"gaussian_k{kernel_size}",
        op="gaussian",
        m=m,
        n=1,
        k=k,
        kernel_size=kernel_size,
        radius=radius,
        macs=m * k,
        output_pixels=m,
        input_pixels_with_halo=tile.input_pixels_with_halo(radius),
    )


def sobel_stage(tile: TileClass) -> StageSpec:
    m = tile.output_pixels
    radius = 1
    return StageSpec(
        name="sobel_3x3",
        op="sobel",
        m=m,
        n=2,
        k=9,
        kernel_size=3,
        radius=radius,
        macs=m * 18,
        output_pixels=m,
        input_pixels_with_halo=tile.input_pixels_with_halo(radius),
    )


def pipeline_stages(tile: TileClass, gaussian_kernel: int) -> list[StageSpec]:
    return [gaussian_stage(tile, gaussian_kernel), sobel_stage(tile)]


def frame_macs(width: int, height: int, gaussian_kernel: int) -> int:
    pixels = width * height
    return pixels * (gaussian_kernel * gaussian_kernel + 18)
