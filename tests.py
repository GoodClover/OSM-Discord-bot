print("Running tests")
import main


def test_1():
    assert main.bits_to_frag((1, 0.0, 0.0)) == "#map=1/0.0/0.0"


def test_2():
    assert main.frag_to_bits("#map=1/0/0") == (1, 0.0, 0.0)
    assert main.frag_to_bits("#map=1/0.0/0.0") == (1, 0.0, 0.0)
    assert main.frag_to_bits("#map=1/90.0/0.0") == (1, 90.0, 0.0)
    assert main.frag_to_bits("#map=10/360.0/180.0") == (10, 360.0, 180.0)


def test_3():
    for i in range(1, 17):
        assert main.deg2tile(0.0, 0.0, i) == (2 ** (i - 1), 2 ** (i - 1))
        assert main.deg2tile(89.99, -179.9999, i) == (0, 0)


def test_4():
    assert main.get_render_queue_bounds([[(0.10, 0.0)], [(0.6, 0.5)]]) == (0.1, 0.6, 0.0, 0.5)
    assert main.get_render_queue_bounds([[(0.0, 0.0)], [(0.0, 0.0)]]) == (-1e-05, 1e-05, -1e-05, 1e-05)


def test_5():
    assert main.tiles_x - 2 * main.tile_margin_x > 0 and main.tiles_y - 2 * main.tile_margin_y > 0


def test_6():
    assert main.max_note_zoom <= main.max_zoom


test_1()
test_2()
test_3()
test_4()
test_5()
test_6()
print(f"All {len(set(filter(lambda x:x[0]!='_', dir())))-1} tests passed.")
