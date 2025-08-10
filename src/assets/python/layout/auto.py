from io import StringIO
class Auto:
    def __init__(self, coord, signal, direction):
        self.coord = coord
        self.signal = signal
        self.direction = direction
    
    def pressed(self, text, game):
        x,y = self.coord
        self.signal.auto = True
        f = StringIO(text)
        lines = f.readlines()
        grid = [list(line.rstrip('\n')) for line in lines]
        # Change the character (safely)
        if 0 <= y < len(grid) and 0 <= x < len(grid[y]):
            grid[y][x] = 'q'
        self.signal.auto = True
        # Convert back to string
        new_text = '\n'.join(''.join(line) for line in grid)
        game.text = new_text
    
    def depressed(self, text, game):
        x,y = self.coord
        self.signal.auto = True
        f = StringIO(text)
        lines = f.readlines()
        grid = [list(line.rstrip('\n')) for line in lines]
        # Change the character (safely)
        if 0 <= y < len(grid) and 0 <= x < len(grid[y]):
            grid[y][x] = 'p'
        self.signal.auto = False
        # Convert back to string
        new_text = '\n'.join(''.join(line) for line in grid)
        game.text = new_text