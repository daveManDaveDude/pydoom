import math


from game.world import World
from game.config import DEFAULT_ENEMY_HEALTH


def test_world_custom_map_grid_and_is_wall():
    grid = [[0, 1], [1, 0]]
    w = World(map_grid=grid)
    # Custom grid should be used directly
    assert w.map == grid
    assert w.width == 2 and w.height == 2
    # No powerup or sprites/enemies by default
    assert w.powerup_pos is None
    assert w.powerup_angle == 0.0
    assert w.sprites == []
    assert w.enemies == []
    # is_wall should detect bounds and wall cells
    assert not w.is_wall(0, 0)
    assert w.is_wall(1, 0)
    assert w.is_wall(-1, 0)
    assert w.is_wall(0, -1)


def test_world_default_json_loading():
    w = World()
    # Default world map should load from JSON and have valid dimensions
    assert w.map
    assert w.width > 0 and w.height > 0
    # Powerup position and angle per default.json
    assert w.powerup_pos == (3.5, 5.5)
    assert math.isclose(w.powerup_angle, math.radians(45), rel_tol=1e-9)
    # No static sprites, only enemy spawns
    assert w.sprites == []
    assert len(w.enemies) == 2
    for e in w.enemies:
        assert e.health == DEFAULT_ENEMY_HEALTH
