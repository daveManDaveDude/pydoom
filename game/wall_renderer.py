"""
Module defining an interface for wall rendering (casting) and a CPU-based implementation.
"""
import ctypes
import math
import numpy as np
from OpenGL.GL import *

class WallRenderer:
    """Abstract base class for wall rendering implementations."""
    def render(self, world, player):
        raise NotImplementedError("WallRenderer.render must be implemented by subclasses")

class CpuWallRenderer(WallRenderer):
    """CPU-based wall caster: performs DDA per column and draws textured walls."""
    def __init__(self, width, height, fov, proj_plane_dist,
                 wall_texture, shader_program,
                 pos_attr, uv_attr, u_tex_loc):
        self.w = width
        self.h = height
        self.fov = fov
        self.half_fov = fov / 2.0
        self.proj_plane_dist = proj_plane_dist
        self.wall_tex = wall_texture
        self.shader = shader_program
        self.pos_attr = pos_attr
        self.uv_attr = uv_attr
        self.u_tex_loc = u_tex_loc
        # VBO for wall vertices + UVs
        self.vbo = glGenBuffers(1)

    def render(self, world, player):
        # Prepare vertex buffer: each wall slice is two triangles (6 verts) with (x,y,u,v)
        verts_uv = np.zeros((self.w * 6, 4), dtype=np.float32)
        idx = 0
        cos_pa = math.cos(player.angle)
        sin_pa = math.sin(player.angle)
        for i in range(self.w):
            # Ray direction for this column
            angle_off = -self.half_fov + i * (self.fov / self.w)
            dir_x = cos_pa * math.cos(angle_off) - sin_pa * math.sin(angle_off)
            dir_y = sin_pa * math.cos(angle_off) + cos_pa * math.sin(angle_off)
            # DDA initialization
            map_x = int(player.x)
            map_y = int(player.y)
            delta_x = abs(1.0 / dir_x) if dir_x != 0 else 1e9
            delta_y = abs(1.0 / dir_y) if dir_y != 0 else 1e9
            if dir_x < 0:
                step_x = -1; side_x = (player.x - map_x) * delta_x
            else:
                step_x = 1; side_x = (map_x + 1 - player.x) * delta_x
            if dir_y < 0:
                step_y = -1; side_y = (player.y - map_y) * delta_y
            else:
                step_y = 1; side_y = (map_y + 1 - player.y) * delta_y
            # Perform DDA to find wall hit
            hit = False; side = 0
            while not hit:
                if side_x < side_y:
                    side_x += delta_x; map_x += step_x; side = 0
                else:
                    side_y += delta_y; map_y += step_y; side = 1
                if world.map[map_y][map_x]:
                    hit = True
            # Calculate perpendicular distance
            # Distance from player to wall along the ray (before fisheye correction)
            if side == 0:
                dist = (map_x - player.x + (1 - step_x) / 2) / dir_x
            else:
                dist = (map_y - player.y + (1 - step_y) / 2) / dir_y
            # Correct distance to avoid fish-eye effect
            perp = dist * math.cos(angle_off)
            perp = max(perp, 1e-3)
            # Wall slice height in pixels
            slice_h = int(self.proj_plane_dist / perp)
            # Vertical slice extents (centered and taking pitch into account)
            mid = self.h / 2 + player.pitch
            y0 = mid - slice_h / 2.0
            y1 = mid + slice_h / 2.0
            # Normalize to NDC (-1..1)
            inv_h = 1.0 / (self.h - 1.0)
            y0_ndc = (y0 * inv_h) * 2.0 - 1.0
            y1_ndc = (y1 * inv_h) * 2.0 - 1.0
            inv_w = 1.0 / (self.w - 1.0)
            x0_ndc = (i * inv_w) * 2.0 - 1.0
            x1_ndc = ((i + 1) * inv_w) * 2.0 - 1.0
            # Texture coordinate (u) based on wall hit position
            # Calculate exact hit position on the wall for texture coordinate using raw distance
            if side == 0:
                wallX = player.y + dist * dir_y
            else:
                wallX = player.x + dist * dir_x
            u = wallX - math.floor(wallX)
            # Two triangles per slice
            verts_uv[idx] = [x0_ndc, y1_ndc, u, 1.0]; idx += 1
            verts_uv[idx] = [x0_ndc, y0_ndc, u, 0.0]; idx += 1
            verts_uv[idx] = [x1_ndc, y0_ndc, u, 0.0]; idx += 1
            verts_uv[idx] = [x1_ndc, y0_ndc, u, 0.0]; idx += 1
            verts_uv[idx] = [x1_ndc, y1_ndc, u, 1.0]; idx += 1
            verts_uv[idx] = [x0_ndc, y1_ndc, u, 1.0]; idx += 1
        # Upload vertex data and draw
        self.shader.use()
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, verts_uv.nbytes, verts_uv, GL_DYNAMIC_DRAW)
        stride = verts_uv.strides[0]
        glEnableVertexAttribArray(self.pos_attr)
        glVertexAttribPointer(self.pos_attr, 2, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(0))
        glEnableVertexAttribArray(self.uv_attr)
        glVertexAttribPointer(self.uv_attr, 2, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(8))
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.wall_tex)
        glUniform1i(self.u_tex_loc, 0)
        glDrawArrays(GL_TRIANGLES, 0, self.w * 6)
        glDisableVertexAttribArray(self.pos_attr)
        glDisableVertexAttribArray(self.uv_attr)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindTexture(GL_TEXTURE_2D, 0)
        self.shader.stop()