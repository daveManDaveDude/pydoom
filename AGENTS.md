# Repository Guidelines

## Project Structure & Module Organization
- Source: `game/`
  - Core: `game.py`, `player.py`, `world.py`, `enemy.py`, `bullet.py`
  - Rendering: `renderer.py`, `wall_renderer.py`, `gl_utils.py`, `gl_resources.py`, `shaders/`, `textures/`
  - Data: `worlds/` (JSON maps)
- Entry point: `main.py`
- Tests: `tests/` (pytest, `test_*.py`)

## Build, Test, and Development Commands
- Create venv and install deps:
  - `python -m venv .venv && source .venv/bin/activate`
  - `pip install pygame PyOpenGL PyOpenGL_accelerate numpy pytest black`
- Run game locally: `python main.py`
- Run tests: `pytest -q`
- Format code: `black . -l 80`

## Coding Style & Naming Conventions
- Python 3.8+; format with `black` (line length 80, see `pyproject.toml`).
- Use type hints and docstrings; prefer `snake_case` for functions/variables and `lower_snake` for modules.
- Keep functions small and focused; extract helpers when math/GL logic repeats.
- Prefer dataclasses for simple data containers (`Door`, `Enemy`, `Player`).
- Avoid direct access to private attributes; add small APIs instead (e.g., resource registration).

## Testing Guidelines
- Framework: `pytest`. Place tests in `tests/` named `test_*.py`.
- Keep tests headless: stub Pygame/GL as in `tests/test_fixes.py` using `monkeypatch`.
- Test logic at module boundaries (world/doors, pathfinding, input, physics) and avoid real GL contexts.
- Run `pytest -q` before pushing; add minimal fixtures for new subsystems.

## Commit & Pull Request Guidelines
- Commits: short, imperative subject (<=72 chars), optional scope (e.g., `world: door lookup map`), body explains why + notable trade‑offs.
- PRs: include description, motivation/approach, before/after notes (screenshots or GIFs if visual), and test plan. Reference issues (e.g., `Closes #123`).
- Keep diffs surgical; avoid unrelated formatting.

## Security & Configuration Tips
- No secrets in repo. Assets live in `game/textures/`; keep binaries small.
- OpenGL requires a working GPU/driver. For CI or headless, rely on stubs and unit tests; do not initialize real GL in tests.
