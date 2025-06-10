"""
OpenGL-based renderer: uses GPU shaders for floor, ceiling, walls, and UI overlay.
"""

from __future__ import annotations
import os
import ctypes
import pygame
import math
import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .world import World
    from .player import Player

# Animation frame duration in milliseconds (ping-pong cycle)
# Increased to slow the animation slightly
_ANIM_FRAME_MS = 300
try:
    import OpenGL.GL as gl  # noqa: N811
except ImportError:
    raise ImportError(
        "PyOpenGL is required to run this renderer. "
        "Please install via: pip install PyOpenGL PyOpenGL_accelerate"
    )
from .gl_resources import GLResourceManager
from .config import (
    CEILING_COLOR,
    WALL_SHADE_X,
    WALL_SHADE_Y,
    FLOOR_TEXTURE_FILE,
    CEILING_TEXTURE_FILE,
    WALL_TEXTURE_FILE,
    DOOR_TEXTURE_FILE,
    SPRITE_TEXTURE_FILE,
)
from .gl_utils import (
    ShaderProgram,
    load_texture,
    setup_opengl,
    create_texture_from_surface,
)

# Local logger for shader helpers
logger = logging.getLogger(__name__)
from .wall_renderer import CpuWallRenderer


def _delete_buffer(obj_id: int) -> None:
    """Deletes a single GL buffer."""
    gl.glDeleteBuffers(1, [obj_id])


def _delete_texture(obj_id: int) -> None:
    """Deletes a single GL texture."""
    gl.glDeleteTextures(1, [obj_id])


def compile_shader(source: str, shader_type: int) -> int:
    """
    Compile a GLSL shader (vertex or fragment) from the given source string.
    Raises RuntimeError if compilation fails.
    """
    shader = gl.glCreateShader(shader_type)
    gl.glShaderSource(shader, source)
    gl.glCompileShader(shader)
    status = gl.glGetShaderiv(shader, gl.GL_COMPILE_STATUS)
    if not status:
        log = gl.glGetShaderInfoLog(shader).decode()
        logger.error("Shader compile failed: %s", log)
        raise RuntimeError(f"Shader compile error: {log}")
    return shader


def link_program(vs: int, fs: int) -> int:
    """
    Link compiled vertex and fragment shaders into a GL program.
    Raises RuntimeError if linking fails.
    """
    prog = gl.glCreateProgram()
    gl.glAttachShader(prog, vs)
    gl.glAttachShader(prog, fs)
    gl.glLinkProgram(prog)
    status = gl.glGetProgramiv(prog, gl.GL_LINK_STATUS)
    if not status:
        log = gl.glGetProgramInfoLog(prog).decode()
        logger.error("Program link failed: %s", log)
        raise RuntimeError(f"Shader link error: {log}")
    return prog


class Renderer:
    """OpenGL-based renderer: GPU floor/ceiling, CPU walls via GL_LINES."""

    def __init__(
        self,
        screen_width: int,
        screen_height: int,
        fov: float = math.pi / 3,
        step_size: float = 0.005,
        world: Optional[World] = None,
    ) -> None:
        self.w = screen_width
        self.h = screen_height
        self.world = world
        self.fov = fov
        self.half_fov = fov / 2.0
        # GL resource manager to track and clean up GL objects
        self._res = GLResourceManager()
        # Hit flash timer (milliseconds timestamp until which to flash)
        self.hit_flash_until = 0
        # Projection plane distance for wall heights
        self.proj_plane_dist = (self.w / 2.0) / __import__("math").tan(
            self.half_fov
        )
        # Basic OpenGL state
        setup_opengl(self.w, self.h)
        # Floor & ceiling shader
        shader_dir = os.path.join(os.path.dirname(__file__), "shaders")
        floor_vs = os.path.join(shader_dir, "floor.vert")
        floor_fs = os.path.join(shader_dir, "floor.frag")
        self.floor_shader = ShaderProgram(
            vertex_path=floor_vs, fragment_path=floor_fs
        )
        # Uniform/attribute locations
        self.aPosLoc = self.floor_shader.get_attrib("aPos")
        self.uResLoc = self.floor_shader.get_uniform("uRes")
        self.uPosLoc = self.floor_shader.get_uniform("uPos")
        self.uAngLoc = self.floor_shader.get_uniform("uAng")
        self.uHalfFovLoc = self.floor_shader.get_uniform("uHalfFov")
        self.uPitchLoc = self.floor_shader.get_uniform("uPitch")
        self.uFloorTexLoc = self.floor_shader.get_uniform("uFloorTex")
        self.uCeilTexLoc = self.floor_shader.get_uniform("uCeilTex")
        # Full-screen quad VBO
        quad = __import__("numpy").array(
            [-1.0, -1.0, 1.0, -1.0, -1.0, 1.0, 1.0, 1.0],
            dtype=__import__("numpy").float32,
        )
        self.quad_vbo = self._res.gen(
            lambda: gl.glGenBuffers(1), _delete_buffer
        )
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.quad_vbo)
        gl.glBufferData(
            gl.GL_ARRAY_BUFFER, quad.nbytes, quad, gl.GL_STATIC_DRAW
        )
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
        # Simple color wall shader (currently unused)
        wall_vs_src = """
#version 120
attribute vec3 aPos;
attribute vec3 aColor;
varying vec3 vColor;
void main() {
    gl_Position = vec4(aPos, 1.0);
    vColor = aColor;
}
"""
        wall_fs_src = """
#version 120
varying vec3 vColor;
void main() {
    gl_FragColor = vec4(vColor, 1.0);
}
"""
        self.wall_color_shader = ShaderProgram(
            vertex_source=wall_vs_src, fragment_source=wall_fs_src
        )
        self.posAttr = self.wall_color_shader.get_attrib("aPos")
        self.colAttr = self.wall_color_shader.get_attrib("aColor")
        self.wall_vbo = self._res.gen(
            lambda: gl.glGenBuffers(1), _delete_buffer
        )
        self.color_vbo = self._res.gen(
            lambda: gl.glGenBuffers(1), _delete_buffer
        )
        # Load floor and ceiling textures
        textures_dir = os.path.join(os.path.dirname(__file__), "textures")
        self.floor_tex = load_texture(
            os.path.join(textures_dir, FLOOR_TEXTURE_FILE)
        )
        self._res._objs[_delete_texture].append(self.floor_tex)
        self.ceil_tex = load_texture(
            os.path.join(textures_dir, CEILING_TEXTURE_FILE)
        )
        self._res._objs[_delete_texture].append(self.ceil_tex)
        # Textured wall shader
        wall_vs = os.path.join(shader_dir, "wall_textured.vert")
        wall_fs = os.path.join(shader_dir, "wall_textured.frag")
        self.wall_tex_shader = ShaderProgram(
            vertex_path=wall_vs, fragment_path=wall_fs
        )
        self.wall_pos2Attr = self.wall_tex_shader.get_attrib("aPos")
        self.wall_uvAttr = self.wall_tex_shader.get_attrib("aUV")
        self.uWallTexLoc = self.wall_tex_shader.get_uniform("uWallTex")
        self.wall_tex_vbo = self._res.gen(
            lambda: gl.glGenBuffers(1), _delete_buffer
        )
        self.wall_tex = load_texture(
            os.path.join(textures_dir, WALL_TEXTURE_FILE)
        )
        self._res._objs[_delete_texture].append(self.wall_tex)
        self.door_tex = load_texture(
            os.path.join(textures_dir, DOOR_TEXTURE_FILE)
        )
        self._res._objs[_delete_texture].append(self.door_tex)
        self.wall_renderer = CpuWallRenderer(
            self.w,
            self.h,
            self.fov,
            self.proj_plane_dist,
            self.wall_tex,
            self.door_tex,
            self.wall_tex_shader,
            self.wall_pos2Attr,
            self.wall_uvAttr,
            self.uWallTexLoc,
            self._res,
        )
        # Load sprite texture for demo sprite rendering
        sprite_path = os.path.join(textures_dir, SPRITE_TEXTURE_FILE)
        spr_surf = pygame.image.load(sprite_path).convert_alpha()
        self.sprite_tex = load_texture(
            sprite_path, wrap_s=gl.GL_CLAMP_TO_EDGE, wrap_t=gl.GL_CLAMP_TO_EDGE
        )
        self._res._objs[_delete_texture].append(self.sprite_tex)
        self.sprite_width, self.sprite_height = spr_surf.get_size()
        self.sprite_vbo = self._res.gen(
            lambda: gl.glGenBuffers(1), _delete_buffer
        )
        # Prepare mapping of sprite textures (demo and any additional sprites)
        # Prepare mapping of sprite textures for all sprites (animation frames)
        self.sprite_texs = {}
        if self.world and hasattr(self.world, "sprites"):
            for sp in self.world.sprites:
                for tex_name in sp.get("textures", []):
                    if tex_name and tex_name not in self.sprite_texs:
                        sp_path = os.path.join(textures_dir, tex_name)
                        sp_surf = pygame.image.load(sp_path).convert_alpha()
                        tex_id = load_texture(
                            sp_path,
                            wrap_s=gl.GL_CLAMP_TO_EDGE,
                            wrap_t=gl.GL_CLAMP_TO_EDGE,
                        )
                        self._res._objs[_delete_texture].append(tex_id)
                        w, h = sp_surf.get_size()
                        self.sprite_texs[tex_name] = (tex_id, w, h)
        # Load enemy textures for billboard rendering
        if self.world and hasattr(self.world, "enemies"):
            for enemy in self.world.enemies:
                for tex_name in enemy.textures or []:
                    if tex_name and tex_name not in self.sprite_texs:
                        sp_path = os.path.join(textures_dir, tex_name)
                        # Load and register texture
                        sp_surf = pygame.image.load(sp_path).convert_alpha()
                        tex_id = load_texture(
                            sp_path,
                            wrap_s=gl.GL_CLAMP_TO_EDGE,
                            wrap_t=gl.GL_CLAMP_TO_EDGE,
                        )
                        self._res._objs[_delete_texture].append(tex_id)
                        w, h = sp_surf.get_size()
                        self.sprite_texs[tex_name] = (tex_id, w, h)
        # Prepare UI overlay text (Press X to quit)
        self.ui_font = pygame.font.SysFont(None, 24)
        ui_surf = self.ui_font.render("Press X to eXit", True, (255, 255, 255))
        self.ui_text_width, self.ui_text_height = ui_surf.get_size()
        # Create UI texture
        self.ui_tex = create_texture_from_surface(ui_surf)
        # Track UI texture for cleanup
        self._res._objs[_delete_texture].append(self.ui_tex)
        # VBO for UI quad
        self.ui_vbo = self._res.gen(lambda: gl.glGenBuffers(1), _delete_buffer)

    def render(
        self, screen: pygame.Surface, world: World, player: Player
    ) -> None:
        # Clear color and depth buffers and disable depth testing for full-screen draws
        # Clear buffers
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        gl.glDisable(gl.GL_DEPTH_TEST)
        # Floor & ceiling pass
        self.floor_shader.use()
        gl.glUniform2f(self.uResLoc, float(self.w), float(self.h))
        gl.glUniform2f(self.uPosLoc, player.x, player.y)
        gl.glUniform1f(self.uAngLoc, player.angle)
        gl.glUniform1f(self.uHalfFovLoc, self.half_fov)
        gl.glUniform1f(self.uPitchLoc, player.pitch)
        # Bind floor texture
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.floor_tex)
        gl.glUniform1i(self.uFloorTexLoc, 0)
        # Bind ceiling texture
        gl.glActiveTexture(gl.GL_TEXTURE1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.ceil_tex)
        gl.glUniform1i(self.uCeilTexLoc, 1)
        # Draw full-screen quad
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.quad_vbo)
        gl.glEnableVertexAttribArray(self.aPosLoc)
        gl.glVertexAttribPointer(
            self.aPosLoc, 2, gl.GL_FLOAT, gl.GL_FALSE, 0, ctypes.c_void_p(0)
        )
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
        gl.glDisableVertexAttribArray(self.aPosLoc)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
        self.floor_shader.stop()
        # Walls pass
        gl.glDisable(gl.GL_BLEND)
        self.wall_renderer.render(world, player)
        # Sprite pass: render planar sprite at world-defined orientation
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        # Sprite world size: height and width preserving texture aspect
        world_h = 0.25
        aspect = float(self.sprite_width) / float(self.sprite_height)
        world_w = world_h * aspect
        half_w = world_w * 0.5
        inv_w = 1.0 / (self.w - 1.0)
        inv_h = 1.0 / (self.h - 1.0)
        mid_y = self.h * 0.5 + player.pitch
        depth = self.wall_renderer.depth_buffer
        if world.powerup_pos:
            pxw, pyw = world.powerup_pos
            ang_p = world.powerup_angle
            # Plane normal and tangent
            n_x = math.cos(ang_p)
            n_y = math.sin(ang_p)
            t_x = -n_y
            t_y = n_x
            px0, py0 = player.x, player.y
            cols = []
            for col in range(self.w):
                ang_off = -self.half_fov + col * (self.fov / self.w)
                r_dx = math.cos(player.angle) * math.cos(ang_off) - math.sin(
                    player.angle
                ) * math.sin(ang_off)
                r_dy = math.sin(player.angle) * math.cos(ang_off) + math.cos(
                    player.angle
                ) * math.sin(ang_off)
                denom = n_x * r_dx + n_y * r_dy
                if abs(denom) < 1e-6:
                    continue
                num = n_x * (pxw - px0) + n_y * (pyw - py0)
                t_dist = num / denom
                if t_dist <= 0:
                    continue
                perp = t_dist * math.cos(ang_off)
                if perp <= 0 or perp >= depth[col]:
                    continue
                # Intersection on plane
                hx = px0 + r_dx * t_dist
                hy = py0 + r_dy * t_dist
                proj = (hx - pxw) * t_x + (hy - pyw) * t_y
                if abs(proj) > half_w:
                    continue
                u = (proj + half_w) / world_w
                sl_h = (self.proj_plane_dist / perp) * world_h
                y0 = mid_y - sl_h * 0.5
                y1 = mid_y + sl_h * 0.5
                x0_ndc = col * inv_w * 2.0 - 1.0
                x1_ndc = (col + 1) * inv_w * 2.0 - 1.0
                y0_ndc = y0 * inv_h * 2.0 - 1.0
                y1_ndc = y1 * inv_h * 2.0 - 1.0
                cols.extend(
                    [
                        [x0_ndc, y1_ndc, u, 1.0],
                        [x0_ndc, y0_ndc, u, 0.0],
                        [x1_ndc, y0_ndc, u, 0.0],
                        [x1_ndc, y0_ndc, u, 0.0],
                        [x1_ndc, y1_ndc, u, 1.0],
                        [x0_ndc, y1_ndc, u, 1.0],
                    ]
                )
            if cols:
                sprite_verts = __import__("numpy").array(
                    cols, dtype=__import__("numpy").float32
                )
                self.wall_tex_shader.use()
                gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.sprite_vbo)
                gl.glBufferData(
                    gl.GL_ARRAY_BUFFER,
                    sprite_verts.nbytes,
                    sprite_verts,
                    gl.GL_DYNAMIC_DRAW,
                )
                stride = sprite_verts.strides[0]
                gl.glEnableVertexAttribArray(self.wall_pos2Attr)
                gl.glVertexAttribPointer(
                    self.wall_pos2Attr,
                    2,
                    gl.GL_FLOAT,
                    gl.GL_FALSE,
                    stride,
                    ctypes.c_void_p(0),
                )
                gl.glEnableVertexAttribArray(self.wall_uvAttr)
                gl.glVertexAttribPointer(
                    self.wall_uvAttr,
                    2,
                    gl.GL_FLOAT,
                    gl.GL_FALSE,
                    stride,
                    ctypes.c_void_p(8),
                )
                gl.glActiveTexture(gl.GL_TEXTURE0)
                gl.glBindTexture(gl.GL_TEXTURE_2D, self.sprite_tex)
                gl.glUniform1i(self.uWallTexLoc, 0)
                gl.glDrawArrays(gl.GL_TRIANGLES, 0, len(cols))
                gl.glDisableVertexAttribArray(self.wall_pos2Attr)
                gl.glDisableVertexAttribArray(self.wall_uvAttr)
                gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
                gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
                self.wall_tex_shader.stop()
        # Billboard sprites for any additional sprites defined in world.sprites
        if hasattr(world, "sprites"):
            inv_w = 1.0 / (self.w - 1.0)
            inv_h = 1.0 / (self.h - 1.0)
            mid_y = self.h * 0.5 + player.pitch
            depth = self.wall_renderer.depth_buffer
            px0, py0 = player.x, player.y
            for sp in world.sprites:
                pxw, pyw = sp["pos"]
                world_h2 = sp.get("height") or 0.25
                # Determine current animation frame
                textures = sp.get("textures", [])
                n_frames = len(textures)
                if n_frames == 0:
                    continue
                if n_frames == 1:
                    frame_idx = 0
                else:
                    cycle = 2 * n_frames - 2
                    t = (pygame.time.get_ticks() // _ANIM_FRAME_MS) % cycle
                    frame_idx = t if t < n_frames else cycle - t
                tex_name = textures[frame_idx]
                tex_id, spr_w, spr_h = self.sprite_texs.get(
                    tex_name, (None, None, None)
                )
                if tex_id is None:
                    continue
                aspect2 = float(spr_w) / float(spr_h)
                world_w2 = world_h2 * aspect2
                half_w2 = world_w2 * 0.5
                # Compute plane normal facing the camera
                dx = px0 - pxw
                dy = py0 - pyw
                dist_plane = math.hypot(dx, dy)
                if dist_plane < 1e-6:
                    continue
                n_x = dx / dist_plane
                n_y = dy / dist_plane
                t_x = -n_y
                t_y = n_x
                cols2 = []
                for col in range(self.w):
                    ang_off = -self.half_fov + col * (self.fov / self.w)
                    r_dx = math.cos(player.angle) * math.cos(
                        ang_off
                    ) - math.sin(player.angle) * math.sin(ang_off)
                    r_dy = math.sin(player.angle) * math.cos(
                        ang_off
                    ) + math.cos(player.angle) * math.sin(ang_off)
                    denom = n_x * r_dx + n_y * r_dy
                    if abs(denom) < 1e-6:
                        continue
                    num = n_x * (pxw - px0) + n_y * (pyw - py0)
                    t_dist = num / denom
                    if t_dist <= 0:
                        continue
                    perp = t_dist * math.cos(ang_off)
                    if perp <= 0 or perp >= depth[col]:
                        continue
                    # Intersection on plane
                    hx = px0 + r_dx * t_dist
                    hy = py0 + r_dy * t_dist
                    proj = (hx - pxw) * t_x + (hy - pyw) * t_y
                    if abs(proj) > half_w2:
                        continue
                    u = (proj + half_w2) / world_w2
                    sl_h = (self.proj_plane_dist / perp) * world_h2
                    # Align enemy sprite base with ground plane
                    h_half = self.h * 0.5
                    y_base = mid_y - h_half / perp
                    y_top = y_base + sl_h
                    x0_ndc = col * inv_w * 2.0 - 1.0
                    x1_ndc = (col + 1) * inv_w * 2.0 - 1.0
                    y0_ndc = y_base * inv_h * 2.0 - 1.0
                    y1_ndc = y_top * inv_h * 2.0 - 1.0
                    cols2.extend(
                        [
                            [x0_ndc, y1_ndc, u, 1.0],
                            [x0_ndc, y0_ndc, u, 0.0],
                            [x1_ndc, y0_ndc, u, 0.0],
                            [x1_ndc, y0_ndc, u, 0.0],
                            [x1_ndc, y1_ndc, u, 1.0],
                            [x0_ndc, y1_ndc, u, 1.0],
                        ]
                    )
                if cols2:
                    sprite_verts2 = __import__("numpy").array(
                        cols2, dtype=__import__("numpy").float32
                    )
                    self.wall_tex_shader.use()
                    gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.sprite_vbo)
                    gl.glBufferData(
                        gl.GL_ARRAY_BUFFER,
                        sprite_verts2.nbytes,
                        sprite_verts2,
                        gl.GL_DYNAMIC_DRAW,
                    )
                    stride2 = sprite_verts2.strides[0]
                    gl.glEnableVertexAttribArray(self.wall_pos2Attr)
                    gl.glVertexAttribPointer(
                        self.wall_pos2Attr,
                        2,
                        gl.GL_FLOAT,
                        gl.GL_FALSE,
                        stride2,
                        ctypes.c_void_p(0),
                    )
                    gl.glEnableVertexAttribArray(self.wall_uvAttr)
                    gl.glVertexAttribPointer(
                        self.wall_uvAttr,
                        2,
                        gl.GL_FLOAT,
                        gl.GL_FALSE,
                        stride2,
                        ctypes.c_void_p(8),
                    )
                    gl.glActiveTexture(gl.GL_TEXTURE0)
                    gl.glBindTexture(gl.GL_TEXTURE_2D, tex_id)
                    gl.glUniform1i(self.uWallTexLoc, 0)
                    gl.glDrawArrays(gl.GL_TRIANGLES, 0, len(cols2))
                    gl.glDisableVertexAttribArray(self.wall_pos2Attr)
                    gl.glDisableVertexAttribArray(self.wall_uvAttr)
                    gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
                    gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
                    self.wall_tex_shader.stop()
        # Billboard sprites for dynamic enemies (chasing the player)
        if hasattr(world, "enemies"):
            inv_w = 1.0 / (self.w - 1.0)
            inv_h = 1.0 / (self.h - 1.0)
            mid_y = self.h * 0.5 + player.pitch
            depth = self.wall_renderer.depth_buffer
            px0, py0 = player.x, player.y
            # Dynamic enemies (chasing the player)
            for enemy in world.enemies:
                # Skip enemies pending respawn or dead
                if getattr(enemy, "respawn_timer", 0) > 0 or enemy.health <= 0:
                    continue
                pxw, pyw = enemy.x, enemy.y
                world_h2 = enemy.height or 0.25
                textures = enemy.textures or []
                n_frames = len(textures)
                if n_frames == 0:
                    continue
                if n_frames == 1:
                    frame_idx = 0
                else:
                    cycle = 2 * n_frames - 2
                    t = (pygame.time.get_ticks() // _ANIM_FRAME_MS) % cycle
                    frame_idx = t if t < n_frames else cycle - t
                tex_name = textures[frame_idx]
                tex_id, spr_w, spr_h = self.sprite_texs.get(
                    tex_name, (None, None, None)
                )
                if tex_id is None:
                    continue
                aspect2 = float(spr_w) / float(spr_h)
                world_w2 = world_h2 * aspect2
                half_w2 = world_w2 * 0.5
                # Compute plane normal facing the camera
                dx = px0 - pxw
                dy = py0 - pyw
                dist_plane = math.hypot(dx, dy)
                if dist_plane < 1e-6:
                    continue
                n_x = dx / dist_plane
                n_y = dy / dist_plane
                t_x = -n_y
                t_y = n_x
                cols2 = []
                for col in range(self.w):
                    ang_off = -self.half_fov + col * (self.fov / self.w)
                    r_dx = math.cos(player.angle) * math.cos(
                        ang_off
                    ) - math.sin(player.angle) * math.sin(ang_off)
                    r_dy = math.sin(player.angle) * math.cos(
                        ang_off
                    ) + math.cos(player.angle) * math.sin(ang_off)
                    denom = n_x * r_dx + n_y * r_dy
                    if abs(denom) < 1e-6:
                        continue
                    num = n_x * (pxw - px0) + n_y * (pyw - py0)
                    t_dist = num / denom
                    if t_dist <= 0:
                        continue
                    perp = t_dist * math.cos(ang_off)
                    if perp <= 0 or perp >= depth[col]:
                        continue
                    # Intersection on plane
                    hx = px0 + r_dx * t_dist
                    hy = py0 + r_dy * t_dist
                    proj = (hx - pxw) * t_x + (hy - pyw) * t_y
                    if abs(proj) > half_w2:
                        continue
                    u = (proj + half_w2) / world_w2
                    sl_h = (self.proj_plane_dist / perp) * world_h2
                    # Align sprite base with ground plane
                    y_base = mid_y - (self.h * 0.5) / perp
                    y_top = y_base + sl_h
                    x0_ndc = col * inv_w * 2.0 - 1.0
                    x1_ndc = (col + 1) * inv_w * 2.0 - 1.0
                    y0_ndc = y_base * inv_h * 2.0 - 1.0
                    y1_ndc = y_top * inv_h * 2.0 - 1.0
                    cols2.extend(
                        [
                            [x0_ndc, y1_ndc, u, 1.0],
                            [x0_ndc, y0_ndc, u, 0.0],
                            [x1_ndc, y0_ndc, u, 0.0],
                            [x1_ndc, y0_ndc, u, 0.0],
                            [x1_ndc, y1_ndc, u, 1.0],
                            [x0_ndc, y1_ndc, u, 1.0],
                        ]
                    )
                if cols2:
                    sprite_verts2 = __import__("numpy").array(
                        cols2, dtype=__import__("numpy").float32
                    )
                    self.wall_tex_shader.use()
                    gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.sprite_vbo)
                    gl.glBufferData(
                        gl.GL_ARRAY_BUFFER,
                        sprite_verts2.nbytes,
                        sprite_verts2,
                        gl.GL_DYNAMIC_DRAW,
                    )
                    stride2 = sprite_verts2.strides[0]
                    gl.glEnableVertexAttribArray(self.wall_pos2Attr)
                    gl.glVertexAttribPointer(
                        self.wall_pos2Attr,
                        2,
                        gl.GL_FLOAT,
                        gl.GL_FALSE,
                        stride2,
                        ctypes.c_void_p(0),
                    )
                    gl.glEnableVertexAttribArray(self.wall_uvAttr)
                    gl.glVertexAttribPointer(
                        self.wall_uvAttr,
                        2,
                        gl.GL_FLOAT,
                        gl.GL_FALSE,
                        stride2,
                        ctypes.c_void_p(8),
                    )
                    gl.glActiveTexture(gl.GL_TEXTURE0)
                    gl.glBindTexture(gl.GL_TEXTURE_2D, tex_id)
                    gl.glUniform1i(self.uWallTexLoc, 0)
                    gl.glDrawArrays(gl.GL_TRIANGLES, 0, len(cols2))
                    gl.glDisableVertexAttribArray(self.wall_pos2Attr)
                    gl.glDisableVertexAttribArray(self.wall_uvAttr)
                    gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
                    gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
                    self.wall_tex_shader.stop()
        # UI overlay: render text quad
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        # Calculate quad in NDC (10px from bottom-left)
        px, py = 10, self.h - 10 - self.ui_text_height
        inv_w = 1.0 / (self.w - 1.0)
        inv_h = 1.0 / (self.h - 1.0)
        x0 = px * inv_w * 2.0 - 1.0
        x1 = (px + self.ui_text_width) * inv_w * 2.0 - 1.0
        y0 = py * inv_h * 2.0 - 1.0
        y1 = (py + self.ui_text_height) * inv_h * 2.0 - 1.0
        ui_verts = __import__("numpy").array(
            [
                [x0, y0, 0.0, 0.0],
                [x1, y0, 1.0, 0.0],
                [x1, y1, 1.0, 1.0],
                [x0, y0, 0.0, 0.0],
                [x1, y1, 1.0, 1.0],
                [x0, y1, 0.0, 1.0],
            ],
            dtype=__import__("numpy").float32,
        )
        self.wall_tex_shader.use()
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.ui_vbo)
        gl.glBufferData(
            gl.GL_ARRAY_BUFFER, ui_verts.nbytes, ui_verts, gl.GL_DYNAMIC_DRAW
        )
        stride = ui_verts.strides[0]
        gl.glEnableVertexAttribArray(self.wall_pos2Attr)
        gl.glVertexAttribPointer(
            self.wall_pos2Attr,
            2,
            gl.GL_FLOAT,
            gl.GL_FALSE,
            stride,
            ctypes.c_void_p(0),
        )
        gl.glEnableVertexAttribArray(self.wall_uvAttr)
        gl.glVertexAttribPointer(
            self.wall_uvAttr,
            2,
            gl.GL_FLOAT,
            gl.GL_FALSE,
            stride,
            ctypes.c_void_p(8),
        )
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.ui_tex)
        gl.glUniform1i(self.uWallTexLoc, 0)
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, 6)
        gl.glDisableVertexAttribArray(self.wall_pos2Attr)
        gl.glDisableVertexAttribArray(self.wall_uvAttr)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        self.wall_tex_shader.stop()
        # Crosshair overlay: draw a simple plus at screen center
        # Switch to orthographic projection for 2D drawing
        gl.glMatrixMode(gl.GL_PROJECTION)
        gl.glPushMatrix()
        gl.glLoadIdentity()
        gl.glOrtho(0, self.w, self.h, 0, -1, 1)
        gl.glMatrixMode(gl.GL_MODELVIEW)
        gl.glPushMatrix()
        gl.glLoadIdentity()
        # Draw crosshair lines (10px total length)
        gl.glDisable(gl.GL_TEXTURE_2D)
        gl.glColor3f(1.0, 1.0, 1.0)
        gl.glLineWidth(2.0)
        cx = self.w // 2
        cy = self.h // 2
        gl.glBegin(gl.GL_LINES)
        gl.glVertex2f(cx - 5, cy)
        gl.glVertex2f(cx + 5, cy)
        gl.glVertex2f(cx, cy - 5)
        gl.glVertex2f(cx, cy + 5)
        gl.glEnd()
        # Flash red crosshair on hit
        if pygame.time.get_ticks() < self.hit_flash_until:
            gl.glColor3f(1.0, 0.0, 0.0)
            gl.glLineWidth(4.0)
            gl.glBegin(gl.GL_LINES)
            gl.glVertex2f(cx - 5, cy)
            gl.glVertex2f(cx + 5, cy)
            gl.glVertex2f(cx, cy - 5)
            gl.glVertex2f(cx, cy + 5)
            gl.glEnd()
            # restore white crosshair width
            gl.glColor3f(1.0, 1.0, 1.0)
            gl.glLineWidth(2.0)
        gl.glEnable(gl.GL_TEXTURE_2D)
        # Restore previous matrices
        gl.glPopMatrix()
        gl.glMatrixMode(gl.GL_PROJECTION)
        gl.glPopMatrix()
        gl.glMatrixMode(gl.GL_MODELVIEW)
        # Swap buffers
        pygame.display.flip()

    def shutdown(self) -> None:
        """Free tracked GL resources."""
        self._res.shutdown()
