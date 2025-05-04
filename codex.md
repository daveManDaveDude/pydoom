Current project status
    •  Window, input, game loop, world-loader, player and collision all wired up.
    •  OpenGL renderer that
      – draws a textured floor & ceiling in a single full-screen shader pass
      – raycasts walls on the CPU (DDA) and renders them as textured GL_TRIANGLES
      – overlays simple UI text
    •  Configuration (FOV, speeds, textures, JSON map) is all externalized

    next steps

        1. Sprite & object support
           – Implement a “billboard” sprite renderer (e.g. for pickups, enemies)
           – Extend your world-JSON format to include object spawns (x,y,type)
           – Sort sprites by depth each frame and render as textured quads
        2. Map & texture variety
           – Allow different wall/floor/ceiling textures per cell (use map values >1 → texture index)
           – Support multiple map files and a level-select menu
        3. Mini-map / debug view
           – Top-down 2D overlay in a corner, showing walls, player position & FOV
           – Toggle with a key for easier level design & debugging
        4. HUD & crosshair
           – Draw a simple crosshair at screen center (in GL or as a 2D overlay)
           – Show FPS, player coordinates, health/ammo bars (prepare for gameplay)
        5. Audio & feedback
           – Integrate Pygame’s mixer: footsteps, ambient track, weapon sounds
           – Add a “footstep” timer based on move distance for more immersion
        6. Doors & level interactions
           – Define doors in the map that can open (e.g. animate a textured quad sliding up)
           – Trigger via “use” key, with collision temporarily disabled
        7. Basic enemy AI & combat
           – Place simple AI agents that patrol or chase the player
           – Implement a shooting mechanic (raycast or projectile), damage, and health
           – Sprite-based enemies with simple finite-state logic
        8. Performance & refactoring
           – Move wall-casting into a GLSL shader (true GPU raymarch) or batch your CPU data better
           – Break the code into “engine” vs “game” modules (renderers, world, entities, UI)
           – Add unit tests for map loading, collision, raycasting math
           – Profile hot spots (NumPy vs pure Python wall loops)
        9. Project hygiene & packaging
           – Add a README with controls, dependencies (Pygame, PyOpenGL, NumPy)
           – requirements.txt / setup.py for easy installs
           – Pre-commit hooks / CI to lint, run smoke tests
           – Document the JSON world format (schema, examples)