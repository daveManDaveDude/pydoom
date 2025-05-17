import math
from game import config


def test_fov_value():
    # Field of view should be pi/3 radians
    assert math.isclose(config.FOV, math.pi / 3, rel_tol=1e-9)


def test_world_file_extension():
    # World file should be a JSON definition
    assert config.WORLD_FILE.endswith(".json")
