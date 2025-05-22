from __future__ import annotations
import math
import random
import pygame
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .enemy import Enemy

from .world import World
from .player import Player
from .renderer import Renderer
from .config import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    FPS,
    MOVE_SPEED,
    ROT_SPEED,
    FOV,
    STEP_SIZE,
    MOUSE_SENSITIVITY,
    MOUSE_SENSITIVITY_Y,
    MAX_PITCH,
    SPRITE_ROT_SPEED,
    ENEMY_SPEED,
    COLLISION_RADIUS,
    BULLET_HIT_RADIUS,
    ENEMY_RESPAWN_DELAY,
    ENEMY_LOS_DIRECT_DELAY,
    HIT_FLASH_DURATION_MS,
)
from .bullet import Bullet
from .input_handler import InputHandler


class Game:
    """Main Game class: handles initialization, loop, and high-level coordination."""

    def __init__(self, clock: Optional[pygame.time.Clock] = None) -> None:
        # Initialize Pygame and its subsystems
        pygame.init()
        # Screen setup
        self.screen_width = SCREEN_WIDTH
        self.screen_height = SCREEN_HEIGHT
        # Initialize an OpenGL-enabled window
        self.screen = pygame.display.set_mode(
            (self.screen_width, self.screen_height),
            pygame.OPENGL | pygame.DOUBLEBUF,
        )
        pygame.display.set_caption("Doom-Like Prototype")
        # Hide mouse cursor and capture it for relative motion
        pygame.mouse.set_visible(False)
        pygame.event.set_grab(True)
        # Flush any initial mouse movement deltas
        pygame.mouse.get_rel()
        # Clock for frame rate (injectable for testing)
        self.clock = clock or pygame.time.Clock()
        # Target frames per second (configurable)
        self.fps = FPS
        # World and Player
        self.world = World()
        self.player = Player(
            x=12,
            y=8.5,
            angle=math.pi,
            move_speed=MOVE_SPEED,
            rot_speed=ROT_SPEED,
        )
        # Instantiate enemies from world spawn definitions
        # Store dynamic actors separately from static sprites
        self.enemies = list(self.world.enemies)
        # Store active bullets/projectiles
        self.bullets = []
        # Renderer: GPU-based floor/ceiling shaders plus CPU wall casting
        self.renderer = Renderer(
            self.screen_width,
            self.screen_height,
            fov=FOV,
            step_size=STEP_SIZE,
            world=self.world,
        )
        # Input abstraction
        self.input = InputHandler()
        # Control flag
        self.running = True

    def handle_events(self) -> None:
        """Process input events via InputHandler and handle quit/fire actions."""
        self.input.process_events()
        if self.input.should_quit():
            self.running = False
        if self.input.fire_pressed():
            # Spawn bullet slightly in front of player
            offset = 0.2
            bx = self.player.x + math.cos(self.player.angle) * offset
            by = self.player.y + math.sin(self.player.angle) * offset
            self.bullets.append(Bullet(bx, by, self.player.angle))

    def update(self, dt: float) -> None:
        """Update game state: handle input-driven movement and actions."""
        # Mouse look: horizontal (yaw) and vertical (pitch)
        dx, dy = self.input.get_mouse_rel()
        self.player.angle += dx * MOUSE_SENSITIVITY
        self.player.pitch -= dy * MOUSE_SENSITIVITY_Y
        # Clamp pitch to limits
        self.player.pitch = max(-MAX_PITCH, min(MAX_PITCH, self.player.pitch))
        # Auto‑open/close doors when player moves
        self.world.update_doors(self.player, dt)
        # Keyboard movement: forward/backward and strafing
        keys = self.input.get_key_state()
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
        if (
            hasattr(self.world, "powerup_angle")
            and self.world.powerup_angle is not None
        ):
            self.world.powerup_angle += SPRITE_ROT_SPEED * dt
        # Enemy chasing logic: only pursue if in same room as player
        player_room = self.world.get_room_id(self.player.x, self.player.y)
        for enemy in self.enemies:
            if getattr(enemy, "home_room", None) != player_room:
                continue
            # Skip enemies that are dead or awaiting respawn
            if getattr(enemy, "respawn_timer", 0) > 0 or enemy.health <= 0:
                continue
            # Update sight timer for line-of-sight detection
            if self._is_visible_to_player(enemy.x, enemy.y):
                enemy.sight_timer += dt
            else:
                enemy.sight_timer = 0.0
            # Choose chase behavior: direct only after LOS has held for delay
            if enemy.sight_timer >= ENEMY_LOS_DIRECT_DELAY:
                # Direct pursuit: head toward exact player position
                target_x = self.player.x
                target_y = self.player.y
            else:
                # Pathfinding pursuit: follow next waypoint
                path = enemy.find_path(
                    self.world, (self.player.x, self.player.y)
                )
                if len(path) > 1:
                    # Next waypoint cell center
                    target_x = path[1][0] + 0.5
                    target_y = path[1][1] + 0.5
                elif len(path) == 1:
                    # Same cell: head directly at player
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
                # Only move if not colliding with wall
                if not self.world.is_wall(int(new_x), int(new_y)):
                    enemy.x = new_x
                    enemy.y = new_y
        # Collision detection: if an enemy reaches the player, schedule respawn
        for enemy in self.enemies:
            # Skip enemies already dead/pending respawn
            if getattr(enemy, "respawn_timer", 0) > 0:
                continue
            dx_e = enemy.x - self.player.x
            dy_e = enemy.y - self.player.y
            if math.hypot(dx_e, dy_e) < COLLISION_RADIUS:
                # Kill enemy and start respawn timer
                enemy.health = 0
                enemy.respawn_timer = ENEMY_RESPAWN_DELAY
        # Update bullets: move, check lifespan and wall collisions
        for bullet in self.bullets:
            bullet.update(dt)
            # Deactivate if out of lifespan or collided with a wall
            if not bullet.active or self.world.is_wall(
                int(bullet.x), int(bullet.y)
            ):
                bullet.active = False
                continue
            # Check collision with alive enemies
            for enemy in self.enemies:
                if getattr(enemy, "respawn_timer", 0) > 0 or enemy.health <= 0:
                    continue
                dx_b = bullet.x - enemy.x
                dy_b = bullet.y - enemy.y
                if math.hypot(dx_b, dy_b) < BULLET_HIT_RADIUS:
                    bullet.active = False
                    self.renderer.hit_flash_until = (
                        pygame.time.get_ticks() + HIT_FLASH_DURATION_MS
                    )
                    enemy.health -= 1
                    break
        # Remove inactive bullets
        self.bullets = [b for b in self.bullets if b.active]
        # Process enemy respawn timers
        for enemy in self.enemies:
            if getattr(enemy, "respawn_timer", 0) > 0:
                enemy.respawn_timer -= dt
                if enemy.respawn_timer <= 0:
                    # Time to respawn: teleport and reset health
                    self._respawn_enemy(enemy)
        # End of update

    def _respawn_enemy(self, enemy: Enemy) -> None:
        """
        Teleport the given enemy back to its original spawn location or, if unknown,
        to a random free cell away from walls, player, and other enemies.
        """
        w = self.world
        # Respawn at original spawn if available
        if hasattr(enemy, "spawn_x") and hasattr(enemy, "spawn_y"):
            enemy.x = enemy.spawn_x
            enemy.y = enemy.spawn_y
        else:
            player_cell = (int(self.player.x), int(self.player.y))
            for _ in range(100):
                rx = random.randrange(w.width)
                ry = random.randrange(w.height)
                if w.is_wall(rx, ry):
                    continue
                if (rx, ry) == player_cell:
                    continue
                conflict = any(
                    other is not enemy
                    and (int(other.x), int(other.y)) == (rx, ry)
                    for other in self.enemies
                )
                if conflict:
                    continue
                cx, cy = rx + 0.5, ry + 0.5
                if math.hypot(cx - self.player.x, cy - self.player.y) < 2.0:
                    continue
                if self._is_visible_to_player(cx, cy):
                    continue
                enemy.x = cx
                enemy.y = cy
                break
        # Restore full health and clear respawn timer
        if hasattr(enemy, "max_health"):
            enemy.health = enemy.max_health
        if hasattr(enemy, "respawn_timer"):
            enemy.respawn_timer = 0.0

    def _is_visible_to_player(self, x: float, y: float) -> bool:
        """
        Return True if (x, y) is visible to the player (no wall blocking).
        """
        px, py = self.player.x, self.player.y
        dx = x - px
        dy = y - py
        dist = math.hypot(dx, dy)
        # Sample along the line at intervals, check for walls
        steps = max(int(dist / 0.1), 1)
        for i in range(1, steps):
            t = i / steps
            ix = px + dx * t
            iy = py + dy * t
            if self.world.is_wall(int(ix), int(iy)):
                return False
        return True

    def render(self) -> None:
        """Render the entire scene."""
        # Delegate drawing to OpenGL renderer (which swaps buffers internally)
        self.renderer.render(self.screen, self.world, self.player)

    def run(self) -> None:
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
        # Return to caller instead of exiting process
        return
