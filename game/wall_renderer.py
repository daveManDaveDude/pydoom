"""
Module defining an interface for wall rendering (casting) and a CPU-based implementation.
"""

from __future__ import annotations
import ctypes
import math
import numpy as np
import OpenGL.GL as gl  # noqa: N811
from .config import TILE_WALL, TILE_DOOR
from .gl_resources import GLResourceManager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .world import World
    from .player import Player
    from .gl_utils import ShaderProgram
    from .gl_resources import GLResourceManager


class WallRenderer:
    """Abstract base class for wall rendering implementations."""

    def render(self, world: World, player: Player) -> None:
        raise NotImplementedError(
            "WallRenderer.render must be implemented by subclasses"
        )


class CpuWallRenderer(WallRenderer):
    """CPU-based wall caster: performs DDA per column and draws textured walls."""

    def __init__(
        self,
        width: int,
        height: int,
        fov: float,
        proj_plane_dist: float,
        wall_texture: int,
        door_texture: int,
        shader_program: ShaderProgram,
        pos_attr: int,
        uv_attr: int,
        u_tex_loc: int,
        res_mgr: GLResourceManager | None = None,
    ) -> None:
        self._res = res_mgr
        self.w = width
        self.h = height
        self.fov = fov
        self.half_fov = fov / 2.0
        self.proj_plane_dist = proj_plane_dist
        self.wall_tex = wall_texture
        self.door_tex = door_texture
        self.shader = shader_program
        self.pos_attr = pos_attr
        self.uv_attr = uv_attr
        self.u_tex_loc = u_tex_loc
        if hasattr(self, "_res") and self._res:
            self.vbo = self._res.gen(
                lambda: gl.glGenBuffers(1),
                lambda obj: gl.glDeleteBuffers(1, [obj]),
            )
        else:
            self.vbo = gl.glGenBuffers(1)
        # Depth buffer for occlusion per column
        self.depth_buffer = np.zeros(self.w, dtype=np.float32)

    def render(self, world: World, player: Player) -> None:
        # Prepare separate vertex lists for wall and door slices
        wall_slices: list[np.ndarray] = []
        door_slices: list[np.ndarray] = []
        # Collect door slice segments for slide animation pivot adjustment
        door_slice_infos = {}
        cos_pa = math.cos(player.angle)
        sin_pa = math.sin(player.angle)
        for i in range(self.w):
            # Ray direction for this column
            angle_off = -self.half_fov + i * (self.fov / self.w)
            dir_x = cos_pa * math.cos(angle_off) - sin_pa * math.sin(angle_off)
            dir_y = sin_pa * math.cos(angle_off) + cos_pa * math.sin(angle_off)
            door_hits: list[tuple] = []
            # DDA initialization
            map_x = int(player.x)
            map_y = int(player.y)
            delta_x = abs(1.0 / dir_x) if dir_x != 0 else 1e9
            delta_y = abs(1.0 / dir_y) if dir_y != 0 else 1e9
            if dir_x < 0:
                step_x = -1
                side_x = (player.x - map_x) * delta_x
            else:
                step_x = 1
                side_x = (map_x + 1 - player.x) * delta_x
            if dir_y < 0:
                step_y = -1
                side_y = (player.y - map_y) * delta_y
            else:
                step_y = 1
                side_y = (map_y + 1 - player.y) * delta_y
            # Perform DDA to find wall hit
            hit = False
            side = 0
            cur_tile = None
            while not hit:
                if side_x < side_y:
                    side_x += delta_x
                    map_x += step_x
                    side = 0
                else:
                    side_y += delta_y
                    map_y += step_y
                    side = 1
                if (
                    map_x < 0
                    or map_y < 0
                    or map_x >= world.width
                    or map_y >= world.height
                ):
                    hit = True
                    cur_tile = TILE_WALL
                    break
                cell = world.map[map_y][map_x]
                if cell == TILE_WALL:
                    hit = True
                    cur_tile = TILE_WALL
                elif cell == TILE_DOOR:
                    door_obj = next(
                        (
                            d
                            for d in world.doors
                            if d.x == map_x and d.y == map_y
                        ),
                        None,
                    )
                    if door_obj is not None:
                        if door_obj.progress >= 1.0:
                            continue
                        if door_obj.progress > 0.0:
                            door_hits.append(
                                (
                                    door_obj,
                                    map_x,
                                    map_y,
                                    side,
                                    step_x,
                                    step_y,
                                    dir_x,
                                    dir_y,
                                    angle_off,
                                )
                            )
                            continue
                    hit = True
                    cur_tile = TILE_DOOR
            # Calculate perpendicular distance (avoid fish-eye)
            if side == 0:
                dist = (map_x - player.x + (1 - step_x) / 2) / dir_x
            else:
                dist = (map_y - player.y + (1 - step_y) / 2) / dir_y
            perp = max(dist * math.cos(angle_off), 1e-3)
            self.depth_buffer[i] = perp
            # Compute slice extents and texture coordinate
            slice_h = int(self.proj_plane_dist / perp)
            mid = self.h / 2 + player.pitch
            y0_ndc = ((mid - slice_h / 2) / (self.h - 1) * 2) - 1
            y1_ndc = ((mid + slice_h / 2) / (self.h - 1) * 2) - 1
            inv_w = 1.0 / (self.w - 1)
            x0_ndc = (i * inv_w) * 2 - 1
            x1_ndc = ((i + 1) * inv_w) * 2 - 1
            if side == 0:
                wallX = player.y + dist * dir_y
            else:
                wallX = player.x + dist * dir_x
            u = wallX - math.floor(wallX)
            # Two triangles per slice
            slice_uv = np.array(
                [
                    [x0_ndc, y1_ndc, u, 1.0],
                    [x0_ndc, y0_ndc, u, 0.0],
                    [x1_ndc, y0_ndc, u, 0.0],
                    [x1_ndc, y0_ndc, u, 0.0],
                    [x1_ndc, y1_ndc, u, 1.0],
                    [x0_ndc, y1_ndc, u, 1.0],
                ],
                dtype=np.float32,
            )
            # Partial open doors: record segments for slide animation
            for (
                door_obj,
                mx_d,
                my_d,
                side_d,
                step_x_d,
                step_y_d,
                dir_x_d,
                dir_y_d,
                angle_off_d,
            ) in door_hits:
                if side_d == 0:
                    dist_d = (mx_d - player.x + (1 - step_x_d) / 2) / dir_x_d
                else:
                    dist_d = (my_d - player.y + (1 - step_y_d) / 2) / dir_y_d
                perp_d = max(dist_d * math.cos(angle_off_d), 1e-3)
                slice_h_d = int(self.proj_plane_dist / perp_d)
                mid_d = self.h / 2 + player.pitch
                y0_d = ((mid_d - slice_h_d / 2) / (self.h - 1) * 2) - 1
                y1_d = ((mid_d + slice_h_d / 2) / (self.h - 1) * 2) - 1
                if side_d == 0:
                    wallX_d = player.y + dist_d * dir_y_d
                else:
                    wallX_d = player.x + dist_d * dir_x_d
                u_d = wallX_d - math.floor(wallX_d)
                slice_uv_d = np.array(
                    [
                        [x0_ndc, y1_d, u_d, 1.0],
                        [x0_ndc, y0_d, u_d, 0.0],
                        [x1_ndc, y0_d, u_d, 0.0],
                        [x1_ndc, y0_d, u_d, 0.0],
                        [x1_ndc, y1_d, u_d, 1.0],
                        [x0_ndc, y1_d, u_d, 1.0],
                    ],
                    dtype=np.float32,
                )
                door_slice_infos.setdefault(door_obj, []).append(slice_uv_d)

            if cur_tile == TILE_WALL:
                wall_slices.append(slice_uv)
            elif cur_tile == TILE_DOOR:
                door_obj = next(
                    (d for d in world.doors if d.x == map_x and d.y == map_y),
                    None,
                )
                if door_obj is not None and door_obj.progress > 0.0:
                    door_slice_infos.setdefault(door_obj, []).append(slice_uv)
                else:
                    door_slices.append(slice_uv)

        # Apply slide animation pivot adjustments for door slices
        for door_obj, segments in door_slice_infos.items():
            if not segments:
                continue
            if door_obj.slide_axis == "x":
                # Horizontal slide: pivot at block side of door
                xs0 = [seg[:, 0].min() for seg in segments]
                xs1 = [seg[:, 0].max() for seg in segments]
                pivot = min(xs0) if door_obj.slide_dir == 1 else max(xs1)
                for seg in segments:
                    seg[:, 0] = pivot + (seg[:, 0] - pivot) * (
                        1.0 - door_obj.progress
                    )
            else:
                # Vertical slide: pivot at block side of door
                ys0 = [seg[:, 1].min() for seg in segments]
                ys1 = [seg[:, 1].max() for seg in segments]
                pivot = max(ys1) if door_obj.slide_dir == 1 else min(ys0)
                for seg in segments:
                    seg[:, 1] = pivot + (seg[:, 1] - pivot) * (
                        1.0 - door_obj.progress
                    )
            door_slices.extend(segments)

        def draw_slices(slices_list: list[np.ndarray], texture: int) -> None:
            if not slices_list:
                return
            verts_uv = np.vstack(slices_list)
            self.shader.use()
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)
            gl.glBufferData(
                gl.GL_ARRAY_BUFFER,
                verts_uv.nbytes,
                verts_uv,
                gl.GL_DYNAMIC_DRAW,
            )
            stride = verts_uv.strides[0]
            gl.glEnableVertexAttribArray(self.pos_attr)
            gl.glVertexAttribPointer(
                self.pos_attr,
                2,
                gl.GL_FLOAT,
                gl.GL_FALSE,
                stride,
                ctypes.c_void_p(0),
            )
            gl.glEnableVertexAttribArray(self.uv_attr)
            gl.glVertexAttribPointer(
                self.uv_attr,
                2,
                gl.GL_FLOAT,
                gl.GL_FALSE,
                stride,
                ctypes.c_void_p(8),
            )
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
            gl.glUniform1i(self.u_tex_loc, 0)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, len(verts_uv))
            gl.glDisableVertexAttribArray(self.pos_attr)
            gl.glDisableVertexAttribArray(self.uv_attr)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
            self.shader.stop()

        # Draw walls first, then doors
        draw_slices(wall_slices, self.wall_tex)
        draw_slices(door_slices, self.door_tex)
