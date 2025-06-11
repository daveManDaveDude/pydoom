"""
Input handling abstraction to decouple Pygame input from game logic.
"""

from __future__ import annotations
import pygame
from typing import Sequence, Tuple


class InputHandler:
    """
    Abstraction for gathering input state. Processes Pygame events and
    provides key states, mouse movement, and action queries.
    """

    def __init__(self) -> None:
        self._quit = False
        self._fire = False
        # Toggle door debug overlay (Shift+D)
        self._toggle_door_debug = False
        # Toggle pause state (P key)
        self._pause = False
        self._mouse_rel: Tuple[int, int] = (0, 0)
        # Key state and mouse movement are initialized in process_events()
        self._keys: Sequence[bool] = ()

    def process_events(self) -> None:
        """
        Poll Pygame events, update internal state for quit and fire actions,
        and capture mouse relative movement and key states.
        """
        self._quit = False
        self._fire = False
        self._toggle_door_debug = False
        self._pause = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._quit = True
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_x:
                    self._quit = True
                elif event.key == pygame.K_SPACE:
                    self._fire = True
                elif event.key == pygame.K_d and (
                    event.mod & pygame.KMOD_SHIFT
                ):
                    # Toggle door debug lines
                    self._toggle_door_debug = True
                elif event.key == pygame.K_p:
                    # Toggle pause
                    self._pause = True
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._fire = True
        # Update continuous states
        self._keys = pygame.key.get_pressed()
        self._mouse_rel = pygame.mouse.get_rel()

    def should_quit(self) -> bool:
        """Return True if a quit command was issued this frame."""
        return self._quit

    def toggle_debug_doors_pressed(self) -> bool:
        """Return True if Shift+D was pressed this frame to toggle door debug overlay."""
        return self._toggle_door_debug

    def pause_pressed(self) -> bool:
        """Return True if P key was pressed this frame to toggle pause state."""
        return self._pause

    def fire_pressed(self) -> bool:
        """Return True if fire action (space or left click) occurred this frame."""
        return self._fire

    def get_key_state(self) -> Sequence[bool]:
        """Return the current pressed state for all keys."""
        return self._keys

    def get_mouse_rel(self) -> Tuple[int, int]:
        """Return mouse movement delta since last call to process_events."""
        return self._mouse_rel
