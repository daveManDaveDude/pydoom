"""
Helper functions and classes for OpenGL setup, shader compilation, and texture loading.
"""

from __future__ import annotations
import logging
import pygame
import OpenGL.GL as gl  # noqa: N811
from typing import Optional

logger = logging.getLogger(__name__)


class ShaderProgram:
    """
    Encapsulates an OpenGL shader program (vertex + fragment).
    Handles compilation, linking, and provides convenience methods.
    """

    def __init__(
        self,
        vertex_source: Optional[str] = None,
        fragment_source: Optional[str] = None,
        vertex_path: Optional[str] = None,
        fragment_path: Optional[str] = None,
    ) -> None:
        # Load sources from files if paths provided
        if vertex_path:
            with open(vertex_path, "r") as f:
                vertex_source = f.read()
        if fragment_path:
            with open(fragment_path, "r") as f:
                fragment_source = f.read()
        if vertex_source is None or fragment_source is None:
            raise ValueError(
                "Vertex and fragment shader sources must be provided"
            )
        # Compile shaders
        vs = self._compile_shader(vertex_source, gl.GL_VERTEX_SHADER)
        fs = self._compile_shader(fragment_source, gl.GL_FRAGMENT_SHADER)
        # Link program
        self.id = self._link_program(vs, fs)

    def _compile_shader(self, source: str, shader_type: int) -> int:
        shader = gl.glCreateShader(shader_type)
        gl.glShaderSource(shader, source)
        gl.glCompileShader(shader)
        status = gl.glGetShaderiv(shader, gl.GL_COMPILE_STATUS)
        if not status:
            log = gl.glGetShaderInfoLog(shader).decode()
            logger.error("Shader compile failed: %s", log)
            raise RuntimeError(f"Shader compile error: {log}")
        return shader

    def _link_program(self, vs: int, fs: int) -> int:
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

    def use(self) -> None:
        gl.glUseProgram(self.id)

    def stop(self) -> None:
        gl.glUseProgram(0)

    def get_attrib(self, name: str) -> int:
        return gl.glGetAttribLocation(self.id, name)

    def get_uniform(self, name: str) -> int:
        return gl.glGetUniformLocation(self.id, name)


def setup_opengl(width: int, height: int) -> None:
    """
    Configure basic OpenGL state (viewport, depth testing, blending).
    """
    gl.glViewport(0, 0, width, height)
    gl.glEnable(gl.GL_DEPTH_TEST)
    gl.glEnable(gl.GL_BLEND)
    gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)


def load_texture(
    path: str,
    wrap_s: int = gl.GL_REPEAT,
    wrap_t: int = gl.GL_REPEAT,
    min_filter: int = gl.GL_LINEAR,
    mag_filter: int = gl.GL_LINEAR,
) -> int:
    """
    Load an image file via Pygame and upload as an OpenGL texture.
    Returns the texture ID.
    """
    img = pygame.image.load(path).convert_alpha()
    tw, th = img.get_size()
    raw = pygame.image.tostring(img, "RGBA", True)
    tex = gl.glGenTextures(1)
    gl.glBindTexture(gl.GL_TEXTURE_2D, tex)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, min_filter)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, mag_filter)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, wrap_s)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, wrap_t)
    gl.glTexImage2D(
        gl.GL_TEXTURE_2D,
        0,
        gl.GL_RGBA,
        tw,
        th,
        0,
        gl.GL_RGBA,
        gl.GL_UNSIGNED_BYTE,
        raw,
    )
    gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
    return tex


def create_texture_from_surface(
    surf: pygame.Surface,
    wrap_s: int = gl.GL_CLAMP_TO_EDGE,
    wrap_t: int = gl.GL_CLAMP_TO_EDGE,
    min_filter: int = gl.GL_LINEAR,
    mag_filter: int = gl.GL_LINEAR,
) -> int:
    """
    Create an OpenGL texture from a Pygame Surface (e.g., for UI text).
    """
    data = pygame.image.tostring(surf, "RGBA", True)
    w, h = surf.get_size()
    tex = gl.glGenTextures(1)
    gl.glBindTexture(gl.GL_TEXTURE_2D, tex)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, min_filter)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, mag_filter)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, wrap_s)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, wrap_t)
    gl.glTexImage2D(
        gl.GL_TEXTURE_2D,
        0,
        gl.GL_RGBA,
        w,
        h,
        0,
        gl.GL_RGBA,
        gl.GL_UNSIGNED_BYTE,
        data,
    )
    gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
    return tex
