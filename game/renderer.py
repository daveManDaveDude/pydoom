"""
OpenGL-based renderer: uses GPU shaders for floor, ceiling, walls, and UI overlay.
"""
import os
import ctypes
import pygame
import math
try:
    import OpenGL.GL as gl  # noqa: N811
except ImportError:
    raise ImportError(
        "PyOpenGL is required to run this renderer. "
        "Please install via: pip install PyOpenGL PyOpenGL_accelerate"
    )
from .gl_resources import GLResourceManager
from .config import CEILING_COLOR, WALL_SHADE_X, WALL_SHADE_Y, FLOOR_TEXTURE_FILE, CEILING_TEXTURE_FILE, WALL_TEXTURE_FILE, SPRITE_TEXTURE_FILE
from .gl_utils import ShaderProgram, load_texture, setup_opengl, create_texture_from_surface
from .wall_renderer import CpuWallRenderer

def _delete_buffer(obj_id):
    """Deletes a single GL buffer."""
    gl.glDeleteBuffers(1, [obj_id])

def _delete_texture(obj_id):
    """Deletes a single GL texture."""
    gl.glDeleteTextures(1, [obj_id])

def compile_shader(source, shader_type):
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

def link_program(vs, fs):
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
    def __init__(self, screen_width, screen_height, fov=math.pi/3, step_size=0.005, world=None):
        self.w = screen_width
        self.h = screen_height
        self.world = world
        self.fov = fov
        self.half_fov = fov / 2.0
        # GL resource manager to track and clean up GL objects
        self._res = GLResourceManager()
        # Projection plane distance for wall heights
        self.proj_plane_dist = (self.w / 2.0) / __import__('math').tan(self.half_fov)
        # Basic OpenGL state
        setup_opengl(self.w, self.h)
        # Floor & ceiling shader
        shader_dir = os.path.join(os.path.dirname(__file__), 'shaders')
        floor_vs = os.path.join(shader_dir, 'floor.vert')
        floor_fs = os.path.join(shader_dir, 'floor.frag')
        self.floor_shader = ShaderProgram(vertex_path=floor_vs, fragment_path=floor_fs)
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
        quad = __import__('numpy').array([-1.0, -1.0,
                                         1.0, -1.0,
                                        -1.0,  1.0,
                                         1.0,  1.0], dtype=__import__('numpy').float32)
        self.quad_vbo = self._res.gen(lambda: gl.glGenBuffers(1), _delete_buffer)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.quad_vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, quad.nbytes, quad, gl.GL_STATIC_DRAW)
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
        self.wall_color_shader = ShaderProgram(vertex_source=wall_vs_src, fragment_source=wall_fs_src)
        self.posAttr = self.wall_color_shader.get_attrib("aPos")
        self.colAttr = self.wall_color_shader.get_attrib("aColor")
        self.wall_vbo = self._res.gen(lambda: gl.glGenBuffers(1), _delete_buffer)
        self.color_vbo = self._res.gen(lambda: gl.glGenBuffers(1), _delete_buffer)
        # Load floor and ceiling textures
        textures_dir = os.path.join(os.path.dirname(__file__), 'textures')
        self.floor_tex = load_texture(os.path.join(textures_dir, FLOOR_TEXTURE_FILE))
        self.ceil_tex  = load_texture(os.path.join(textures_dir, CEILING_TEXTURE_FILE))
        # Textured wall shader
        wall_vs = os.path.join(shader_dir, 'wall_textured.vert')
        wall_fs = os.path.join(shader_dir, 'wall_textured.frag')
        self.wall_tex_shader = ShaderProgram(vertex_path=wall_vs, fragment_path=wall_fs)
        self.wall_pos2Attr = self.wall_tex_shader.get_attrib("aPos")
        self.wall_uvAttr   = self.wall_tex_shader.get_attrib("aUV")
        self.uWallTexLoc   = self.wall_tex_shader.get_uniform("uWallTex")
        self.wall_tex_vbo = self._res.gen(lambda: gl.glGenBuffers(1), _delete_buffer)
        # Load wall texture
        self.wall_tex = load_texture(os.path.join(textures_dir, WALL_TEXTURE_FILE))
        # CPU-based wall renderer
        self.wall_renderer = CpuWallRenderer(
            self.w, self.h, self.fov, self.proj_plane_dist,
            self.wall_tex, self.wall_tex_shader,
            self.wall_pos2Attr, self.wall_uvAttr, self.uWallTexLoc
        )
        # Load sprite texture for demo sprite rendering
        sprite_path = os.path.join(textures_dir, SPRITE_TEXTURE_FILE)
        spr_surf = pygame.image.load(sprite_path).convert_alpha()
        self.sprite_tex = load_texture(sprite_path, wrap_s=gl.GL_CLAMP, wrap_t=gl.GL_CLAMP)
        self.sprite_width, self.sprite_height = spr_surf.get_size()
        self.sprite_vbo = self._res.gen(lambda: gl.glGenBuffers(1), _delete_buffer)
        # Prepare mapping of sprite textures (demo and any additional sprites)
        self.sprite_texs = {SPRITE_TEXTURE_FILE: (self.sprite_tex, self.sprite_width, self.sprite_height)}
        if self.world and hasattr(self.world, 'sprites'):
            for sp in self.world.sprites:
                tex_name = sp.get('texture')
                if tex_name and tex_name not in self.sprite_texs:
                    sp_path = os.path.join(textures_dir, tex_name)
                    sp_surf = pygame.image.load(sp_path).convert_alpha()
                    tex_id = load_texture(sp_path, wrap_s=gl.GL_CLAMP, wrap_t=gl.GL_CLAMP)
                    w, h = sp_surf.get_size()
                    self.sprite_texs[tex_name] = (tex_id, w, h)
        # Prepare UI overlay text (Press Q to quit)
        self.ui_font = pygame.font.SysFont(None, 24)
        ui_surf = self.ui_font.render("Press Q to quit", True, (255, 255, 255))
        self.ui_text_width, self.ui_text_height = ui_surf.get_size()
        # Create UI texture
        self.ui_tex = create_texture_from_surface(ui_surf)
        # VBO for UI quad
        self.ui_vbo = self._res.gen(lambda: gl.glGenBuffers(1), _delete_buffer)
        # Load ceiling texture
        path_c = os.path.join(textures_dir, CEILING_TEXTURE_FILE)
        img_c = pygame.image.load(path_c).convert_alpha()
        twc, thc = img_c.get_size()
        raw_c = pygame.image.tostring(img_c, "RGBA", True)
        self.ceil_tex = self._res.gen(lambda: gl.glGenTextures(1), _delete_texture)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.ceil_tex)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_REPEAT)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_REPEAT)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, twc, thc, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, raw_c)
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)

    def render(self, screen, world, player):
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
        gl.glVertexAttribPointer(self.aPosLoc, 2, gl.GL_FLOAT, gl.GL_FALSE, 0, ctypes.c_void_p(0))
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
            n_x = math.cos(ang_p); n_y = math.sin(ang_p)
            t_x = -n_y; t_y = n_x
            px0, py0 = player.x, player.y
            cols = []
            for col in range(self.w):
                ang_off = -self.half_fov + col * (self.fov / self.w)
                r_dx = math.cos(player.angle) * math.cos(ang_off) - math.sin(player.angle) * math.sin(ang_off)
                r_dy = math.sin(player.angle) * math.cos(ang_off) + math.cos(player.angle) * math.sin(ang_off)
                denom = n_x * r_dx + n_y * r_dy
                if abs(denom) < 1e-6: continue
                num = n_x * (pxw - px0) + n_y * (pyw - py0)
                t_dist = num / denom
                if t_dist <= 0: continue
                perp = t_dist * math.cos(ang_off)
                if perp <= 0 or perp >= depth[col]: continue
                # Intersection on plane
                hx = px0 + r_dx * t_dist
                hy = py0 + r_dy * t_dist
                proj = (hx - pxw) * t_x + (hy - pyw) * t_y
                if abs(proj) > half_w: continue
                u = (proj + half_w) / world_w
                sl_h = (self.proj_plane_dist / perp) * world_h
                y0 = mid_y - sl_h * 0.5; y1 = mid_y + sl_h * 0.5
                x0_ndc = col * inv_w * 2.0 - 1.0
                x1_ndc = (col + 1) * inv_w * 2.0 - 1.0
                y0_ndc = y0 * inv_h * 2.0 - 1.0
                y1_ndc = y1 * inv_h * 2.0 - 1.0
                cols.extend([
                    [x0_ndc, y1_ndc, u, 1.0],
                    [x0_ndc, y0_ndc, u, 0.0],
                    [x1_ndc, y0_ndc, u, 0.0],
                    [x1_ndc, y0_ndc, u, 0.0],
                    [x1_ndc, y1_ndc, u, 1.0],
                    [x0_ndc, y1_ndc, u, 1.0],
                ])
            if cols:
                sprite_verts = __import__('numpy').array(cols, dtype=__import__('numpy').float32)
                self.wall_tex_shader.use()
                gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.sprite_vbo)
                gl.glBufferData(gl.GL_ARRAY_BUFFER, sprite_verts.nbytes, sprite_verts, gl.GL_DYNAMIC_DRAW)
                stride = sprite_verts.strides[0]
                gl.glEnableVertexAttribArray(self.wall_pos2Attr)
                gl.glVertexAttribPointer(self.wall_pos2Attr, 2, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(0))
                gl.glEnableVertexAttribArray(self.wall_uvAttr)
                gl.glVertexAttribPointer(self.wall_uvAttr, 2, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(8))
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
        if hasattr(world, 'sprites'):
            inv_w = 1.0 / (self.w - 1.0)
            inv_h = 1.0 / (self.h - 1.0)
            mid_y = self.h * 0.5 + player.pitch
            depth = self.wall_renderer.depth_buffer
            px0, py0 = player.x, player.y
            for sp in world.sprites:
                pxw, pyw = sp['pos']
                world_h2 = sp.get('height') or 0.25
                tex_name = sp['texture']
                tex_id, spr_w, spr_h = self.sprite_texs.get(tex_name, (None, None, None))
                if tex_id is None:
                    continue
                aspect2 = float(spr_w) / float(spr_h)
                world_w2 = world_h2 * aspect2
                half_w2 = world_w2 * 0.5
                # Compute plane normal facing the camera
                dx = px0 - pxw; dy = py0 - pyw
                dist_plane = math.hypot(dx, dy)
                if dist_plane < 1e-6:
                    continue
                n_x = dx / dist_plane; n_y = dy / dist_plane
                t_x = -n_y; t_y = n_x
                cols2 = []
                for col in range(self.w):
                    ang_off = -self.half_fov + col * (self.fov / self.w)
                    r_dx = math.cos(player.angle) * math.cos(ang_off) - math.sin(player.angle) * math.sin(ang_off)
                    r_dy = math.sin(player.angle) * math.cos(ang_off) + math.cos(player.angle) * math.sin(ang_off)
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
                    hx = px0 + r_dx * t_dist; hy = py0 + r_dy * t_dist
                    proj = (hx - pxw) * t_x + (hy - pyw) * t_y
                    if abs(proj) > half_w2:
                        continue
                    u = (proj + half_w2) / world_w2
                    sl_h = (self.proj_plane_dist / perp) * world_h2
                    # Align enemy sprite base with ground plane
                    h_half = self.h * 0.5
                    y_base = mid_y - h_half / perp
                    y_top = y_base + sl_h
                    x0_ndc = col * inv_w * 2.0 - 1.0; x1_ndc = (col + 1) * inv_w * 2.0 - 1.0
                    y0_ndc = y_base * inv_h * 2.0 - 1.0; y1_ndc = y_top * inv_h * 2.0 - 1.0
                    cols2.extend([
                        [x0_ndc, y1_ndc, u, 1.0],
                        [x0_ndc, y0_ndc, u, 0.0],
                        [x1_ndc, y0_ndc, u, 0.0],
                        [x1_ndc, y0_ndc, u, 0.0],
                        [x1_ndc, y1_ndc, u, 1.0],
                        [x0_ndc, y1_ndc, u, 1.0],
                    ])
                if cols2:
                    sprite_verts2 = __import__('numpy').array(cols2, dtype=__import__('numpy').float32)
                    self.wall_tex_shader.use()
                    gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.sprite_vbo)
                    gl.glBufferData(gl.GL_ARRAY_BUFFER, sprite_verts2.nbytes, sprite_verts2, gl.GL_DYNAMIC_DRAW)
                    stride2 = sprite_verts2.strides[0]
                    gl.glEnableVertexAttribArray(self.wall_pos2Attr)
                    gl.glVertexAttribPointer(self.wall_pos2Attr, 2, gl.GL_FLOAT, gl.GL_FALSE, stride2, ctypes.c_void_p(0))
                    gl.glEnableVertexAttribArray(self.wall_uvAttr)
                    gl.glVertexAttribPointer(self.wall_uvAttr, 2, gl.GL_FLOAT, gl.GL_FALSE, stride2, ctypes.c_void_p(8))
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
        ui_verts = __import__('numpy').array([
            [x0, y0, 0.0, 0.0],
            [x1, y0, 1.0, 0.0],
            [x1, y1, 1.0, 1.0],
            [x0, y0, 0.0, 0.0],
            [x1, y1, 1.0, 1.0],
            [x0, y1, 0.0, 1.0],
        ], dtype=__import__('numpy').float32)
        self.wall_tex_shader.use()
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.ui_vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, ui_verts.nbytes, ui_verts, gl.GL_DYNAMIC_DRAW)
        stride = ui_verts.strides[0]
        gl.glEnableVertexAttribArray(self.wall_pos2Attr)
        gl.glVertexAttribPointer(self.wall_pos2Attr, 2, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(0))
        gl.glEnableVertexAttribArray(self.wall_uvAttr)
        gl.glVertexAttribPointer(self.wall_uvAttr, 2, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(8))
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.ui_tex)
        gl.glUniform1i(self.uWallTexLoc, 0)
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, 6)
        gl.glDisableVertexAttribArray(self.wall_pos2Attr)
        gl.glDisableVertexAttribArray(self.wall_uvAttr)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        self.wall_tex_shader.stop()
        # Swap buffers
        pygame.display.flip()

    def shutdown(self):
        """Free tracked GL resources."""
        self._res.shutdown()