import OpenGL.GL as gl
from game.gl_resources import GLResourceManager

def test_manager_tracks_and_deletes(monkeypatch):
    mgr = GLResourceManager()
    created = []
    deleted = []

    # Monkey-patch glGenTextures to simulate creation of texture IDs
    monkeypatch.setattr(gl, "glGenTextures", lambda: len(created) + 42)
    # Monkey-patch glDeleteTextures to record deletions
    monkeypatch.setattr(gl, "glDeleteTextures", lambda i: deleted.append(i))

    # Generate two textures
    tid1 = mgr.gen(gl.glGenTextures, gl.glDeleteTextures)
    tid2 = mgr.gen(gl.glGenTextures, gl.glDeleteTextures)
    created.extend([tid1, tid2])

    # Ensure resources are tracked
    assert mgr._objs[gl.glDeleteTextures] == created
    # Perform shutdown and verify all deletes are called
    mgr.shutdown()
    assert deleted == created