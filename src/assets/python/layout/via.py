class ViaButton:
    def __init__(self, coord):
        self.coord = coord                      # (x, y) of the 'q' character
        self.track_coord = (coord[0], coord[1] + 1)  # (x, y + 1) track character 'a' directly below
        self.flash_coord = (coord[0], coord[1] + 1)  # Tile that flashes on screen
        self.flash_original_color = None
        self.colored = False

    def prepare_flash(self, display, lines):
        if self.flash_original_color is not None:
            return
        x, y = self.flash_coord
        current_color = display.get_char_color_at_coord(x, y, lines)
        self.flash_original_color = current_color if current_color is not None else (128, 128, 128)

    def clear_flash(self, display, lines):
        if self.flash_original_color is None:
            return
        x, y = self.flash_coord
        idx = sum(len(line) + 1 for line in lines[:y]) + x
        display.char_colors[idx] = self.flash_original_color
        self.flash_original_color = None
