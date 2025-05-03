"""
Helper functions and classes for OpenGL setup, shader compilation, and texture loading.
"""
import logging
import pygame
from OpenGL.GL import *

logger = logging.getLogger(__name__)

class ShaderProgram:
    """
    Encapsulates an OpenGL shader program (vertex + fragment).
    Handles compilation, linking, and provides convenience methods.
    """
    def __init__(self, vertex_source=None, fragment_source=None,
                 vertex_path=None, fragment_path=None):
        # Load sources from files if paths provided
        if vertex_path:
            with open(vertex_path, 'r') as f:
                vertex_source = f.read()
        if fragment_path:
            with open(fragment_path, 'r') as f:
                fragment_source = f.read()
        if vertex_source is None or fragment_source is None:
            raise ValueError("Vertex and fragment shader sources must be provided")
        # Compile shaders
        vs = self._compile_shader(vertex_source, GL_VERTEX_SHADER)
        fs = self._compile_shader(fragment_source, GL_FRAGMENT_SHADER)
        # Link program
        self.id = self._link_program(vs, fs)

    def _compile_shader(self, source, shader_type):
        shader = glCreateShader(shader_type)
        glShaderSource(shader, source)
        glCompileShader(shader)
        status = glGetShaderiv(shader, GL_COMPILE_STATUS)
        if not status:
            log = glGetShaderInfoLog(shader).decode()
            logger.error("Shader compile failed: %s", log)
            raise RuntimeError(f"Shader compile error: {log}")
        return shader

    def _link_program(self, vs, fs):
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

    def use(self):
        glUseProgram(self.id)

    def stop(self):
        glUseProgram(0)

    def get_attrib(self, name):
        return glGetAttribLocation(self.id, name)

    def get_uniform(self, name):
        return glGetUniformLocation(self.id, name)

def setup_opengl(width, height):
    """
    Configure basic OpenGL state (viewport, depth testing, blending).
    """
    glViewport(0, 0, width, height)
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

def load_texture(path, wrap_s=GL_REPEAT, wrap_t=GL_REPEAT,
                 min_filter=GL_LINEAR, mag_filter=GL_LINEAR):
    """
    Load an image file via Pygame and upload as an OpenGL texture.
    Returns the texture ID.
    """
    img = pygame.image.load(path).convert_alpha()
    tw, th = img.get_size()
    raw = pygame.image.tostring(img, "RGBA", True)
    tex = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, min_filter)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, mag_filter)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, wrap_s)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, wrap_t)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, tw, th, 0, GL_RGBA, GL_UNSIGNED_BYTE, raw)
    glBindTexture(GL_TEXTURE_2D, 0)
    return tex

def create_texture_from_surface(surf, wrap_s=GL_CLAMP, wrap_t=GL_CLAMP,
                                min_filter=GL_LINEAR, mag_filter=GL_LINEAR):
    """
    Create an OpenGL texture from a Pygame Surface (e.g., for UI text).
    """
    data = pygame.image.tostring(surf, "RGBA", True)
    w, h = surf.get_size()
    tex = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, min_filter)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, mag_filter)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, wrap_s)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, wrap_t)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, data)
    glBindTexture(GL_TEXTURE_2D, 0)
    return tex