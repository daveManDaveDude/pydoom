import pytest

from game.world import World


@pytest.mark.parametrize(
    "x,y",
    [(-1, 0), (0, -1), (10, 0), (0, 10), (10.5, 0), (0, 10.2)],
)
def test_is_wall_out_of_bounds(x, y):
    # Create a small map  size 2x2
    grid = [[0, 0], [0, 0]]
    world = World(map_grid=grid)
    # Any coordinate outside [0,2) should be treated as wall
    assert world.is_wall(x, y)


def test_is_wall_empty_and_wall_cells():
    grid = [[0, 1], [1, 0]]
    world = World(map_grid=grid)
    assert not world.is_wall(0, 0)
    assert world.is_wall(1, 0)
    assert world.is_wall(0, 1)
    assert not world.is_wall(1, 1)
