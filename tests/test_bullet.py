import math

from game.bullet import Bullet
from game.config import BULLET_SPEED, BULLET_LIFESPAN


def test_bullet_initialization_and_position():
    angle = math.pi / 2
    b = Bullet(1.0, 2.0, angle)
    # Initial position and velocity decomposition
    assert b.x == 1.0 and b.y == 2.0
    # dx should be effectively zero when angle is pi/2
    assert math.isclose(b.dx, 0.0, abs_tol=1e-9)
    assert math.isclose(b.dy, BULLET_SPEED, rel_tol=1e-9)
    assert b.lifespan == BULLET_LIFESPAN
    assert b.active
    assert b.position() == (b.x, b.y)


def test_bullet_update_and_expiry():
    b = Bullet(0, 0, 0.0)
    dt = 0.5
    b.update(dt)
    # Position evolves according to speed and dt
    assert math.isclose(b.x, BULLET_SPEED * dt, rel_tol=1e-9)
    assert math.isclose(b.lifespan, BULLET_LIFESPAN - dt, rel_tol=1e-9)
    assert b.active
    # Expire bullet when lifespan is exhausted
    b.update(BULLET_LIFESPAN)
    assert not b.active