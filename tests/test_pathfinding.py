from game.pathfinding import heuristic, find_path


class DummyWorld:
    """Simple stub for grid world with optional walls and bounds."""
    def __init__(self, walls=None):
        self._walls = walls or set()

    def is_wall(self, x, y):
        # Treat negative or far out coords as walls
        if x < 0 or y < 0 or x > 10 or y > 10:
            return True
        return (x, y) in self._walls


def test_heuristic_manhattan():
    # Manhattan distance heuristic
    assert heuristic((0, 0), (2, 3)) == 5


def test_find_path_simple():
    world = DummyWorld()
    path = find_path((0, 0), (2, 0), world)
    assert path == [(0, 0), (1, 0), (2, 0)]


def test_find_path_blocked_goal():
    # If goal cell is a wall, path should be empty
    world = DummyWorld(walls={(2, 0)})
    assert find_path((0, 0), (2, 0), world) == []