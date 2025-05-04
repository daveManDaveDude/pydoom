"""Sprite (billboard) representation for in-world objects."""

class Sprite:
    """
    Represents a billboard sprite in the world, with orientation.
    Attributes:
        x (float): X position in map coordinates.
        y (float): Y position in map coordinates.
        type (str): Identifier for the sprite type (used for selecting texture).
        orientation (float): Facing angle in radians (0 = +X axis).
    """
    def __init__(self, x, y, type, orientation=0.0):
        self.x = x
        self.y = y
        self.type = type
        # Orientation of the sprite in world space (radians)
        self.orientation = orientation