import sys
import math
import random
import pygame

from .world import World
from .player import Player
from .renderer import Renderer
from .config import SCREEN_WIDTH, SCREEN_HEIGHT, FPS, MOVE_SPEED, ROT_SPEED, FOV, STEP_SIZE, MOUSE_SENSITIVITY, MOUSE_SENSITIVITY_Y, MAX_PITCH, SPRITE_ROT_SPEED, ENEMY_SPEED, COLLISION_RADIUS

class Game:
    """Main Game class: handles initialization, loop, and high-level coordination."""
    def __init__(self):
        # Initialize Pygame and its subsystems
        pygame.init()
        # Screen setup
        self.screen_width = SCREEN_WIDTH
        self.screen_height = SCREEN_HEIGHT
        # Initialize an OpenGL-enabled window
        self.screen = pygame.display.set_mode(
            (self.screen_width, self.screen_height),
            pygame.OPENGL | pygame.DOUBLEBUF
        )
        pygame.display.set_caption("Doom-Like Prototype")
        # Hide mouse cursor and capture it for relative motion
        pygame.mouse.set_visible(False)
        pygame.event.set_grab(True)
        # Flush any initial mouse movement deltas
        pygame.mouse.get_rel()
        # Clock for frame rate
        self.clock = pygame.time.Clock()
        # Target frames per second
        self.fps = FPS
        # World and Player
        self.world = World()
        self.player = Player(x=3.5,
                             y=3.5,
                             angle=0.0,
                             move_speed=MOVE_SPEED,
                             rot_speed=ROT_SPEED)
        # Instantiate enemies from world spawn definitions
        # Store dynamic actors separately from static sprites
        self.enemies = list(self.world.enemies)
        # Renderer
        # Pass world into renderer for wall raycasting
        self.renderer = Renderer(
            self.screen_width,
            self.screen_height,
            fov=FOV,
            step_size=STEP_SIZE,
            world=self.world
        )
        # Control flag
        self.running = True

    def handle_events(self):
        """Process Pygame events (e.g., quit)."""
        for event in pygame.event.get():
            # Quit on window close
            if event.type == pygame.QUIT:
                self.running = False
            # Quit on pressing Q
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_q:
                self.running = False

    def update(self, dt):
        """Update game state: handle input and move player."""
        # Mouse look: horizontal (yaw) and vertical (pitch)
        dx, dy = pygame.mouse.get_rel()
        self.player.angle += dx * MOUSE_SENSITIVITY
        self.player.pitch -= dy * MOUSE_SENSITIVITY_Y
        # Clamp pitch to limits
        self.player.pitch = max(-MAX_PITCH, min(MAX_PITCH, self.player.pitch))
        # Keyboard movement: forward/backward and strafing
        keys = pygame.key.get_pressed()
        # Forward/backward
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            self.player.move(1, self.world, dt)
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            self.player.move(-1, self.world, dt)
        # Strafe left/right (AD or arrow keys)
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            self.player.strafe(-1, self.world, dt)
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            self.player.strafe(1, self.world, dt)
        # Rotate powerup sprite
        if hasattr(self.world, 'powerup_angle') and self.world.powerup_angle is not None:
            self.world.powerup_angle += SPRITE_ROT_SPEED * dt
        # Enemy chasing logic: recompute path each frame towards player
        for enemy in self.enemies:
            # Determine path on integer grid
            path = enemy.find_path(self.world, (self.player.x, self.player.y))
            if len(path) > 1:
                # Next waypoint cell center
                target_x = path[1][0] + 0.5
                target_y = path[1][1] + 0.5
            elif len(path) == 1:
                # Already in same cell: head toward exact player position
                target_x = self.player.x
                target_y = self.player.y
            else:
                # No path available: skip movement
                continue
            # Compute movement vector toward target
            dx = target_x - enemy.x
            dy = target_y - enemy.y
            dist = math.hypot(dx, dy)
            if dist > 1e-6:
                step = ENEMY_SPEED * dt
                if dist < step:
                    step = dist
                new_x = enemy.x + (dx / dist) * step
                new_y = enemy.y + (dy / dist) * step
                if not self.world.is_wall(int(new_x), int(new_y)):
                    enemy.x = new_x
                    enemy.y = new_y
        # Collision detection: if an enemy reaches the player, respawn it
        for enemy in self.enemies:
            dx_e = enemy.x - self.player.x
            dy_e = enemy.y - self.player.y
            if math.hypot(dx_e, dy_e) < COLLISION_RADIUS:
                self._respawn_enemy(enemy)

    def _respawn_enemy(self, enemy):
        """
        Teleport the given enemy to a random free cell away from walls, player, and other enemies.
        """
        w = self.world
        player_cell = (int(self.player.x), int(self.player.y))
        for _ in range(100):
            rx = random.randrange(w.width)
            ry = random.randrange(w.height)
            # Must be walkable
            if w.is_wall(rx, ry):
                continue
            # Not on player
            if (rx, ry) == player_cell:
                continue
            # Not on another enemy
            conflict = any(
                other is not enemy and (int(other.x), int(other.y)) == (rx, ry)
                for other in self.enemies
            )
            if conflict:
                continue
            # Ensure sufficient distance from player (at least 2 units)
            cx, cy = rx + 0.5, ry + 0.5
            if math.hypot(cx - self.player.x, cy - self.player.y) < 2.0:
                continue
            # Found valid spawn
            enemy.x = cx
            enemy.y = cy
            return
        # Fallback: do nothing if no suitable tile found

    def render(self):
        """Render the entire scene."""
        # Delegate drawing to OpenGL renderer (which swaps buffers internally)
        self.renderer.render(self.screen, self.world, self.player)

    def run(self):
        """Main loop: handle events, update, and render."""
        while self.running:
            # Cap the frame rate and compute delta time in seconds
            dt = self.clock.tick(self.fps) / 1000.0
            self.handle_events()
            self.update(dt)
            self.render()
        # Clean up GL resources before quitting
        self.renderer.shutdown()
        pygame.quit()
        sys.exit()