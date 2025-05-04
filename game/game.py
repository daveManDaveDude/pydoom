import sys
import pygame

from .world import World
from .player import Player
from .renderer import Renderer
from .config import SCREEN_WIDTH, SCREEN_HEIGHT, FPS, MOVE_SPEED, ROT_SPEED, FOV, STEP_SIZE, MOUSE_SENSITIVITY, MOUSE_SENSITIVITY_Y, MAX_PITCH, SPRITE_ROT_SPEED

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
        self.player = Player(x=3.0,
                             y=3.0,
                             angle=0.0,
                             move_speed=MOVE_SPEED,
                             rot_speed=ROT_SPEED)
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
        pygame.quit()
        sys.exit()