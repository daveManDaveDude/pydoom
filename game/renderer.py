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
from .config import CEILING_COLOR, WALL_SHADE_X, WALL_SHADE_Y, FLOOR_TEXTURE_FILE, CEILING_TEXTURE_FILE, WALL_TEXTURE_FILE, SPRITE_TEXTURE_FILE
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
        # Load sprite texture for demo sprite rendering
        sprite_path = os.path.join(textures_dir, SPRITE_TEXTURE_FILE)
        spr_surf = pygame.image.load(sprite_path).convert_alpha()
        self.sprite_tex = load_texture(sprite_path, wrap_s=GL_CLAMP, wrap_t=GL_CLAMP)
        self.sprite_width, self.sprite_height = spr_surf.get_size()
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
        self.wall_renderer.render(world, player)
        # Sprite pass: render fixed planar sprite in perspective
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        # Define sprite size in world units: height and width (aspect preserved)
        world_h = 0.25
        aspect = float(self.sprite_width) / float(self.sprite_height)
        world_w = world_h * aspect
        half_w = world_w / 2.0
        inv_w = 1.0 / (self.w - 1.0)
        inv_h = 1.0 / (self.h - 1.0)
        mid_y = self.h / 2.0 + player.pitch
        depth = self.wall_renderer.depth_buffer
        cos_pa = math.cos(player.angle)
        sin_pa = math.sin(player.angle)
        fx, fy = cos_pa, sin_pa
        rx, ry = -sin_pa, cos_pa
        cols = []
        if world.powerup:
            pxw, pyw = world.powerup
            for col in range(self.w):
                ang = -self.half_fov + col * (self.fov / self.w)
                dx = cos_pa * math.cos(ang) - sin_pa * math.sin(ang)
                dy = sin_pa * math.cos(ang) + cos_pa * math.sin(ang)
                if abs(dx) < 1e-6:
                    continue
                t = (pxw - player.x) / dx
                if t <= 0:
                    continue
                y_hit = player.y + t * dy
                if abs(y_hit - pyw) > half_w:
                    continue
                perp = t * math.cos(ang)
                if perp <= 0 or perp >= depth[col]:
                    continue
                # Projected slice height (pixels) based on world height
                sl_h = (self.proj_plane_dist / perp) * world_h
                y0 = mid_y - sl_h / 2.0
                y1 = mid_y + sl_h / 2.0
                # Texture U coordinate proportional to hit position on sprite width
                u = (y_hit - (pyw - half_w)) / world_w
                x0 = col * inv_w * 2.0 - 1.0
                x1 = (col + 1) * inv_w * 2.0 - 1.0
                y0_ndc = y0 * inv_h * 2.0 - 1.0
                y1_ndc = y1 * inv_h * 2.0 - 1.0
                cols += [
                    [x0, y1_ndc, u, 1.0],
                    [x0, y0_ndc, u, 0.0],
                    [x1, y0_ndc, u, 0.0],
                    [x1, y0_ndc, u, 0.0],
                    [x1, y1_ndc, u, 1.0],
                    [x0, y1_ndc, u, 1.0],
                ]
        if cols:
            sprite_verts = __import__('numpy').array(cols, dtype=__import__('numpy').float32)
            self.wall_tex_shader.use()
            glBindBuffer(GL_ARRAY_BUFFER, self.sprite_vbo)
            glBufferData(GL_ARRAY_BUFFER, sprite_verts.nbytes, sprite_verts, GL_DYNAMIC_DRAW)
            stride = sprite_verts.strides[0]
            glEnableVertexAttribArray(self.wall_pos2Attr)
            glVertexAttribPointer(self.wall_pos2Attr, 2, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(0))
            glEnableVertexAttribArray(self.wall_uvAttr)
            glVertexAttribPointer(self.wall_uvAttr, 2, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(8))
            glActiveTexture(GL_TEXTURE0)
            glBindTexture(GL_TEXTURE_2D, self.sprite_tex)
            glUniform1i(self.uWallTexLoc, 0)
            glDrawArrays(GL_TRIANGLES, 0, len(cols))
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