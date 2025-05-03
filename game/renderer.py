import math
import os
import ctypes
import pygame
import numpy as np
try:
    from OpenGL.GL import *
except ImportError:
    raise ImportError(
        "PyOpenGL is required to run this renderer. "
        "Please install via: pip install PyOpenGL PyOpenGL_accelerate"
    )
from .config import CEILING_COLOR, WALL_SHADE_X, WALL_SHADE_Y, FLOOR_TEXTURE_FILE, CEILING_TEXTURE_FILE, WALL_TEXTURE_FILE

def compile_shader(source, shader_type):
    shader = glCreateShader(shader_type)
    glShaderSource(shader, source)
    glCompileShader(shader)
    status = glGetShaderiv(shader, GL_COMPILE_STATUS)
    if not status:
        log = glGetShaderInfoLog(shader).decode()
        raise RuntimeError(f"Shader compile error: {log}")
    return shader

def link_program(vs, fs):
    prog = glCreateProgram()
    glAttachShader(prog, vs)
    glAttachShader(prog, fs)
    glLinkProgram(prog)
    status = glGetProgramiv(prog, GL_LINK_STATUS)
    if not status:
        log = glGetProgramInfoLog(prog).decode()
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
        self.proj_plane_dist = (self.w / 2.0) / math.tan(self.half_fov)
        # Setup OpenGL context
        glViewport(0, 0, self.w, self.h)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        # Floor shader sources
        floor_vs = """
#version 120
attribute vec2 aPos;
varying vec2 vUV;
void main() {
    vUV = aPos;
    gl_Position = vec4(aPos, 0.0, 1.0);
}
"""
        floor_fs = """
#version 120
varying vec2 vUV;
uniform vec2 uRes;
uniform vec2 uPos;
uniform float uAng;
uniform float uHalfFov;
uniform float uPitch;
uniform sampler2D uFloorTex;
uniform sampler2D uCeilTex;
void main() {
    float fx = gl_FragCoord.x / uRes.x;
    float horizon = uRes.y * 0.5 + uPitch;
    // cast floor or ceiling depending on pixel row
    if (gl_FragCoord.y < horizon) {
        // floor
        float rowDist = (uRes.y * 0.5) / abs(gl_FragCoord.y - horizon);
        float cosA = cos(uAng);
        float sinA = sin(uAng);
        float planeX = -sinA * tan(uHalfFov);
        float planeY =  cosA * tan(uHalfFov);
        vec2 dir0 = vec2(cosA - planeX, sinA - planeY);
        vec2 dir1 = vec2(cosA + planeX, sinA + planeY);
        vec2 pos = uPos + rowDist * (dir0 + fx * (dir1 - dir0));
        vec2 texUV = fract(pos);
        gl_FragColor = texture2D(uFloorTex, texUV);
    } else {
        // ceiling
        float rowDist = (uRes.y * 0.5) / abs(gl_FragCoord.y - horizon);
        float cosA = cos(uAng);
        float sinA = sin(uAng);
        float planeX = -sinA * tan(uHalfFov);
        float planeY =  cosA * tan(uHalfFov);
        vec2 dir0 = vec2(cosA - planeX, sinA - planeY);
        vec2 dir1 = vec2(cosA + planeX, sinA + planeY);
        vec2 pos = uPos + rowDist * (dir0 + fx * (dir1 - dir0));
        vec2 texUV = fract(pos);
        gl_FragColor = texture2D(uCeilTex, texUV);
    }
}
"""
        # Compile and link floor shader
        vs = compile_shader(floor_vs, GL_VERTEX_SHADER)
        fs = compile_shader(floor_fs, GL_FRAGMENT_SHADER)
        self.floor_prog = link_program(vs, fs)
        # Get locations
        self.aPosLoc = glGetAttribLocation(self.floor_prog, "aPos")
        self.uResLoc = glGetUniformLocation(self.floor_prog, "uRes")
        self.uPosLoc = glGetUniformLocation(self.floor_prog, "uPos")
        self.uAngLoc = glGetUniformLocation(self.floor_prog, "uAng")
        self.uHalfFovLoc = glGetUniformLocation(self.floor_prog, "uHalfFov")
        self.uPitchLoc = glGetUniformLocation(self.floor_prog, "uPitch")
        self.uFloorTexLoc = glGetUniformLocation(self.floor_prog, "uFloorTex")
        self.uCeilTexLoc = glGetUniformLocation(self.floor_prog, "uCeilTex")
        # Full-screen quad VBO
        quad = np.array([-1.0, -1.0,
                          1.0, -1.0,
                         -1.0,  1.0,
                          1.0,  1.0], dtype=np.float32)
        self.quad_vbo = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.quad_vbo)
        glBufferData(GL_ARRAY_BUFFER, quad.nbytes, quad, GL_STATIC_DRAW)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        # Simple color shader for walls
        wall_vs = """
#version 120
attribute vec3 aPos;
attribute vec3 aColor;
varying vec3 vColor;
void main() {
    gl_Position = vec4(aPos, 1.0);
    vColor = aColor;
}
"""
        wall_fs = """
#version 120
varying vec3 vColor;
void main() {
    gl_FragColor = vec4(vColor, 1.0);
}
"""
        vs2 = compile_shader(wall_vs, GL_VERTEX_SHADER)
        fs2 = compile_shader(wall_fs, GL_FRAGMENT_SHADER)
        self.wall_prog = link_program(vs2, fs2)
        self.posAttr = glGetAttribLocation(self.wall_prog, "aPos")
        self.colAttr = glGetAttribLocation(self.wall_prog, "aColor")
        # VBOs for walls
        self.wall_vbo = glGenBuffers(1)
        self.color_vbo = glGenBuffers(1)
        # Load floor texture
        textures_dir = os.path.join(os.path.dirname(__file__), 'textures')
        path = os.path.join(textures_dir, FLOOR_TEXTURE_FILE)
        img = pygame.image.load(path).convert_alpha()
        tw, th = img.get_size()
        raw = pygame.image.tostring(img, "RGBA", True)
        self.floor_tex = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.floor_tex)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, tw, th, 0, GL_RGBA, GL_UNSIGNED_BYTE, raw)
        glBindTexture(GL_TEXTURE_2D, 0)
        # Compile textured wall shader
        tex_wall_vs = """
#version 120
attribute vec2 aPos;
attribute vec2 aUV;
varying vec2 vUV;
void main() {
    gl_Position = vec4(aPos, 0.0, 1.0);
    vUV = aUV;
}
"""
        tex_wall_fs = """
#version 120
varying vec2 vUV;
uniform sampler2D uWallTex;
void main() {
    gl_FragColor = texture2D(uWallTex, vUV);
}
"""
        vs3 = compile_shader(tex_wall_vs, GL_VERTEX_SHADER)
        fs3 = compile_shader(tex_wall_fs, GL_FRAGMENT_SHADER)
        self.wall_tex_prog = link_program(vs3, fs3)
        self.wall_pos2Attr = glGetAttribLocation(self.wall_tex_prog, "aPos")
        self.wall_uvAttr = glGetAttribLocation(self.wall_tex_prog, "aUV")
        self.uWallTexLoc = glGetUniformLocation(self.wall_tex_prog, "uWallTex")
        # VBO for textured walls
        self.wall_tex_vbo = glGenBuffers(1)
        # Load wall texture
        path_w = os.path.join(textures_dir, WALL_TEXTURE_FILE)
        img_w = pygame.image.load(path_w).convert_alpha()
        tw_w, th_w = img_w.get_size()
        raw_w = pygame.image.tostring(img_w, "RGBA", True)
        self.wall_tex = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.wall_tex)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, tw_w, th_w, 0, GL_RGBA, GL_UNSIGNED_BYTE, raw_w)
        glBindTexture(GL_TEXTURE_2D, 0)
        # Prepare UI overlay text (Press Q to quit)
        # Use Pygame font to render text into RGBA pixel data
        self.ui_font = pygame.font.SysFont(None, 24)
        ui_surf = self.ui_font.render("Press Q to quit", True, (255, 255, 255))
        self.ui_text_width, self.ui_text_height = ui_surf.get_size()
        self.ui_text_data = pygame.image.tostring(ui_surf, "RGBA", True)
        # Create GL texture for UI text
        self.ui_tex = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.ui_tex)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, self.ui_text_width, self.ui_text_height,
                     0, GL_RGBA, GL_UNSIGNED_BYTE, self.ui_text_data)
        glBindTexture(GL_TEXTURE_2D, 0)
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
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glDisable(GL_DEPTH_TEST)
        # Floor & ceiling pass
        glUseProgram(self.floor_prog)
        glUniform2f(self.uResLoc, float(self.w), float(self.h))
        glUniform2f(self.uPosLoc, player.x, player.y)
        glUniform1f(self.uAngLoc, player.angle)
        glUniform1f(self.uHalfFovLoc, self.half_fov)
        glUniform1f(self.uPitchLoc, player.pitch)
        # Bind floor texture to texture unit 0
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.floor_tex)
        glUniform1i(self.uFloorTexLoc, 0)
        # Bind ceiling texture to texture unit 1
        glActiveTexture(GL_TEXTURE1)
        glBindTexture(GL_TEXTURE_2D, self.ceil_tex)
        glUniform1i(self.uCeilTexLoc, 1)
        glBindBuffer(GL_ARRAY_BUFFER, self.quad_vbo)
        glEnableVertexAttribArray(self.aPosLoc)
        glVertexAttribPointer(self.aPosLoc, 2, GL_FLOAT, GL_FALSE, 0, ctypes.c_void_p(0))
        glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)
        glDisableVertexAttribArray(self.aPosLoc)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindTexture(GL_TEXTURE_2D, 0)
        glUseProgram(0)
        # Disable blending so walls render fully opaque over floor/ceiling
        glDisable(GL_BLEND)
        # Walls pass (textured)
        verts_uv = np.zeros((self.w * 6, 4), dtype=np.float32)
        idx = 0
        cos_pa = math.cos(player.angle)
        sin_pa = math.sin(player.angle)
        for i in range(self.w):
            off = -self.half_fov + i * (self.fov / self.w)
            dir_x = cos_pa * math.cos(off) - sin_pa * math.sin(off)
            dir_y = sin_pa * math.cos(off) + cos_pa * math.sin(off)
            map_x = int(player.x); map_y = int(player.y)
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
            hit = False; side = 0
            while not hit:
                if side_x < side_y:
                    side_x += delta_x; map_x += step_x; side = 0
                else:
                    side_y += delta_y; map_y += step_y; side = 1
                if world.map[map_y][map_x]:
                    hit = True
            if side == 0:
                perp = (map_x - player.x + (1 - step_x) / 2) / dir_x
            else:
                perp = (map_y - player.y + (1 - step_y) / 2) / dir_y
            perp *= math.cos(off); perp = max(perp, 1e-3)
            h_pixels = int(self.proj_plane_dist / perp)
            mid = self.h / 2 + player.pitch
            y0 = mid - h_pixels / 2.0
            y1 = mid + h_pixels / 2.0
            # Convert screen coords to NDC
            inv_h = 1.0 / (self.h - 1.0)
            y0_ndc = (y0 * inv_h) * 2.0 - 1.0
            y1_ndc = (y1 * inv_h) * 2.0 - 1.0
            inv_w = 1.0 / (self.w - 1.0)
            x0_ndc = (i * inv_w) * 2.0 - 1.0
            x1_ndc = ((i + 1) * inv_w) * 2.0 - 1.0
            if side == 0:
                wallX = player.y + perp * dir_y
            else:
                wallX = player.x + perp * dir_x
            u = wallX - math.floor(wallX)
            # First triangle
            verts_uv[idx]     = [x0_ndc, y1_ndc, u, 1.0]; idx += 1
            verts_uv[idx]     = [x0_ndc, y0_ndc, u, 0.0]; idx += 1
            verts_uv[idx]     = [x1_ndc, y0_ndc, u, 0.0]; idx += 1
            # Second triangle
            verts_uv[idx]     = [x1_ndc, y0_ndc, u, 0.0]; idx += 1
            verts_uv[idx]     = [x1_ndc, y1_ndc, u, 1.0]; idx += 1
            verts_uv[idx]     = [x0_ndc, y1_ndc, u, 1.0]; idx += 1
        # Upload and render textured walls
        glUseProgram(self.wall_tex_prog)
        glBindBuffer(GL_ARRAY_BUFFER, self.wall_tex_vbo)
        glBufferData(GL_ARRAY_BUFFER, verts_uv.nbytes, verts_uv, GL_DYNAMIC_DRAW)
        stride = verts_uv.strides[0]
        glEnableVertexAttribArray(self.wall_pos2Attr)
        glVertexAttribPointer(self.wall_pos2Attr, 2, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(0))
        glEnableVertexAttribArray(self.wall_uvAttr)
        glVertexAttribPointer(self.wall_uvAttr, 2, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(8))
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.wall_tex)
        glUniform1i(self.uWallTexLoc, 0)
        glDrawArrays(GL_TRIANGLES, 0, self.w * 6)
        # UI overlay: textured quad (Press Q to quit)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        # Calculate quad corners in NDC for UI position 10px from top-left
        px, py = 10, self.h - 10 - self.ui_text_height
        inv_w = 1.0 / (self.w - 1.0)
        inv_h = 1.0 / (self.h - 1.0)
        x0 = px * inv_w * 2.0 - 1.0
        x1 = (px + self.ui_text_width) * inv_w * 2.0 - 1.0
        y0 = py * inv_h * 2.0 - 1.0
        y1 = (py + self.ui_text_height) * inv_h * 2.0 - 1.0
        # Build vertex array: [pos.x, pos.y, uv.x, uv.y]
        ui_verts = np.array([
            [x0, y0, 0.0, 0.0],
            [x1, y0, 1.0, 0.0],
            [x1, y1, 1.0, 1.0],
            [x0, y0, 0.0, 0.0],
            [x1, y1, 1.0, 1.0],
            [x0, y1, 0.0, 1.0],
        ], dtype=np.float32)
        # Render UI quad with wall texture program
        glUseProgram(self.wall_tex_prog)
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
        glUseProgram(0)
        # Swap buffers
        pygame.display.flip()