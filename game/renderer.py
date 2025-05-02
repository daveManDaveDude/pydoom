import math
import pygame

class Renderer:
    """Renderer for drawing the 3D view using raycasting."""
    def __init__(self, screen_width, screen_height, fov=math.pi/3, step_size=0.005):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.fov = fov
        self.step_size = step_size
        # Number of rays equals screen width for per-column raycasting
        self.num_rays = screen_width
        # Half of the field of view
        self.half_fov = fov / 2
        # Angle between subsequent rays
        self.angle_step = fov / self.num_rays
        # Distance from player to projection plane for accurate perspective
        self.proj_plane_dist = (screen_width / 2) / math.tan(self.half_fov)
        # Precompute per-ray angle offsets and their sine/cosine for performance
        self.ray_offsets = [(-self.half_fov + i * self.angle_step) for i in range(self.num_rays)]
        self.cos_offsets = [math.cos(offset) for offset in self.ray_offsets]
        self.sin_offsets = [math.sin(offset) for offset in self.ray_offsets]

    def render(self, screen, world, player):
        """Render ceiling, floor, and walls."""
        # Draw ceiling (dark) and floor (lighter)
        screen.fill((30, 30, 30), (0, 0, self.screen_width, self.screen_height // 2))
        screen.fill((50, 50, 50), (0, self.screen_height // 2, self.screen_width, self.screen_height // 2))
        # Pre-calculate values for performance
        cos_pa = math.cos(player.angle)
        sin_pa = math.sin(player.angle)
        map_grid = world.map
        draw_line = pygame.draw.line
        shade_x = (100, 100, 100)
        shade_y = (70, 70, 70)
        # Raycasting using DDA with precomputed angle offsets
        for ray in range(self.num_rays):
            cos_off = self.cos_offsets[ray]
            sin_off = self.sin_offsets[ray]
            dir_x = cos_pa * cos_off - sin_pa * sin_off
            dir_y = sin_pa * cos_off + cos_pa * sin_off
            map_x = int(player.x)
            map_y = int(player.y)
            delta_dist_x = abs(1 / dir_x) if dir_x != 0 else float('inf')
            delta_dist_y = abs(1 / dir_y) if dir_y != 0 else float('inf')
            if dir_x < 0:
                step_x = -1
                side_dist_x = (player.x - map_x) * delta_dist_x
            else:
                step_x = 1
                side_dist_x = (map_x + 1 - player.x) * delta_dist_x
            if dir_y < 0:
                step_y = -1
                side_dist_y = (player.y - map_y) * delta_dist_y
            else:
                step_y = 1
                side_dist_y = (map_y + 1 - player.y) * delta_dist_y
            hit = False
            side = 0
            while not hit:
                if side_dist_x < side_dist_y:
                    side_dist_x += delta_dist_x
                    map_x += step_x
                    side = 0
                else:
                    side_dist_y += delta_dist_y
                    map_y += step_y
                    side = 1
                if map_grid[map_y][map_x]:
                    hit = True
            if side == 0:
                ray_dist = (map_x - player.x + (1 - step_x) / 2) / dir_x
            else:
                ray_dist = (map_y - player.y + (1 - step_y) / 2) / dir_y
            perp_distance = ray_dist * cos_off
            perp_distance = max(perp_distance, 0.0001)
            slice_height = int(self.proj_plane_dist / perp_distance)
            start_y = max(0, (self.screen_height // 2) - (slice_height // 2))
            end_y = min(self.screen_height, (self.screen_height // 2) + (slice_height // 2))
            color = shade_x if side == 0 else shade_y
            draw_line(screen, color, (ray, start_y), (ray, end_y))