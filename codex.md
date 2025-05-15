
In this plan, we will add enemy sprites that actively chase the player while avoiding walls. The solution uses a grid-based pathfinding approach, since the game world is a tile grid. By treating the map as a grid of walkable and blocked cells, we can simplify navigation and ensure enemies find valid routes around obstacles A pathfinding is a well-established choice for game AI because it efficiently finds shortest paths by combining travel cost and heuristic estimates. Enemies will move continuously in the 3D world but use the grid path as a guide for direction. This avoids the complexity of continuous obstacle avoidance, while guaranteeing that movement is collision-free. We will also implement a teleportation (respawn) mechanic: if an enemy touches the player, it instantly relocates to a random valid spawn position (on an open floor tile, not inside a wall or the player). 

The steps reak down tt break down the implementation in detail are provided in this ands futuire prompts.

Always ensure that you leave woirking software, every time you finsih we should have code that at gthe very leasty compiles

