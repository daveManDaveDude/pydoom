import os
import json
from .config import WORLD_FILE
from .enemy import Enemy

class World:
    """World map representation loaded from external file (default) or provided grid."""
    def __init__(self, map_grid=None):
        # Initialize map and other world attributes
        self.powerup_pos = None
        self.powerup_angle = 0.0
        # Initialize list of enemies
        self.enemies = []
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
                        # Skip enemy definitions for static sprite list
                        if sp.get('type') == 'enemy':
                            continue
                        pos = sp.get('pos')
                        height = sp.get('height', None)
                        # Determine animation textures list or single texture
                        texs = sp.get('textures')
                        if isinstance(texs, list) and all(isinstance(t, str) for t in texs):
                            textures = texs
                        else:
                            tex = sp.get('texture')
                            if isinstance(tex, str):
                                textures = [tex]
                            else:
                                continue
                        if not (isinstance(pos, (list, tuple)) and len(pos) == 2):
                            continue
                        try:
                            hval = float(height) if height is not None else None
                        except Exception:
                            hval = None
                        self.sprites.append({
                            'pos': (float(pos[0]), float(pos[1])),
                            'height': hval,
                            'textures': textures
                        })
                # Parse enemy spawn definitions
                self.enemies = []
                if isinstance(sprs, list):
                    for sp in sprs:
                        if sp.get('type') != 'enemy':
                            continue
                        # Parse position: support 'pos' or 'x','y' fields
                        pos = sp.get('pos')
                        if not (isinstance(pos, (list, tuple)) and len(pos) == 2):
                            x_val = sp.get('x'); y_val = sp.get('y')
                            if x_val is None or y_val is None:
                                continue
                            pos = [x_val, y_val]
                        try:
                            ex = float(pos[0]); ey = float(pos[1])
                        except Exception:
                            continue
                        # Parse textures list or single texture
                        texs = sp.get('textures')
                        if isinstance(texs, list) and all(isinstance(t, str) for t in texs):
                            textures = texs
                        else:
                            tex_single = sp.get('texture')
                            textures = [tex_single] if isinstance(tex_single, str) else []
                        # Parse height
                        h_raw = sp.get('height', 0.25)
                        try:
                            h_val = float(h_raw)
                        except Exception:
                            h_val = 0.25
                        enemy = Enemy(ex, ey, textures=textures, height=h_val)
                        self.enemies.append(enemy)
            except Exception as e:
                raise RuntimeError(f"Failed to load world map from {world_path}: {e}")
        self.height = len(self.map)
        self.width = len(self.map[0]) if self.height > 0 else 0

    def is_wall(self, x, y):
        """Return True if (x, y) is a wall or out of bounds."""
        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            return True
        return self.map[int(y)][int(x)] == 1