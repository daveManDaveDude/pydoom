import math
import logging
import pytest


@pytest.fixture(autouse=True)
def stub_pygame_and_renderer(monkeypatch):
    """Stub out pygame display, mouse, clock and the OpenGL-based Renderer to allow Game init."""
    import pygame

    # Stub Pygame init and display functions
    monkeypatch.setattr(pygame, "init", lambda: None)
    monkeypatch.setattr(
        pygame.display, "set_mode", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        pygame.display, "set_caption", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        pygame.mouse, "set_visible", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(pygame.event, "set_grab", lambda *args, **kwargs: None)
    monkeypatch.setattr(pygame.mouse, "get_rel", lambda *args, **kwargs: (0, 0))

    # Stub clock to avoid real timing
    class DummyClock:
        def tick(self, fps):
            return 0

    monkeypatch.setattr(pygame.time, "Clock", DummyClock)
    # Stub Renderer to avoid OpenGL in tests
    import game.renderer as gr

    # Stub Renderer signature to match current parameters (step_size instead of step)
    monkeypatch.setattr(
        gr,
        "Renderer",
        lambda w, h, fov, step_size, world: type(
            "R",
            (),
            {
                "shutdown": lambda self: None,
                "render": lambda self, s, w, p: None,
            },
        )(),
    )


def test_game_default_angle_radians():
    from game.game import Game

    game = Game()
    # The default player angle should be pi radians (180 degrees)
    assert math.isclose(game.player.angle, math.pi, rel_tol=1e-9)


def test_default_powerup_angle_radians():
    from game.world import World

    world = World()
    # default.json specifies angle=45 degrees; should be converted to radians
    expected = math.radians(45.0)
    assert math.isclose(world.powerup_angle, expected, rel_tol=1e-9)


def test_renderer_logger_defined():
    import game.renderer as renderer

    # logger should be initialized in renderer module to avoid NameError
    assert hasattr(renderer, "logger")
    assert isinstance(renderer.logger, logging.Logger)
