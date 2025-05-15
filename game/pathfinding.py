"""
Pathfinding utilities: implements grid-based A* search.
"""
import heapq

def heuristic(a, b):
    """Manhattan distance heuristic for grid."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])

def find_path(start, goal, world):
    """
    Find a path on a grid-based world from start to goal using A*.
    start, goal: (x, y) tuples of integer grid coordinates.
    world: object with is_wall(x, y) -> bool indicating walls or out-of-bounds.
    Returns list of (x, y) coordinates from start to goal inclusive, or empty list if no path.
    """
    # Convert to integer grid positions
    start = (int(start[0]), int(start[1]))
    goal = (int(goal[0]), int(goal[1]))

    # If goal is not walkable, no path
    if world.is_wall(goal[0], goal[1]):
        return []

    # A* open set as a priority queue of (f_score, count, node)
    open_set = []
    count = 0
    # G cost from start to node
    g_score = {start: 0}
    # For path reconstruction
    came_from = {}

    # Initial f score
    f0 = heuristic(start, goal)
    heapq.heappush(open_set, (f0, count, start))
    # Closed set of visited nodes
    closed = set()

    while open_set:
        _, _, current = heapq.heappop(open_set)
        # If reached goal, reconstruct path
        if current == goal:
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            return path

        if current in closed:
            continue
        closed.add(current)

        x0, y0 = current
        # Explore 4-directional neighbors
        for dx, dy in ((1,0), (-1,0), (0,1), (0,-1)):
            neighbor = (x0 + dx, y0 + dy)
            # Skip walls or already visited
            if world.is_wall(neighbor[0], neighbor[1]) or neighbor in closed:
                continue
            tentative_g = g_score[current] + 1
            # If this path to neighbor is better than any previous one
            if tentative_g < g_score.get(neighbor, float('inf')):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f_score = tentative_g + heuristic(neighbor, goal)
                count += 1
                heapq.heappush(open_set, (f_score, count, neighbor))

    # No path found
    return []