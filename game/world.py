from __future__ import annotations
import os
import json
import math
from typing import Optional, List, TYPE_CHECKING
from .config import (
    WORLD_FILE,
    DEFAULT_ENEMY_HEALTH,
    TILE_WALL,
    TILE_EMPTY,
    TILE_DOOR,
)
from .enemy import Enemy

if TYPE_CHECKING:
    from .player import Player


class Door:
    """Door entity tracking position and open/closed state."""

    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y
        # 'closed', 'opening', 'open', 'closing'
        self.state = "closed"
        # timer for auto-close delay
        self.timer: float = 0.0
        # 0.0 (closed) .. 1.0 (fully open) sliding progress
        self.progress: float = 0.0
        # sliding axis ('x' or 'y') and direction (+1 or -1)
        self.slide_axis: str = "x"
        self.slide_dir: int = 1

    def update(self, player: Player, dt: float) -> None:
        """
        Handle door state: auto-open when approached, auto-close after delay,
        and animate sliding over DOOR_ANIM_DURATION seconds.
        """
        from .config import (
            DOOR_OPEN_DISTANCE,
            DOOR_CLOSE_DELAY,
            DOOR_ANIM_DURATION,
        )

        # distance squared from player to door center
        dx = player.x - (self.x + 0.5)
        dy = player.y - (self.y + 0.5)
        dist2 = dx * dx + dy * dy
        # State machine for opening/closing
        if self.state == "closed":
            if dist2 <= DOOR_OPEN_DISTANCE * DOOR_OPEN_DISTANCE:
                self.state = "opening"
                self.timer = 0.0
        elif self.state == "opening":
            self.progress = min(1.0, self.progress + dt / DOOR_ANIM_DURATION)
            if self.progress >= 1.0:
                self.state = "open"
                self.timer = 0.0
        elif self.state == "open":
            # reset close timer when player in range
            if dist2 <= DOOR_OPEN_DISTANCE * DOOR_OPEN_DISTANCE:
                self.timer = 0.0
            else:
                self.timer += dt
                if self.timer >= DOOR_CLOSE_DELAY:
                    self.state = "closing"
        elif self.state == "closing":
            if dist2 <= DOOR_OPEN_DISTANCE * DOOR_OPEN_DISTANCE:
                # Reopen if player comes back while door is closing
                self.state = "opening"
            else:
                self.progress = max(
                    0.0, self.progress - dt / DOOR_ANIM_DURATION
                )
                if self.progress <= 0.0:
                    self.state = "closed"
                    self.timer = 0.0


class World:
    """World map representation loaded from external file (default) or provided grid."""

    def __init__(self, map_grid: Optional[List[List[int]]] = None) -> None:
        # Initialize map and other world attributes
        self.powerup_pos = None
        self.powerup_angle = 0.0
        self.enemies = []
        self.sprites = []
        self.doors: List[Door] = []
        if map_grid is not None:
            self.map = map_grid
        else:
            # Load map and other attributes from JSON file
            world_path = os.path.join(os.path.dirname(__file__), WORLD_FILE)
            try:
                with open(world_path, "r") as f:
                    data = json.load(f)
                self.map = data.get("map", [])
                # Load powerup attributes if specified
                pu = data.get("powerup")
                # If powerup specified as dict with pos and angle (angle in degrees)
                if isinstance(pu, dict):
                    pos = pu.get("pos")
                    if isinstance(pos, (list, tuple)) and len(pos) == 2:
                        self.powerup_pos = (float(pos[0]), float(pos[1]))
                    ang = pu.get("angle")
                    try:
                        self.powerup_angle = math.radians(float(ang))
                    except Exception:
                        pass
                # Legacy: powerup as simple [x, y]
                elif isinstance(pu, (list, tuple)) and len(pu) == 2:
                    self.powerup_pos = (float(pu[0]), float(pu[1]))
                # Load additional billboard sprites if specified
                self.sprites = []
                sprs = data.get("sprites")
                if isinstance(sprs, list):
                    for sp in sprs:
                        # Skip enemy definitions for static sprite list
                        if sp.get("type") == "enemy":
                            continue
                        pos = sp.get("pos")
                        height = sp.get("height", None)
                        # Determine animation textures list or single texture
                        texs = sp.get("textures")
                        if isinstance(texs, list) and all(
                            isinstance(t, str) for t in texs
                        ):
                            textures = texs
                        else:
                            tex = sp.get("texture")
                            if isinstance(tex, str):
                                textures = [tex]
                            else:
                                continue
                        if not (
                            isinstance(pos, (list, tuple)) and len(pos) == 2
                        ):
                            continue
                        try:
                            hval = float(height) if height is not None else None
                        except Exception:
                            hval = None
                        self.sprites.append(
                            {
                                "pos": (float(pos[0]), float(pos[1])),
                                "height": hval,
                                "textures": textures,
                            }
                        )
                # Parse enemy spawn definitions
                self.enemies = []
                if isinstance(sprs, list):
                    for sp in sprs:
                        if sp.get("type") != "enemy":
                            continue
                        # Parse position: support 'pos' or 'x','y' fields
                        pos = sp.get("pos")
                        if not (
                            isinstance(pos, (list, tuple)) and len(pos) == 2
                        ):
                            x_val = sp.get("x")
                            y_val = sp.get("y")
                            if x_val is None or y_val is None:
                                continue
                            pos = [x_val, y_val]
                        try:
                            ex = float(pos[0])
                            ey = float(pos[1])
                        except Exception:
                            continue
                        # Parse textures list or single texture
                        texs = sp.get("textures")
                        if isinstance(texs, list) and all(
                            isinstance(t, str) for t in texs
                        ):
                            textures = texs
                        else:
                            tex_single = sp.get("texture")
                            textures = (
                                [tex_single]
                                if isinstance(tex_single, str)
                                else []
                            )
                        # Parse height
                        h_raw = sp.get("height", 0.25)
                        try:
                            h_val = float(h_raw)
                        except Exception:
                            h_val = 0.25
                        # Parse optional health for enemy, default if not provided or invalid
                        health_raw = sp.get("health", None)
                        if health_raw is not None:
                            try:
                                health_val = int(health_raw)
                            except Exception:
                                health_val = DEFAULT_ENEMY_HEALTH
                        else:
                            health_val = DEFAULT_ENEMY_HEALTH
                        enemy = Enemy(
                            ex,
                            ey,
                            textures=textures,
                            height=h_val,
                            health=health_val,
                        )
                        self.enemies.append(enemy)
            except Exception as e:
                raise RuntimeError(
                    f"Failed to load world map from {world_path}: {e}"
                )
        self.height = len(self.map)
        self.width = len(self.map[0]) if self.height > 0 else 0

        for y, row in enumerate(self.map):
            for x, tile in enumerate(row):
                if tile == TILE_DOOR:
                    self.doors.append(Door(x, y))

        # Determine sliding orientation for each door
        for door in self.doors:
            x, y = door.x, door.y
            # Determine slide axis and direction based on adjacent empty cell
            if x + 1 < self.width and self.map[y][x + 1] == TILE_EMPTY:
                door.slide_axis = "x"
                door.slide_dir = 1
            elif x - 1 >= 0 and self.map[y][x - 1] == TILE_EMPTY:
                door.slide_axis = "x"
                door.slide_dir = -1
            elif y + 1 < self.height and self.map[y + 1][x] == TILE_EMPTY:
                door.slide_axis = "y"
                door.slide_dir = 1
            else:
                door.slide_axis = "y"
                door.slide_dir = -1

        self.room_map: List[List[int]] = [
            [-1] * self.width for _ in range(self.height)
        ]
        room_id = 0
        for ry in range(self.height):
            for rx in range(self.width):
                if (
                    self.map[ry][rx] != TILE_EMPTY
                    or self.room_map[ry][rx] != -1
                ):
                    continue
                stack = [(rx, ry)]
                while stack:
                    cx, cy = stack.pop()
                    if (
                        cx < 0
                        or cy < 0
                        or cx >= self.width
                        or cy >= self.height
                        or self.map[cy][cx] != TILE_EMPTY
                        or self.room_map[cy][cx] != -1
                    ):
                        continue
                    self.room_map[cy][cx] = room_id
                    stack.extend(
                        [(cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)]
                    )
                room_id += 1
        self.num_rooms = room_id

        for enemy in self.enemies:
            exi, eyi = int(enemy.x), int(enemy.y)
            enemy.home_room = self.room_map[eyi][exi]

    def update_doors(self, player: Player, dt: float) -> None:
        """Update door states (auto-open/close) based on the player's position."""
        for door in self.doors:
            door.update(player, dt)

    def is_wall(self, x: float, y: float) -> bool:
        """Return True if (x, y) is a wall, a closed door, or out of bounds."""
        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            return True
        tx, ty = int(x), int(y)
        for door in self.doors:
            if 0.0 < door.progress < 1.0:
                if door.slide_axis == "x":
                    adj_x, adj_y = door.x + door.slide_dir, door.y
                else:
                    adj_x, adj_y = door.x, door.y + door.slide_dir
                if tx == adj_x and ty == adj_y:
                    return True
        tile = self.map[ty][tx]
        if tile == TILE_DOOR:
            for door in self.doors:
                if door.x == tx and door.y == ty:
                    return door.state != "open"
            return True
        return tile == TILE_WALL

    def get_room_id(self, x: float, y: float) -> Optional[int]:
        """
        Return the room ID at the given world coordinates, or None if out of bounds.
        For a door cell, return the room ID of an adjacent cell only when the
        door's state is "open" to allow enemies to chase through an open doorway.
        """
        ix, iy = int(x), int(y)
        if ix < 0 or iy < 0 or ix >= self.width or iy >= self.height:
            return None
        room = self.room_map[iy][ix]
        if room >= 0:
            return room
        if self.map[iy][ix] == TILE_DOOR:
            for door in self.doors:
                # Only allow passage through fully open doors
                if door.x == ix and door.y == iy and door.state == "open":
                    for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
                        nx, ny = ix + dx, iy + dy
                        if 0 <= nx < self.width and 0 <= ny < self.height:
                            adj_room = self.room_map[ny][nx]
                            if adj_room >= 0:
                                return adj_room
        return None
