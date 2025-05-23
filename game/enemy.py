"""
Enemy module: defines the Enemy class for game AI.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional, Tuple

from .config import DEFAULT_ENEMY_HEALTH

if TYPE_CHECKING:
    from .world import World


class Enemy:
    """Represents an enemy in the game world."""

    def __init__(
        self,
        x: float,
        y: float,
        textures: Optional[List[str]] = None,
        height: float = 0.25,
        health: Optional[int] = None,
    ) -> None:
        # Position in world coordinates
        self.x = float(x)
        self.y = float(y)
        self.spawn_x = self.x
        self.spawn_y = self.y
        # Animation frames or single texture for rendering
        self.textures = textures or []
        # Height of the sprite in world units
        self.height = float(height)
        # Initial facing angle (radians), can be updated by AI
        self.angle = 0.0
        # Health: number of bullet hits to eliminate
        # Use provided health or default from config
        if health is None:
            health = DEFAULT_ENEMY_HEALTH
        self.max_health = int(health)
        self.health = int(health)
        # Timer until respawn after death (seconds); >0 means pending respawn
        self.respawn_timer = 0.0
        # Timer counting line-of-sight before direct pursuit (seconds)
        self.sight_timer = 0.0

    def __repr__(self) -> str:
        return f"<Enemy x={self.x:.2f} y={self.y:.2f} textures={self.textures}>"

    def find_path(
        self, world: World, goal: Tuple[float, float]
    ) -> List[Tuple[int, int]]:
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
