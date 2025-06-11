# After every patch:
        #   Run: pytest -q --disable-warnings --maxfail=1
	#   Run: black . -l 80

Below is a focused review of how the CPU renderer currently computes and draws the “sliding” (i.e. “shrinking”) door slices, why it
 ends up with a constant slice‐height during the animation, and several possible ways to restore correct perspective‑varying
top/bottom edges as the door moves.

----------------------------------------------------------------------------------------------------------------------------------

## 1. What the code is doing today

In CpuWallRenderer.render(), after doing the DDA raycast, the renderer separately records two sets of geometry:

    1. **wall_slices** (full‑depth wall columns), and
    2. **door_slices** (fully closed doors or fully open doors treated like walls), plus
    3. **door_slice_infos** (partial‑open doors, whose slices we will translate/“shrink” into the jamb).

The key bits are these two blocks:

    # ——————————————————————————————
    # (A) for each column i, compute the normal “slice_uv” for walls
    # ——————————————————————————————
    # Calculate perpendicular distance (avoid fish‑eye)
    if side == 0:
        dist = (map_x - player.x + (1 - step_x) / 2) / dir_x
    else:
        dist = (map_y - player.y + (1 - step_y) / 2) / dir_y
    perp = max(dist * math.cos(angle_off), 1e-3)

    # Compute slice extents in NDC and texture U coordinate
    slice_h = int(self.proj_plane_dist / perp)
    mid = self.h / 2 + player.pitch
    y0_ndc = ((mid - slice_h / 2) / (self.h - 1) * 2) - 1
    y1_ndc = ((mid + slice_h / 2) / (self.h - 1) * 2) - 1
    x0_ndc = (i * inv_w) * 2 - 1
    x1_ndc = ((i + 1) * inv_w) * 2 - 1
    …
    slice_uv = np.array([
        [x0_ndc, y1_ndc, u, 1.0],
        [x0_ndc, y0_ndc, u, 0.0],
        … ], dtype=np.float32)
    # ——————————————————————————————
    # (B) for any door partial‑hit in door_hits, compute slice_uv_d
    # ——————————————————————————————
    for (door_obj, mx_d, my_d, side_d, step_x_d, step_y_d,
         dir_x_d, dir_y_d, angle_off_d) in door_hits:
        if side_d == 0:
            dist_d = (mx_d - player.x + (1 - step_x_d) / 2) / dir_x_d
        else:
            dist_d = (my_d - player.y + (1 - step_y_d) / 2) / dir_y_d
        perp_d = max(dist_d * math.cos(angle_off_d), 1e-3)

        slice_h_d = int(self.proj_plane_dist / perp_d)
        mid_d    = self.h / 2 + player.pitch
        y0_d     = ((mid_d - slice_h_d / 2) / (self.h - 1) * 2) - 1
        y1_d     = ((mid_d + slice_h_d / 2) / (self.h - 1) * 2) - 1

        u_d = (…)
        slice_uv_d = np.array([
            [x0_ndc, y1_d, u_d, 1.0],
            [x0_ndc, y0_d, u_d, 0.0],
            … ], dtype=np.float32)

        door_slice_infos.setdefault(door_obj, []).append(slice_uv_d)

game/wall_renderer.py (/Users/davidmcgrath/vibe/pydoom/game/wall_renderer.py)game/wall_renderer.py 
(/Users/davidmcgrath/vibe/pydoom/game/wall_renderer.py)

Finally (still in the same function), all of those slice_uv_d segments get translated horizontally in screen‑space to simulate the
door sliding:

    # Apply sliding-door translation & clamping: translate door slices along screen X into the jamb
    for door_obj, segments in door_slice_infos.items():
        …
        pivot  = …   # hinge‐side X in NDC
        far_x  = …   # far‐edge X in NDC
        slide_x = (far_x - pivot) * door_obj.progress
        for seg in segments:
            seg[:, 0] += slide_x
            seg[:, 0] = np.clip(seg[:, 0], min(pivot, far_x), max(pivot, far_x))

        door_slices.extend(segments)

game/wall_renderer.py (/Users/davidmcgrath/vibe/pydoom/game/wall_renderer.py)

—and then those door_slices are drawn exactly like the walls.

----------------------------------------------------------------------------------------------------------------------------------

### Why does the door’s height stay constant?

Because we calculate y0_d/y1_d once using the door’s fixed grid‐cell coordinates (i.e. at map_x,my_d) and never reproject those NDC
 Y values when we slide the door.  Sliding is done purely in screen‐space X, so the top & bottom of the door block remain at the
same Y each frame—regardless of how “deep” the door face is sliding into the jamb in world‑space.

In other words, the horizontal clamp/translation simulates the width change, but the vertical projection is frozen to the door’s
original position in the grid cell, so you get a door block of constant height (flat top/bottom edges) instead of a shape that
slants or shrinks correctly in perspective as it moves.

----------------------------------------------------------------------------------------------------------------------------------

## 2. “Slide axis” is chosen once when the world loads

The code determines which side the door will slide into (and thus its hinge side) based on the empty neighbor tile:

    # Determine sliding orientation for each door
    for door in self.doors:
        if x + 1 < self.width and self.map[y][x + 1] == TILE_EMPTY:
            door.slide_axis = "x"; door.slide_dir = 1
        elif x - 1 >= 0 and self.map[y][x - 1] == TILE_EMPTY:
            door.slide_axis = "x"; door.slide_dir = -1
        elif y + 1 < self.height and self.map[y + 1][x] == TILE_EMPTY:
            door.slide_axis = "y"; door.slide_dir = 1
        else:
            door.slide_axis = "y"; door.slide_dir = -1

game/world.py (/Users/davidmcgrath/vibe/pydoom/game/world.py)

Because slide_axis/slide_dir are known, we can use them when computing the actual door‐face distance—allowing us to dynamically
adjust the projected height.

----------------------------------------------------------------------------------------------------------------------------------

## 3. Possible approaches to restore correct perspective

Below are four alternative ways to make the door’s top and bottom edges obey the same perspective projection as neighboring wall
slices:

----------------------------------------------------------------------------------------------------------------------------------

### Option 1: Recompute the door‐face distance using its fractional world‐position

In the existing door_hits loop, instead of assuming the door‐face plane always lies at the integer cell coordinate, shift that
plane by door.progress along the chosen axis before computing dist_d.  For example (pseudo‑diff):

    --- a/game/wall_renderer.py
    +++ b/game/wall_renderer.py
    @@ for (door_obj, mx_d, my_d, side_d, step_x_d, step_y_d,
    -    if side_d == 0:
    -        dist_d = (mx_d - player.x + (1 - step_x_d) / 2) / dir_x_d
    -    else:
    -        dist_d = (my_d - player.y + (1 - step_y_d) / 2) / dir_y_d
    +    # incorporate fractional slide offset into world‐space door position
    +    # so the door-face plane moves into the jamb in world‐space,
    +    # yielding a changing distance for correct perspective height.
    +    if door_obj.slide_axis == "x":
    +        door_world_x = mx_d + (1 - step_x_d) / 2 + door_obj.slide_dir * door_obj.progress
    +        door_world_y = my_d + 0.5
    +        dist_d = (door_world_x - player.x) / dir_x_d
    +    else:
    +        door_world_x = mx_d + 0.5
    +        door_world_y = my_d + (1 - step_y_d) / 2 + door_obj.slide_dir * door_obj.progress
    +        dist_d = (door_world_y - player.y) / dir_y_d
         perp_d = max(dist_d * math.cos(angle_off_d), 1e-3)

game/wall_renderer.py (/Users/davidmcgrath/vibe/pydoom/game/wall_renderer.py)

By doing this, when door.progress changes, dist_d (and thus slice_h_d, y0_d, y1_d) are recomputed each frame with the door’s face
at its new world‑space position.  The door’s height will automatically vary exactly the same way adjacent walls do.

----------------------------------------------------------------------------------------------------------------------------------

### Option 2: Warp the top/bottom edge in screen‑space

If you prefer to keep the existing DDA‐based slice_uv_d→seg[:,0] code, you can still warp the Y coordinates in screen‑space in
proportion to the slide.  Rough outline:

    1. Gather the original top/bottom Y values of the hinge edge and the far edge (you already compute `ys0`, `ys1` for the debug
edge).
    2. As the door slides, linearly interpolate the Y bounds for each vertical slice between the hinge Y and far‐edge Y based on
`door.progress`.
    3. Overwrite `seg[:,1]` accordingly before drawing.

This avoids touching the distance math, but effectively produces the same trapezoidal distortion of top/bottom edges.

----------------------------------------------------------------------------------------------------------------------------------

### Option 3: Draw each door face as a single trapezoid polygon

Rather than re‑slicing the door every column, you know the four “corner” points of the door face in NDC:

    * hinge‑edge top (pivot, y_top_pivot)
    * hinge‑edge bottom (pivot, y_bottom_pivot)
    * moving‑edge top (moving_x, y_top_far)
    * moving‑edge bottom (moving_x, y_bottom_far)

You could simply issue a glDrawArrays(GL_TRIANGLES) for two triangles covering that trapezoid—using those four 2D NDC points and
the proper U coordinates (0→1 or whatever your texture coordinates).  That is arguably simpler geometry for a single door face and
will look perfectly perspective‑correct.

----------------------------------------------------------------------------------------------------------------------------------

### Option 4: Use a true 3D door‐polygon in your engine

If you ever extend to a fully GPU‐driven renderer (model/view/projection matrices), you could treat each door as a 3D quad that you
 translate in world‑space (along X or Y) by door.progress.  The GPU will then handle the perspective for you.  At that point the
door sits at fractional world‐space coordinates and naturally projects with correct top/bottom slant.

----------------------------------------------------------------------------------------------------------------------------------

