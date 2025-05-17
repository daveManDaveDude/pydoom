import math

import pytest

from game.player import Player


class DummyWorld:
    """Minimal world stub to control wall collisions."""

    def __init__(self, walls=None):
        # walls as set of (int_x, int_y) positions considered as walls
        self._walls = set(walls or [])

    def is_wall(self, x, y):
        # Convert to grid cell
        return (int(x), int(y)) in self._walls


@pytest.mark.parametrize(
    "direction,angle,expected_dx,expected_dy",
    [
        (1, 0.0, 1.0, 0.0),  # move forward along +x
        (1, math.pi / 2, 0.0, 1.0),  # move forward along +y
        (-1, 0.0, -1.0, 0.0),  # move backward along -x
    ],
)
def test_player_move_no_walls(direction, angle, expected_dx, expected_dy):
    # Use move_speed=1 and dt=1 for simplicity
    player = Player(x=0.0, y=0.0, angle=angle, move_speed=1.0, rot_speed=0.0)
    world = DummyWorld(walls=[])
    player.move(direction, world, dt=1.0)
    # Expect movement exactly expected_dx, expected_dy
    assert pytest.approx(player.x, rel=1e-6) == expected_dx
    assert pytest.approx(player.y, rel=1e-6) == expected_dy


def test_player_move_hits_wall_and_stops():
    # Position starts at x=0,y=0 facing +x; wall at cell (1,0)
    player = Player(x=0.0, y=0.0, angle=0.0, move_speed=1.0, rot_speed=0.0)
    world = DummyWorld(walls=[(1, 0)])
    player.move(1, world, dt=1.0)
    # Movement should be blocked, position unchanged
    assert player.x == 0.0 and player.y == 0.0


@pytest.mark.parametrize(
    "direction,expected_dx,expected_dy", [(1, 0.0, 1.0), (-1, 0.0, -1.0)]
)
def test_player_strafe(direction, expected_dx, expected_dy):
    # Strafe right or left; starting facing along +x (angle=0)
    player = Player(x=0.0, y=0.0, angle=0.0, move_speed=1.0, rot_speed=0.0)
    world = DummyWorld(walls=[])
    player.strafe(direction, world, dt=1.0)
    assert pytest.approx(player.x, rel=1e-6) == expected_dx
    assert pytest.approx(player.y, rel=1e-6) == expected_dy


def test_player_rotate_changes_angle():
    player = Player(x=0.0, y=0.0, angle=0.0, move_speed=0.0, rot_speed=math.pi)
    # Rotate right (direction=1) for dt=0.5 => angle increases by pi*0.5
    player.rotate(1, dt=0.5)
    assert pytest.approx(player.angle, rel=1e-6) == math.pi * 0.5
