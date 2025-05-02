import sys
import pygame
import math

def render_3d_view(screen, world_map, player_x, player_y, player_angle, screen_width, screen_height):
    """Render the 3D projection of walls using simple raycasting."""
    num_rays = screen_width
    fov = math.pi / 3  # 60-degree field of view
    half_fov = fov / 2
    angle_step = fov / num_rays
    max_depth = max(len(world_map), len(world_map[0]))

    for ray in range(num_rays):
        ray_angle = player_angle - half_fov + ray * angle_step
        distance = 0.0
        step_size = 0.01
        hit = False

        # Cast the ray until it hits a wall or reaches max depth
        while not hit and distance < max_depth:
            distance += step_size
            test_x = player_x + math.cos(ray_angle) * distance
            test_y = player_y + math.sin(ray_angle) * distance
            # Check bounds
            if test_x < 0 or test_x >= len(world_map[0]) or test_y < 0 or test_y >= len(world_map):
                hit = True
                break
            # Check wall collision
            if world_map[int(test_y)][int(test_x)] == 1:
                hit = True

        # Correct fish-eye distortion
        perpendicular_distance = distance * math.cos(ray_angle - player_angle)
        if perpendicular_distance == 0:
            perpendicular_distance = 0.0001

        # Calculate wall slice height
        wall_height = int(screen_height / perpendicular_distance)
        # Determine draw positions
        start_y = max(0, (screen_height // 2) - (wall_height // 2))
        end_y = min(screen_height, (screen_height // 2) + (wall_height // 2))
        color = (100, 100, 100)
        pygame.draw.line(screen, color, (ray, start_y), (ray, end_y))

def main():
    # Initialize Pygame
    pygame.init()
    # Set up display
    screen_width, screen_height = 800, 600
    screen = pygame.display.set_mode((screen_width, screen_height))
    pygame.display.set_caption("Doom-Like Prototype")
    # Clock to control frame rate
    clock = pygame.time.Clock()
    # Define the world map: 1 = wall, 0 = empty space
    world_map = [
        [1,1,1,1,1,1,1,1,1,1],
        [1,0,0,0,0,0,0,0,0,1],
        [1,0,1,0,1,1,1,0,0,1],
        [1,0,1,0,0,0,1,0,0,1],
        [1,0,1,1,1,0,1,1,0,1],
        [1,0,0,0,1,0,0,0,0,1],
        [1,0,1,0,1,1,1,0,0,1],
        [1,0,1,0,0,0,1,0,0,1],
        [1,0,0,0,0,0,0,0,0,1],
        [1,1,1,1,1,1,1,1,1,1],
    ]
    # Player start position and viewing angle (in radians)
    player_x, player_y = 3.0, 3.0
    player_angle = 0.0

    running = True
    # Movement settings
    move_speed = 3.0  # units per second
    rot_speed = 2.0   # radians per second
    while running:
        # Delta time (in seconds)
        dt = clock.tick(60) / 1000.0
        # Event handling
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
        # Key handling for movement and rotation
        keys = pygame.key.get_pressed()
        # Move forward
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            new_x = player_x + math.cos(player_angle) * move_speed * dt
            new_y = player_y + math.sin(player_angle) * move_speed * dt
            if world_map[int(new_y)][int(new_x)] == 0:
                player_x, player_y = new_x, new_y
        # Move backward
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            new_x = player_x - math.cos(player_angle) * move_speed * dt
            new_y = player_y - math.sin(player_angle) * move_speed * dt
            if world_map[int(new_y)][int(new_x)] == 0:
                player_x, player_y = new_x, new_y
        # Rotate left
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            player_angle -= rot_speed * dt
        # Rotate right
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            player_angle += rot_speed * dt

        # Clear screen: ceiling (dark) and floor (lighter)
        screen.fill((30, 30, 30), (0, 0, screen_width, screen_height // 2))
        screen.fill((50, 50, 50), (0, screen_height // 2, screen_width, screen_height // 2))
        # Render the 3D view
        render_3d_view(screen, world_map, player_x, player_y, player_angle, screen_width, screen_height)
        # Update display
        pygame.display.flip()

    # Clean up
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()