class World:
    """World map representation."""
    def __init__(self, map_grid=None):
        # Default 10x10 map
        if map_grid is None:
            self.map = [
                [1,1,1,1,1,1,1,1,1,1],
                [1,0,0,0,0,0,0,0,0,1],
                [1,0,1,0,1,1,1,0,0,1],
                [1,0,1,0,0,0,1,0,0,1],
                [1,0,1,1,1,0,1,1,0,1],
                [1,0,0,0,1,0,0,0,0,1],
                [1,0,1,0,1,1,1,0,0,1],
                [1,0,1,0,0,0,1,0,0,1],
                [1,0,0,0,0,0,0,0,0,1],
                [1,1,1,1,1,1,1,1,1,1],
            ]
        else:
            self.map = map_grid
        self.height = len(self.map)
        self.width = len(self.map[0]) if self.height > 0 else 0

    def is_wall(self, x, y):
        """Return True if (x, y) is a wall or out of bounds."""
        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            return True
        return self.map[int(y)][int(x)] == 1