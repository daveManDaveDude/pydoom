import math
from .config import MOVE_SPEED, ROT_SPEED

class Player:
    """Player state and movement."""
    def __init__(self, x=3.0, y=3.0, angle=0.0,
                 move_speed=MOVE_SPEED,
                 rot_speed=ROT_SPEED):
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

    def move(self, direction, world, dt):
        """Move the player forward (direction=1) or backward (direction=-1)."""
        dx = math.cos(self.angle) * self.move_speed * dt * direction
        dy = math.sin(self.angle) * self.move_speed * dt * direction
        new_x = self.x + dx
        new_y = self.y + dy
        if not world.is_wall(new_x, new_y):
            self.x = new_x
            self.y = new_y

    def rotate(self, direction, dt):
        """Rotate the player left (direction=-1) or right (direction=1)."""
        self.angle += self.rot_speed * dt * direction