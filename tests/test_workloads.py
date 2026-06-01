from hpc_final.tiling import TileClass
from hpc_final.workloads import gaussian_stage, sobel_stage


def test_gaussian_mnk_shape():
    tile = TileClass("full", 64, 64, 1)
    stage = gaussian_stage(tile, 5)
    assert (stage.m, stage.n, stage.k) == (4096, 1, 25)
    assert stage.macs == 4096 * 25


def test_sobel_mnk_shape():
    tile = TileClass("full", 64, 64, 1)
    stage = sobel_stage(tile)
    assert (stage.m, stage.n, stage.k) == (4096, 2, 9)
    assert stage.macs == 4096 * 18
