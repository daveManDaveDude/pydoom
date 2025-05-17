from __future__ import annotations
import math
from typing import TYPE_CHECKING
from .config import MOVE_SPEED, ROT_SPEED

if TYPE_CHECKING:
    from .world import World


class Player:
    """Player state and movement."""

    def __init__(
        self,
        x: float = 3.0,
        y: float = 3.0,
        angle: float = 0.0,
        move_speed: float = MOVE_SPEED,
        rot_speed: float = ROT_SPEED,
    ) -> None:
        """
        Initialize the player.
        x, y: starting position in map blocks (floats allowed).
        angle: facing direction in radians.
        move_speed: movement speed in blocks per second.
        rot_speed: rotation speed in radians per second.
        """
        self.x = x
        self.y = y
        self.angle = angle
        self.move_speed = move_speed
        self.rot_speed = rot_speed
        # Vertical look (pitch), offset in pixels
        self.pitch = 0.0

    def move(self, direction: int, world: World, dt: float) -> None:
        """Move the player forward (direction=1) or backward (direction=-1)."""
        dx = math.cos(self.angle) * self.move_speed * dt * direction
        dy = math.sin(self.angle) * self.move_speed * dt * direction
        new_x = self.x + dx
        new_y = self.y + dy
        if not world.is_wall(new_x, new_y):
            self.x = new_x
            self.y = new_y

    def strafe(self, direction: int, world: World, dt: float) -> None:
        """Strafe the player right (direction=1) or left (direction=-1)."""
        # Perpendicular direction vector (right-handed)
        dx = -math.sin(self.angle) * self.move_speed * dt * direction
        dy = math.cos(self.angle) * self.move_speed * dt * direction
        new_x = self.x + dx
        new_y = self.y + dy
        if not world.is_wall(new_x, new_y):
            self.x = new_x
            self.y = new_y

    def rotate(self, direction: int, dt: float) -> None:
        """Rotate the player left (direction=-1) or right (direction=1)."""
        self.angle += self.rot_speed * dt * direction
