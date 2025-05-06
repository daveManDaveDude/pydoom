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

    def gen(self, creator: Callable[[], int], deleter: Callable[[int], None]) -> int:
        """Wraps any glGen* that returns ONE uint id."""
        obj_id: int = creator()
        self._objs[deleter].append(obj_id)
        return obj_id

    @contextlib.contextmanager
    def bind(self, binder: Callable[[int], None], obj_id: int):
        """Context-manager for glBind*, auto-unbinds to 0."""
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