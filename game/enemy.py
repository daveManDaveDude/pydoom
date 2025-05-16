"""
Enemy module: defines the Enemy class for game AI.
"""

class Enemy:
    """Represents an enemy in the game world."""

    def __init__(self, x, y, textures=None, height=0.25, health=2):
        # Position in world coordinates
        self.x = float(x)
        self.y = float(y)
        # Animation frames or single texture for rendering
        self.textures = textures or []
        # Height of the sprite in world units
        self.height = float(height)
        # Initial facing angle (radians), can be updated by AI
        self.angle = 0.0
        # Health: number of bullet hits to eliminate
        self.max_health = int(health)
        self.health = int(health)
        # Timer until respawn after death (seconds); >0 means pending respawn
        self.respawn_timer = 0.0

    def __repr__(self):
        return f"<Enemy x={self.x:.2f} y={self.y:.2f} textures={self.textures}>"
    def find_path(self, world, goal):
        """
        Compute a path from this enemy's current grid cell to the goal cell.
        world: game world instance with is_wall method.
        goal: (x, y) target grid coordinates (floats or ints).
        Returns list of (x, y) integer grid coords or empty list if unreachable.
        """
        from .pathfinding import find_path as _find_path
        start_cell = (int(self.x), int(self.y))
        goal_cell = (int(goal[0]), int(goal[1]))
        return _find_path(start_cell, goal_cell, world)