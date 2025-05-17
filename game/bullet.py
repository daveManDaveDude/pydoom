"""
Bullet/projectile representation for the game.
"""

from __future__ import annotations
import math
from typing import Tuple

from .config import BULLET_SPEED, BULLET_LIFESPAN


class Bullet:
    """
    Represents a projectile shot by the player.
    Attributes:
        x, y: World coordinates of the bullet.
        angle: Direction of travel in radians.
        speed: Movement speed in map units per second.
        dx, dy: Velocity components.
        lifespan: Remaining time before bullet expires (seconds).
        active: Whether the bullet is still active.
    """

    def __init__(self, x: float, y: float, angle: float) -> None:
        self.x = x
        self.y = y
        self.angle = angle
        self.speed = BULLET_SPEED
        # Compute velocity vector
        self.dx = math.cos(angle) * self.speed
        self.dy = math.sin(angle) * self.speed
        # Time before bullet expires
        self.lifespan = BULLET_LIFESPAN
        self.active = True

    def update(self, dt: float) -> None:
        """
        Move the bullet according to its velocity and reduce lifespan.
        Deactivate when lifespan reaches zero.
        """
        # Advance position
        self.x += self.dx * dt
        self.y += self.dy * dt
        # Decrease remaining life
        self.lifespan -= dt
        if self.lifespan <= 0:
            self.active = False

    def position(self) -> Tuple[float, float]:  # noqa: A003
        """Return current (x, y) position of the bullet."""
        return (self.x, self.y)
