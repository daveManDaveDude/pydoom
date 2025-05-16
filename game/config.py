import math

# Screen settings
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60

# Player settings
# Movement speed in map units per second (increase for quicker movement)
MOVE_SPEED = 3.0
# Rotation speed in radians per second
ROT_SPEED = 2.0
# Enemy settings
# Movement speed in map units per second for AI-controlled enemies
ENEMY_SPEED = 1.5
# Collision detection: if enemy is this close to player, trigger respawn (map units)
# Collision detection: if enemy is this close to player, trigger respawn (map units)
COLLISION_RADIUS = 0.5
# Default enemy hit points (number of bullet hits to kill)
DEFAULT_ENEMY_HEALTH = 5

# Raycasting settings
# Field of view angle (in radians)
FOV = math.pi / 3
# Step size for raycasting (kept for compatibility)
STEP_SIZE = 0.005

# Colors
CEILING_COLOR = (30, 30, 30)
FLOOR_COLOR = (50, 50, 50)
WALL_SHADE_X = (100, 100, 100)
WALL_SHADE_Y = (70, 70, 70)
# Mouse settings
# Sensitivity in radians per pixel of mouse movement
MOUSE_SENSITIVITY = 0.003
# Vertical mouse sensitivity: pixels of horizon shift per pixel of mouse movement
MOUSE_SENSITIVITY_Y = 1.0
# Maximum vertical look offset (horizon shift) in pixels: allow up to half screen (~±25°)
MAX_PITCH = SCREEN_HEIGHT // 2
# Texture settings
# Filename of the floor texture (located in game/textures directory)
FLOOR_TEXTURE_FILE = 'cracked_stone_floor.png'
# World file: JSON definition of the map layout
WORLD_FILE = 'worlds/default.json'
# Filename of the ceiling texture (located in game/textures directory)
CEILING_TEXTURE_FILE = 'stained_ceiling_tiles.png'
# Filename of the wall texture (located in game/textures directory)
WALL_TEXTURE_FILE = 'brick_wall.png'
# Filename of the sprite to render (located in game/textures directory)
SPRITE_TEXTURE_FILE = 'health-power-up.png'
# Rotation speed for powerup sprite (radians per second)
SPRITE_ROT_SPEED = math.pi / 2.0

# Projectile settings
# Speed of bullets (map units per second)
BULLET_SPEED = 10.0
# Time in seconds before a bullet expires
BULLET_LIFESPAN = 2.0
# Collision radius for bullet-enemy hits (map units)
# Collision radius for bullet-enemy hits (map units)
BULLET_HIT_RADIUS = 0.5
# Time delay before enemy respawn after death (seconds)
# Time delay before enemy respawn after death (seconds)
ENEMY_RESPAWN_DELAY = 2.0
# Delay before enemy switches to direct pursuit after gaining line-of-sight (seconds)
ENEMY_LOS_DIRECT_DELAY = 0.5
# Duration for hit marker flash (milliseconds)
HIT_FLASH_DURATION_MS = 200