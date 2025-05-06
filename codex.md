
Refactor every wildcard OpenGL import
Create a systematic resource‑lifecycle layer so all GL objects that you create are reliably freed (VAOs, VBOs, textures, frame‑buffers, shader programs).
Feel free to copy this verbatim into the assistant—everything is broken down into clear, testable tasks.

📂 0 – Scope & constraints

Target branch: feature/gl‑imports‑cleanup
Python ≥ 3.10, keep PyOpenGL.
No functional changes (the game must run exactly as before).
Add/modify unit tests only for the new resource‑manager module.
🪄 1 – Replace wildcard imports

1.1 Search‑and‑replace
grep -R "from OpenGL.GL import \*" pydoom/
1.2 For every match:
Delete the line.
Insert the canonical import once per file:
import OpenGL.GL as gl  # noqa: N811  (ignore pep8‑naming rule for module alias)
Qualify every GL symbol in that file with gl. (case‑sensitive).
e.g. glBindTexture → gl.glBindTexture, GL_FLOAT → gl.GL_FLOAT.
1.3 Add [ruff] rule I252 to disallow future wildcard imports (edit pyproject.toml).
1.4 Run ruff --fix and black . to auto‑format.
🗂️ 2 – Central GL resource manager

2.1 Create pydoom/gl_resources.py
from __future__ import annotations

import contextlib
import OpenGL.GL as gl
from collections import defaultdict
from typing import Callable, DefaultDict, List

class GLResourceManager:
    """
    Tracks every GL object created at runtime and frees it on shutdown.

    Usage:
        mgr = GLResourceManager()
        tex = mgr.gen(gl.glGenTextures, gl.glDeleteTextures)
        ...
        mgr.shutdown()
    """

    def __init__(self) -> None:
        self._objs: DefaultDict[Callable[[int], None], List[int]] = defaultdict(list)

    # ---------- public helpers ----------

    def gen(self, creator: Callable[[], int], deleter: Callable[[int], None]) -> int:
        """Wraps any glGen* that returns ONE uint id."""
        obj_id: int = creator()
        self._objs[deleter].append(obj_id)
        return obj_id

    @contextlib.contextmanager
    def bind(self, binder: Callable[[int], None], obj_id: int):
        """Context‑manager for glBind*, auto‑unbinds to 0."""
        binder(obj_id)
        try:
            yield
        finally:
            binder(0)

    def shutdown(self) -> None:
        """Call at program exit **WITH A VALID GL CONTEXT**."""
        for deleter, ids in self._objs.items():
            for obj_id in ids:
                deleter(int(obj_id))
        self._objs.clear()
Notes

Only handles single‑ID creators; extend easily for tuples (e.g. cubemaps) when needed.
Cheap: just two dict look‑ups per allocation.
2.2 Integrate into renderer.py
from pydoom.gl_resources import GLResourceManager
Add self._res = GLResourceManager() in Renderer.__init__.
Replace every gl.glGenTextures(1) pattern:
# before
self._tex = gl.glGenTextures(1)

# after
self._tex = self._res.gen(lambda: gl.glGenTextures(1), gl.glDeleteTextures)
Same for VAOs, VBOs, FBOs, shader programs, render‑buffers.
Add explicit cleanup call:
def shutdown(self):
    self._res.shutdown()
2.3 Wire shutdown from Game.quit()
def quit(self):
    self.renderer.shutdown()
    pygame.quit()
    sys.exit()
2.4 Optional: emphasise RAII with __del__
In each resource‑owning class (e.g. ShaderProgram, Texture2D) add:

def __del__(self):
    # Still safe if GL context already gone – glDelete* silently no‑ops
    gl.glDeleteProgram(self._handle)
…but the manager above already covers most use‑cases, so this is just defence‑in‑depth.

🧪 3 – Unit tests (headless)

3.1 Install [pytest‑pygame] to get a dummy SDL video driver.
3.2 Create tests/test_gl_resources.py
import OpenGL.GL as gl
from pydoom.gl_resources import GLResourceManager

def test_manager_tracks_and_deletes(monkeypatch):
    mgr = GLResourceManager()
    created = []
    deleted = []

    monkeypatch.setattr(gl, "glGenTextures", lambda: len(created) + 42)
    monkeypatch.setattr(gl, "glDeleteTextures", lambda i: deleted.append(i))

    tid1 = mgr.gen(gl.glGenTextures, gl.glDeleteTextures)
    tid2 = mgr.gen(gl.glGenTextures, gl.glDeleteTextures)
    created.extend([tid1, tid2])

    assert mgr._objs[gl.glDeleteTextures] == created
    mgr.shutdown()
    assert deleted == created
Run with pytest -q.

🏁 4 – Finish line

pytest, ruff, mypy all green.
Manual play‑test: python -m pydoom.main runs and exits without GL errors.
Open a pull‑request, tag reviewers, and reference “Fixes #<issue‑id>”.
Deliverables

Modified source files with explicit import OpenGL.GL as gl
pydoom/gl_resources.py
Tests proving that GLResourceManager frees everything
Updated CI config (ruff rule + test run)
That’s it! Hand these instructions to the assistant and it should be able to implement the refactor confidently and safely.
