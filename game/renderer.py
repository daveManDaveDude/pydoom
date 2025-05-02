import math
import pygame

class Renderer:
    """Renderer for drawing the 3D view using raycasting."""
    def __init__(self, screen_width, screen_height, fov=math.pi/3, step_size=0.005):
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
        # Raycasting using DDA algorithm for better performance and smooth motion
        for ray in range(self.num_rays):
            # Calculate ray angle for this column
            ray_angle = player.angle - self.half_fov + ray * self.angle_step
            # Ray direction vector
            dir_x = math.cos(ray_angle)
            dir_y = math.sin(ray_angle)

            # Map position (grid square) of the player
            map_x = int(player.x)
            map_y = int(player.y)

            # Length of ray from one x or y-side to next x or y-side
            delta_dist_x = abs(1 / dir_x) if dir_x != 0 else float('inf')
            delta_dist_y = abs(1 / dir_y) if dir_y != 0 else float('inf')

            # Calculate step direction and initial side distances
            if dir_x < 0:
                step_x = -1
                side_dist_x = (player.x - map_x) * delta_dist_x
            else:
                step_x = 1
                side_dist_x = (map_x + 1.0 - player.x) * delta_dist_x
            if dir_y < 0:
                step_y = -1
                side_dist_y = (player.y - map_y) * delta_dist_y
            else:
                step_y = 1
                side_dist_y = (map_y + 1.0 - player.y) * delta_dist_y

            # Perform DDA to find the wall hit
            hit = False
            side = 0  # 0 for x-side hit, 1 for y-side hit
            while not hit:
                # Jump to next map square in x or y direction
                if side_dist_x < side_dist_y:
                    side_dist_x += delta_dist_x
                    map_x += step_x
                    side = 0
                else:
                    side_dist_y += delta_dist_y
                    map_y += step_y
                    side = 1
                # Check if ray has hit a wall
                if world.is_wall(map_x, map_y):
                    hit = True

            # Calculate perpendicular distance to the wall to avoid fish-eye
            if side == 0:
                perp_distance = (map_x - player.x + (1 - step_x) / 2) / dir_x
            else:
                perp_distance = (map_y - player.y + (1 - step_y) / 2) / dir_y
            # Prevent division by zero
            if perp_distance == 0:
                perp_distance = 0.0001

            # Calculate height of the wall slice to draw
            slice_height = int(self.screen_height / perp_distance)
            start_y = max(0, (self.screen_height // 2) - (slice_height // 2))
            end_y = min(self.screen_height, (self.screen_height // 2) + (slice_height // 2))

            # Shade walls differently for x/y sides for a simple lighting effect
            shade = 100 if side == 0 else 70
            color = (shade, shade, shade)
            pygame.draw.line(screen, color, (ray, start_y), (ray, end_y))