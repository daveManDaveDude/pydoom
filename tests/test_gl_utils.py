import pytest
import OpenGL.GL as gl

import game.gl_utils as gu


def test_shaderprogram_requires_sources():
    # Missing vertex or fragment source should raise ValueError
    with pytest.raises(ValueError):
        gu.ShaderProgram(vertex_source=None, fragment_source="f")
    with pytest.raises(ValueError):
        gu.ShaderProgram(vertex_source="v", fragment_source=None)


def test_setup_opengl_calls(monkeypatch):
    calls = []
    monkeypatch.setattr(
        gl,
        "glViewport",
        lambda x, y, w, h: calls.append(("viewport", x, y, w, h)),
    )
    monkeypatch.setattr(
        gl, "glEnable", lambda flag: calls.append(("enable", flag))
    )
    monkeypatch.setattr(
        gl, "glBlendFunc", lambda sf, df: calls.append(("blendfunc", sf, df))
    )

    gu.setup_opengl(10, 20)
    assert ("viewport", 0, 0, 10, 20) in calls
    assert ("enable", gl.GL_DEPTH_TEST) in calls
    assert ("enable", gl.GL_BLEND) in calls
    assert ("blendfunc", gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA) in calls
