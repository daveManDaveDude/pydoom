# pydoom

A Python‑based “Doom‑like” prototype built with Pygame and PyOpenGL. Explore a simple 3D maze rendered with GPU shaders, textured walls, floor, ceiling and animated sprites.

The entire project including this readme have been created by ai using chat GPT and codex cli. I have so far spent $30 in API costs and so am pausing for now.

---

## Features

- **First‑person 3D raycasting** with OpenGL shaders
- Textured walls, floors & ceilings
- Billboard sprites (e.g. rotating power‑ups)
- Configurable world maps (JSON)
- Smooth mouse‑look and keyboard movement
- Modular design (World, Player, Renderer, etc.)

---

## Requirements

- **Python 3.8+**
- [pygame](https://pypi.org/project/pygame/)
- [PyOpenGL](https://pypi.org/project/PyOpenGL/)
- (Optional) `PyOpenGL_accelerate` for performance
- (Dev) **black** for code formatting

Install dependencies with:

```bash
pip install pygame PyOpenGL PyOpenGL_accelerate numpy
```

To install development tools:

```bash
pip install black
```

---

## Getting Started

1. **Clone the repo**
   ```bash
   git clone https://github.com/daveManDaveDude/pydoom.git
   cd pydoom
   ```
2. **Run the game**
   ```bash
   python main.py
   ```

---

## Development

Format the code with black according to the configuration in `pyproject.toml`:

```bash
black . -l 80
```

---

## Configuration

Most settings are in `game/config.py`:

- **Screen**
  - `SCREEN_WIDTH`, `SCREEN_HEIGHT`, `FPS`
- **Player**
  - `MOVE_SPEED`, `ROT_SPEED`
- **Mouse**
  - `MOUSE_SENSITIVITY`, `MOUSE_SENSITIVITY_Y`, `MAX_PITCH`
- **Textures & World**
  - `FLOOR_TEXTURE_FILE`, `WALL_TEXTURE_FILE`, etc.
  - `WORLD_FILE` points to a JSON map in `game/worlds/` (must exist and define a 2D `map` array)
- **Map Tiles**
  - `TILE_EMPTY` (0), `TILE_WALL` (1) for future tile-type extensions

---

## Controls

-- **W / Up Arrow**: Move forward
-- **S / Down Arrow**: Move backward
-- **A / Left Arrow**: Strafe left
-- **D / Right Arrow**: Strafe right
-- **Mouse**: Look around (yaw & pitch)
-- **Spacebar** or **Left Click**: Fire bullet
-- **P**: Toggle pause/unpause
-- **X** key or window close: Quit

---

## Project Structure

```
pydoom/
├── game/
│   ├── config.py           # Constants & settings
│   ├── game.py             # Main loop & high‑level coordination
│   ├── player.py           # Player state & movement logic
│   ├── world.py            # Map loading & collision
│   ├── renderer.py         # OpenGL‑based rendering
│   ├── wall_renderer.py    # CPU-based wall casting implementation
│   ├── gl_utils.py         # Shader & texture helpers
│   ├── gl_resources.py     # Resource manager for GL objects
│   ├── shaders/            # GLSL shader sources
│   ├── textures/           # PNG assets (walls, floor, sprites…)
│   └── worlds/             # Sample map layouts
│       └── default.json    # Sample map layout
├── main.py                 # Entry point
├── .gitignore
└── README.md               # ← You are here
```

---

## Custom Maps & Assets

- **Maps**: Add or modify JSON files under `game/worlds/`. A map JSON should define a 2D grid (`map`) and optional `powerup` or `sprites` entries.
- **Textures**: Place new `.png` files in `game/textures/` and update `config.py` to point at them.
---

## Testing

Run the full test suite with pytest from the project root:

```bash
pytest -q
```

---

## Contributing

1. Fork the project
2. Create a feature branch (`git checkout -b feature/YourFeature`)
3. Commit your changes
4. Push to your branch & open a Pull Request.
5. If possible don't write any code yourself, lets see how far we can take 100% AI driven development!

---

## License

Open Source MIT licence

---

## Contact

For questions or suggestions, open an issue or reach out via GitHub discussions.
