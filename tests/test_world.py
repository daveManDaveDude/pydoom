import math


from game.world import World
from game.config import DEFAULT_ENEMY_HEALTH


def test_world_custom_map_grid_and_is_wall():
    grid = [[0, 1], [1, 0]]
    w = World(map_grid=grid)
    # Custom grid should be used directly
    assert w.map == grid
    assert w.width == 2 and w.height == 2
    # No powerup or sprites/enemies by default
    assert w.powerup_pos is None
    assert w.powerup_angle == 0.0
    assert w.sprites == []
    assert w.enemies == []
    # is_wall should detect bounds and wall cells
    assert not w.is_wall(0, 0)
    assert w.is_wall(1, 0)
    assert w.is_wall(-1, 0)
    assert w.is_wall(0, -1)


def test_world_default_json_loading():
    w = World()
    # Default world map should load from JSON and have valid dimensions
    assert w.map
    assert w.width > 0 and w.height > 0
    # Powerup position and angle per default.json
    assert w.powerup_pos == (3.5, 5.5)
    assert math.isclose(w.powerup_angle, math.radians(45), rel_tol=1e-9)
    # No static sprites, only enemy spawns
    assert w.sprites == []
    assert len(w.enemies) == 2
    for e in w.enemies:
        assert e.health == DEFAULT_ENEMY_HEALTH


def test_world_door_instantiation_from_map_grid():
    # Define a small map with door tiles marked as 2
    grid = [
        [0, 2, 0],
        [2, 1, 2],
        [0, 2, 0],
    ]
    w = World(map_grid=grid)
    # Expect doors at all positions where grid value == TILE_DOOR
    door_positions = {(door.x, door.y) for door in w.doors}
    expected = {(1, 0), (0, 1), (2, 1), (1, 2)}
    assert door_positions == expected
    # All doors start in 'closed' state with a timer initialized
    for door in w.doors:
        assert door.state == "closed"
        assert isinstance(door.timer, float)


def test_world_door_auto_opens_and_affects_is_wall():
    # Door should open over animation duration when player is within threshold, then be passable
    from game.config import DOOR_OPEN_DISTANCE, DOOR_ANIM_DURATION

    grid = [[0, 2, 0]]
    w = World(map_grid=grid)
    door = w.doors[0]
    # Initially the door is closed and blocks movement
    assert door.state == "closed"
    assert w.is_wall(door.x, door.y)

    # Simulate player exactly at the door center => within threshold
    class P:
        pass

    p = P()
    p.x = door.x + 0.5
    p.y = door.y + 0.5
    # Start opening (state transitions to 'opening')
    w.update_doors(p, dt=0.0)
    assert door.state == "opening"
    # Complete opening animation
    w.update_doors(p, dt=DOOR_ANIM_DURATION)
    assert door.state == "open"
    assert door.progress == 1.0
    assert not w.is_wall(door.x, door.y)


def test_world_door_auto_closes_after_delay_and_resets_timer():
    # Door should close after DOOR_CLOSE_DELAY if player leaves vicinity,
    # and should not close while player remains in threshold.
    from game.config import (
        DOOR_OPEN_DISTANCE,
        DOOR_CLOSE_DELAY,
        DOOR_ANIM_DURATION,
    )

    grid = [[0, 2, 0]]
    w = World(map_grid=grid)
    door = w.doors[0]

    class P:
        pass

    p = P()
    # Step 1: open the door fully via animation
    p.x = door.x + 0.5
    p.y = door.y + 0.5
    # initiate opening
    w.update_doors(p, dt=0.0)
    assert door.state == "opening"
    # complete opening
    w.update_doors(p, dt=DOOR_ANIM_DURATION)
    assert door.state == "open"
    # Step 2: remain near door (inside threshold) for longer than close delay
    p.x = door.x + 0.1
    p.y = door.y + 0.1
    w.update_doors(p, DOOR_CLOSE_DELAY * 2)
    assert door.state == "open"
    # Step 3: move away beyond threshold and trigger closing
    p.x = door.x + 0.5 + DOOR_OPEN_DISTANCE + 0.1
    p.y = door.y + 0.5
    w.update_doors(p, DOOR_CLOSE_DELAY)
    assert door.state == "closing"
    # Fast-forward through closing animation
    w.update_doors(p, DOOR_ANIM_DURATION)
    assert door.state == "closed"
    assert door.progress == 0.0
    assert w.is_wall(door.x, door.y)


def test_room_flood_fill_and_separation_by_doors():
    # Two empty regions separated by a closed door should yield distinct room IDs
    grid = [
        [1, 1, 1, 1, 1],
        [1, 0, 2, 0, 1],
        [1, 0, 1, 0, 1],
        [1, 1, 1, 1, 1],
    ]
    w = World(map_grid=grid)
    # Expect exactly two rooms (left of door, right of door)
    assert w.num_rooms == 2
    # Left-side room and right-side room should differ
    left_id = w.get_room_id(1.5, 1.5)
    right_id = w.get_room_id(3.5, 1.5)
    assert left_id is not None and right_id is not None
    assert left_id != right_id


def test_world_door_animation_progress_and_closing():
    # Verify door slides open over DOOR_ANIM_DURATION and then auto-closes over same duration
    from game.config import (
        DOOR_OPEN_DISTANCE,
        DOOR_CLOSE_DELAY,
        DOOR_ANIM_DURATION,
    )

    grid = [[2]]
    w = World(map_grid=grid)
    door = w.doors[0]

    class P:
        pass

    p = P()
    # Start opening when player in range
    p.x = door.x + 0.5
    p.y = door.y + 0.5
    w.update_doors(p, dt=0.0)
    assert door.state == "opening"
    # Halfway through animation
    w.update_doors(p, dt=DOOR_ANIM_DURATION / 2)
    assert 0.0 < door.progress < 1.0
    # Complete opening
    w.update_doors(p, dt=DOOR_ANIM_DURATION)
    assert door.state == "open"
    assert door.progress == 1.0

    # Move away to trigger closing after delay
    p.x = door.x + 0.5 + DOOR_OPEN_DISTANCE + 1.0
    p.y = door.y + 0.5
    w.update_doors(p, dt=DOOR_CLOSE_DELAY + 0.0)
    assert door.state == "closing"
    # Halfway through closing
    w.update_doors(p, dt=DOOR_ANIM_DURATION / 2)
    assert 0.0 < door.progress < 1.0
    # Complete closing
    w.update_doors(p, dt=DOOR_ANIM_DURATION)
    assert door.state == "closed"
    assert door.progress == 0.0


def test_get_room_id_for_open_and_closed_door():
    grid = [[0, 2, 0]]
    w = World(map_grid=grid)
    door = w.doors[0]
    # Door closed should not return a room ID for its cell
    assert w.get_room_id(1.5, 0.5) is None

    door.state = "open"
    door.progress = 1.0
    expected = w.room_map[0][2]
    assert w.get_room_id(1.5, 0.5) == expected
