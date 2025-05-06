import os
import json
from .config import WORLD_FILE

class World:
    """World map representation loaded from external file (default) or provided grid."""
    def __init__(self, map_grid=None):
        # Initialize map and other world attributes
        self.powerup_pos = None
        self.powerup_angle = 0.0
        if map_grid is not None:
            self.map = map_grid
        else:
            # Load map and other attributes from JSON file
            world_path = os.path.join(os.path.dirname(__file__), WORLD_FILE)
            try:
                with open(world_path, 'r') as f:
                    data = json.load(f)
                self.map = data.get('map', [])
                # Load powerup attributes if specified
                pu = data.get('powerup')
                # If powerup specified as dict with pos and angle
                if isinstance(pu, dict):
                    pos = pu.get('pos')
                    if isinstance(pos, (list, tuple)) and len(pos) == 2:
                        self.powerup_pos = (float(pos[0]), float(pos[1]))
                    ang = pu.get('angle')
                    try:
                        self.powerup_angle = float(ang)
                    except Exception:
                        pass
                # Legacy: powerup as simple [x, y]
                elif isinstance(pu, (list, tuple)) and len(pu) == 2:
                    self.powerup_pos = (float(pu[0]), float(pu[1]))
                # Load additional billboard sprites if specified
                self.sprites = []
                sprs = data.get('sprites')
                if isinstance(sprs, list):
                    for sp in sprs:
                        pos = sp.get('pos')
                        tex = sp.get('texture')
                        height = sp.get('height', None)
                        if isinstance(pos, (list, tuple)) and len(pos) == 2 and isinstance(tex, str):
                            try:
                                hval = float(height) if height is not None else None
                            except Exception:
                                hval = None
                            self.sprites.append({
                                'pos': (float(pos[0]), float(pos[1])), 'texture': tex,
                                'height': hval
                            })
            except Exception as e:
                raise RuntimeError(f"Failed to load world map from {world_path}: {e}")
        self.height = len(self.map)
        self.width = len(self.map[0]) if self.height > 0 else 0

    def is_wall(self, x, y):
        """Return True if (x, y) is a wall or out of bounds."""
        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            return True
        return self.map[int(y)][int(x)] == 1