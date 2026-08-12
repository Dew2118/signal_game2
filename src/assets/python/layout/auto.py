from io import StringIO
class Auto:
    def __init__(self, coord, signal, direction):
        self.coord = coord
        self.signal = signal
        self.direction = direction
        self.colored = False
    
    def pressed(self, game):
        x,y = self.coord
        self.signal.auto = True
        if 0 <= y < len(game.lines) and 0 <= x < len(game.lines[y]):
            game.lines[y][x] = 'q'
        self.signal.auto = True
        # Convert back to string
        print("Auto button pressed at", self.coord)
        
    def depressed(self, game):
        x,y = self.coord
        self.signal.auto = True
        if 0 <= y < len(game.lines) and 0 <= x < len(game.lines[y]):
            game.lines[y][x] = 'p'
        self.signal.auto = False