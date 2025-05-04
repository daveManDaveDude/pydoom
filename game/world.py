import os
import json
from .config import WORLD_FILE

class World:
    """World map representation loaded from external file (default) or provided grid."""
    def __init__(self, map_grid=None):
        # Initialize map and other world attributes
        self.powerup = None
        if map_grid is not None:
            self.map = map_grid
        else:
            # Load map and other attributes from JSON file
            world_path = os.path.join(os.path.dirname(__file__), WORLD_FILE)
            try:
                with open(world_path, 'r') as f:
                    data = json.load(f)
                self.map = data.get('map', [])
                # Load powerup position if specified
                pu = data.get('powerup')
                if isinstance(pu, (list, tuple)) and len(pu) == 2:
                    self.powerup = (float(pu[0]), float(pu[1]))
            except Exception as e:
                raise RuntimeError(f"Failed to load world map from {world_path}: {e}")
        self.height = len(self.map)
        self.width = len(self.map[0]) if self.height > 0 else 0

    def is_wall(self, x, y):
        """Return True if (x, y) is a wall or out of bounds."""
        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            return True
        return self.map[int(y)][int(x)] == 1