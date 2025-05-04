"""
OpenGL-based renderer: uses GPU shaders for floor, ceiling, walls, and UI overlay.
"""
import os
import ctypes
import pygame
import math
try:
    from OpenGL.GL import *
except ImportError:
    raise ImportError(
        "PyOpenGL is required to run this renderer. "
        "Please install via: pip install PyOpenGL PyOpenGL_accelerate"
    )
from .config import (
    CEILING_COLOR, WALL_SHADE_X, WALL_SHADE_Y,
    FLOOR_TEXTURE_FILE, CEILING_TEXTURE_FILE, WALL_TEXTURE_FILE,
    SPRITE_TEXTURES, SPRITE_SCALE
)
from .gl_utils import ShaderProgram, load_texture, setup_opengl, create_texture_from_surface
from .wall_renderer import CpuWallRenderer

def compile_shader(source, shader_type):
    """
    Compile a GLSL shader (vertex or fragment) from the given source string.
    Raises RuntimeError if compilation fails.
    """
    shader = glCreateShader(shader_type)
    glShaderSource(shader, source)
    glCompileShader(shader)
    status = glGetShaderiv(shader, GL_COMPILE_STATUS)
    if not status:
        log = glGetShaderInfoLog(shader).decode()
        logger.error("Shader compile failed: %s", log)
        raise RuntimeError(f"Shader compile error: {log}")
    return shader

def link_program(vs, fs):
    """
    Link compiled vertex and fragment shaders into a GL program.
    Raises RuntimeError if linking fails.
    """
    prog = glCreateProgram()
    glAttachShader(prog, vs)
    glAttachShader(prog, fs)
    glLinkProgram(prog)
    status = glGetProgramiv(prog, GL_LINK_STATUS)
    if not status:
        log = glGetProgramInfoLog(prog).decode()
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
        self.quad_vbo = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.quad_vbo)
        glBufferData(GL_ARRAY_BUFFER, quad.nbytes, quad, GL_STATIC_DRAW)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
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
        self.wall_vbo = glGenBuffers(1)
        self.color_vbo = glGenBuffers(1)
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
        self.wall_tex_vbo  = glGenBuffers(1)
        # Load wall texture
        self.wall_tex = load_texture(os.path.join(textures_dir, WALL_TEXTURE_FILE))
        # CPU-based wall renderer
        self.wall_renderer = CpuWallRenderer(
            self.w, self.h, self.fov, self.proj_plane_dist,
            self.wall_tex, self.wall_tex_shader,
            self.wall_pos2Attr, self.wall_uvAttr, self.uWallTexLoc
        )
        # Sprite textures mapping and VBO
        from .config import SPRITE_TEXTURES, SPRITE_SCALE
        self.sprite_textures = {}
        sprites_dir = os.path.join(os.path.dirname(__file__), 'textures')
        for key, fname in SPRITE_TEXTURES.items():
            tex_path = os.path.join(sprites_dir, fname)
            self.sprite_textures[key] = load_texture(tex_path)
        self.sprite_vbo = glGenBuffers(1)
        # Prepare UI overlay text (Press Q to quit)
        self.ui_font = pygame.font.SysFont(None, 24)
        ui_surf = self.ui_font.render("Press Q to quit", True, (255, 255, 255))
        self.ui_text_width, self.ui_text_height = ui_surf.get_size()
        # Create UI texture
        self.ui_tex = create_texture_from_surface(ui_surf)
        # VBO for UI quad
        self.ui_vbo = glGenBuffers(1)
        # Load ceiling texture
        path_c = os.path.join(textures_dir, CEILING_TEXTURE_FILE)
        img_c = pygame.image.load(path_c).convert_alpha()
        twc, thc = img_c.get_size()
        raw_c = pygame.image.tostring(img_c, "RGBA", True)
        self.ceil_tex = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.ceil_tex)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, twc, thc, 0, GL_RGBA, GL_UNSIGNED_BYTE, raw_c)
        glBindTexture(GL_TEXTURE_2D, 0)

    def render(self, screen, world, player):
        # Clear color and depth buffers and disable depth testing for full-screen draws
        # Clear buffers
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glDisable(GL_DEPTH_TEST)
        # Floor & ceiling pass
        self.floor_shader.use()
        glUniform2f(self.uResLoc, float(self.w), float(self.h))
        glUniform2f(self.uPosLoc, player.x, player.y)
        glUniform1f(self.uAngLoc, player.angle)
        glUniform1f(self.uHalfFovLoc, self.half_fov)
        glUniform1f(self.uPitchLoc, player.pitch)
        # Bind floor texture
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.floor_tex)
        glUniform1i(self.uFloorTexLoc, 0)
        # Bind ceiling texture
        glActiveTexture(GL_TEXTURE1)
        glBindTexture(GL_TEXTURE_2D, self.ceil_tex)
        glUniform1i(self.uCeilTexLoc, 1)
        # Draw full-screen quad
        glBindBuffer(GL_ARRAY_BUFFER, self.quad_vbo)
        glEnableVertexAttribArray(self.aPosLoc)
        glVertexAttribPointer(self.aPosLoc, 2, GL_FLOAT, GL_FALSE, 0, ctypes.c_void_p(0))
        glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)
        glDisableVertexAttribArray(self.aPosLoc)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        self.floor_shader.stop()
        # Walls pass
        glDisable(GL_BLEND)
        # Walls pass
        glDisable(GL_BLEND)
        self.wall_renderer.render(world, player)
        # Sprite rendering pass (billboarded objects)
        sprites = getattr(world, 'objects', None)
        if sprites:
            # Compute per-sprite distance and angle, cull and sort back-to-front
            sprite_list = []
            for sprite in sprites:
                dx = sprite.x - player.x
                dy = sprite.y - player.y
                distance = math.hypot(dx, dy)
                angle = math.atan2(dy, dx) - player.angle
                # Normalize angle to [-pi, pi]
                while angle < -math.pi:
                    angle += 2 * math.pi
                while angle >  math.pi:
                    angle -= 2 * math.pi
                # Cull sprites outside field of view
                if abs(angle) > self.half_fov:
                    continue
                sprite_list.append((sprite, distance, angle))
            # Draw sprites farthest first
            sprite_list.sort(key=lambda s: s[1], reverse=True)
            if sprite_list:
                # Depth buffer from wall renderer for simple occlusion at sprite center
                depth_buffer = getattr(self.wall_renderer, 'depth_buffer', None)
                numpy = __import__('numpy')
                # Use wall-texture shader
                self.wall_tex_shader.use()
                glBindBuffer(GL_ARRAY_BUFFER, self.sprite_vbo)
                # Set up attribute pointers
                stride = numpy.dtype(numpy.float32).itemsize * 4
                glEnableVertexAttribArray(self.wall_pos2Attr)
                glVertexAttribPointer(self.wall_pos2Attr, 2, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(0))
                glEnableVertexAttribArray(self.wall_uvAttr)
                glVertexAttribPointer(self.wall_uvAttr, 2, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(8))
                for sprite, distance, angle in sprite_list:
                    # Per-sprite perpendicular distance
                    perp = max(distance * math.cos(angle), 1e-3)
                    # Occlusion check at sprite center
                    if depth_buffer is not None:
                        ci = int(((angle / self.half_fov + 1) * 0.5) * self.w)
                        ci = max(0, min(self.w - 1, ci))
                        if perp >= depth_buffer[ci]:
                            continue
                    # Sprite dimensions
                    half_w = SPRITE_SCALE * 0.5
                    height_w = SPRITE_SCALE
                    mid = self.h * 0.5 + player.pitch
                    inv_w = 1.0 / (self.w - 1.0)
                    inv_h = 1.0 / (self.h - 1.0)
                    # Sprite orientation
                    rot = sprite.orientation
                    rx = math.sin(rot)
                    ry = -math.cos(rot)
                    # World positions of corners
                    blx = sprite.x - rx * half_w; bly = sprite.y - ry * half_w
                    brx = sprite.x + rx * half_w; bry = sprite.y + ry * half_w
                    # Project bottom-left
                    dx_bl = blx - player.x; dy_bl = bly - player.y
                    ang_bl = math.atan2(dy_bl, dx_bl) - player.angle
                    while ang_bl < -math.pi: ang_bl += 2 * math.pi
                    while ang_bl >  math.pi: ang_bl -= 2 * math.pi
                    dist_bl = math.hypot(dx_bl, dy_bl)
                    perp_bl = max(dist_bl * math.cos(ang_bl), 1e-3)
                    slice_h_bl = self.proj_plane_dist * height_w / perp_bl
                    px_bl = ((ang_bl / self.half_fov + 1.0) * 0.5) * self.w
                    py_bl = mid + slice_h_bl * 0.5
                    py_tl = mid - slice_h_bl * 0.5
                    # Project bottom-right
                    dx_br = brx - player.x; dy_br = bry - player.y
                    ang_br = math.atan2(dy_br, dx_br) - player.angle
                    while ang_br < -math.pi: ang_br += 2 * math.pi
                    while ang_br >  math.pi: ang_br -= 2 * math.pi
                    dist_br = math.hypot(dx_br, dy_br)
                    perp_br = max(dist_br * math.cos(ang_br), 1e-3)
                    slice_h_br = self.proj_plane_dist * height_w / perp_br
                    px_br = ((ang_br / self.half_fov + 1.0) * 0.5) * self.w
                    py_br = mid + slice_h_br * 0.5
                    py_tr = mid - slice_h_br * 0.5
                    # Convert to NDC
                    x0_ndc = px_bl * inv_w * 2.0 - 1.0
                    x1_ndc = px_br * inv_w * 2.0 - 1.0
                    y0_ndc = py_tl * inv_h * 2.0 - 1.0
                    y1_ndc = py_bl * inv_h * 2.0 - 1.0
                    y2_ndc = py_tr * inv_h * 2.0 - 1.0
                    y3_ndc = py_br * inv_h * 2.0 - 1.0
                    # Build vertex array
                    verts = numpy.array([
                        [x0_ndc, y1_ndc, 0.0, 1.0],
                        [x0_ndc, y0_ndc, 0.0, 0.0],
                        [x1_ndc, y2_ndc, 1.0, 0.0],
                        [x1_ndc, y2_ndc, 1.0, 0.0],
                        [x1_ndc, y3_ndc, 1.0, 1.0],
                        [x0_ndc, y1_ndc, 0.0, 1.0],
                    ], dtype=numpy.float32)
                    tex = self.sprite_textures.get(sprite.type)
                    if tex is None:
                        continue
                    glBufferData(GL_ARRAY_BUFFER, verts.nbytes, verts, GL_DYNAMIC_DRAW)
                    glActiveTexture(GL_TEXTURE0)
                    glBindTexture(GL_TEXTURE_2D, tex)
                    glUniform1i(self.uWallTexLoc, 0)
                    glDrawArrays(GL_TRIANGLES, 0, 6)
                # Cleanup
                glDisableVertexAttribArray(self.wall_pos2Attr)
                glDisableVertexAttribArray(self.wall_uvAttr)
                glBindBuffer(GL_ARRAY_BUFFER, 0)
                glBindTexture(GL_TEXTURE_2D, 0)
                self.wall_tex_shader.stop()
        # UI overlay: render text quad
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
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
        glBindBuffer(GL_ARRAY_BUFFER, self.ui_vbo)
        glBufferData(GL_ARRAY_BUFFER, ui_verts.nbytes, ui_verts, GL_DYNAMIC_DRAW)
        stride = ui_verts.strides[0]
        glEnableVertexAttribArray(self.wall_pos2Attr)
        glVertexAttribPointer(self.wall_pos2Attr, 2, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(0))
        glEnableVertexAttribArray(self.wall_uvAttr)
        glVertexAttribPointer(self.wall_uvAttr, 2, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(8))
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.ui_tex)
        glUniform1i(self.uWallTexLoc, 0)
        glDrawArrays(GL_TRIANGLES, 0, 6)
        glDisableVertexAttribArray(self.wall_pos2Attr)
        glDisableVertexAttribArray(self.wall_uvAttr)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindTexture(GL_TEXTURE_2D, 0)
        self.wall_tex_shader.stop()
        # Swap buffers
        pygame.display.flip()