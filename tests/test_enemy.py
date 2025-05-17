
from game.enemy import Enemy


class DummyWorld:
    def is_wall(self, x, y):
        return False


def test_enemy_repr():
    e = Enemy(1.2345, 2.3456, textures=['tex.png'])
    r = repr(e)
    # repr should include rounded position and texture list
    assert 'x=1.23' in r and 'y=2.35' in r
    assert "textures=['tex.png']" in r


def test_find_path_delegation(monkeypatch):
    e = Enemy(0, 0)
    calls = []

    def fake_find_path(start, goal, world):
        calls.append((start, goal, world))
        return ['dummy']

    # Monkey-patch the pathfinding function
    import game.pathfinding
    monkeypatch.setattr(game.pathfinding, 'find_path', fake_find_path)

    world = DummyWorld()
    path = e.find_path(world, (3, 4))
    assert path == ['dummy']
    # Ensure delegation with integer start/goal cells
    assert len(calls) == 1
    start, goal, world_arg = calls[0]
    assert start == (0, 0)
    assert goal == (3, 4)
    assert world_arg is world