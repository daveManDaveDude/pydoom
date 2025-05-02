import math
import pygame

class Renderer:
    """Renderer for drawing the 3D view using raycasting."""
    def __init__(self, screen_width, screen_height, fov=math.pi/3, step_size=0.01):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.fov = fov
        self.step_size = step_size
        self.num_rays = screen_width
        self.half_fov = fov / 2
        self.angle_step = fov / self.num_rays

    def render(self, screen, world, player):
        """Render ceiling, floor, and walls."""
        # Draw ceiling (dark) and floor (lighter)
        screen.fill((30, 30, 30), (0, 0, self.screen_width, self.screen_height // 2))
        screen.fill((50, 50, 50), (0, self.screen_height // 2, self.screen_width, self.screen_height // 2))
        max_depth = max(world.width, world.height)

        for ray in range(self.num_rays):
            ray_angle = player.angle - self.half_fov + ray * self.angle_step
            distance = 0.0
            hit = False

            # Cast the ray
            while not hit and distance < max_depth:
                distance += self.step_size
                test_x = player.x + math.cos(ray_angle) * distance
                test_y = player.y + math.sin(ray_angle) * distance
                if world.is_wall(test_x, test_y):
                    hit = True

            # Correct fish-eye effect
            perp_distance = distance * math.cos(ray_angle - player.angle)
            if perp_distance == 0:
                perp_distance = 0.0001

            # Calculate slice height
            slice_height = int(self.screen_height / perp_distance)
            start_y = max(0, (self.screen_height // 2) - (slice_height // 2))
            end_y = min(self.screen_height, (self.screen_height // 2) + (slice_height // 2))
            color = (100, 100, 100)
            pygame.draw.line(screen, color, (ray, start_y), (ray, end_y))