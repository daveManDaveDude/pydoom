import sys
import pygame

from .world import World
from .player import Player
from .renderer import Renderer

class Game:
    """Main Game class: handles initialization, loop, and high-level coordination."""
    def __init__(self):
        # Initialize Pygame and its subsystems
        pygame.init()
        # Screen setup
        self.screen_width = 800
        self.screen_height = 600
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
        pygame.display.set_caption("Doom-Like Prototype")
        # Clock for frame rate
        self.clock = pygame.time.Clock()
        # World and Player
        self.world = World()
        self.player = Player(x=3.0, y=3.0, angle=0.0)
        # Renderer
        self.renderer = Renderer(self.screen_width, self.screen_height)
        # Control flag
        self.running = True

    def handle_events(self):
        """Process Pygame events (e.g., quit)."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

    def update(self, dt):
        """Update game state: handle input and move player."""
        keys = pygame.key.get_pressed()
        # Movement
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            self.player.move(1, self.world, dt)
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            self.player.move(-1, self.world, dt)
        # Rotation
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            self.player.rotate(-1, dt)
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            self.player.rotate(1, dt)

    def render(self):
        """Render the entire scene."""
        self.renderer.render(self.screen, self.world, self.player)
        pygame.display.flip()

    def run(self):
        """Main loop: handle events, update, and render."""
        while self.running:
            dt = self.clock.tick(60) / 1000.0
            self.handle_events()
            self.update(dt)
            self.render()
        pygame.quit()
        sys.exit()