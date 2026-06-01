from hpc_final.tiling import TileClass, derive_tile_classes


def test_exact_fit_tile_counting():
    tiles = derive_tile_classes(128, 64, 64, 64)
    assert tiles == [TileClass("full", 64, 64, 2)]


def test_ragged_tile_counting():
    tiles = derive_tile_classes(130, 70, 64, 64)
    actual = {(tile.name, tile.out_width, tile.out_height, tile.count) for tile in tiles}
    assert actual == {
        ("full", 64, 64, 2),
        ("right_edge", 2, 64, 1),
        ("bottom_edge", 64, 6, 2),
        ("corner", 2, 6, 1),
    }


def test_halo_increases_input_not_output():
    tile = TileClass("full", 64, 64, 1)
    assert tile.output_pixels == 4096
    assert tile.input_pixels_with_halo(2) == 68 * 68
