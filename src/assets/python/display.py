import pygame

class Display_Class:
    def __init__(self, signals=None):
        pygame.init()
        self.SCREEN_WIDTH, self.SCREEN_HEIGHT = 1000, 800
        self.FONT_PATH = "src/assets/fonts/S-box.ttf"
        self.BASE_FONT_SIZE = 15
        self.WHITE = (255, 255, 255)
        self.BLACK = (0, 0, 0)
        self.char_spacing = -1
        self.orange_char = '¯'
        self.green_indices = set()
        self.char_colors = {}
        self.signals = signals if signals is not None else []
        self.font_size = self.BASE_FONT_SIZE
        self.font_size = max(8, min(200, round(self.font_size / 4) * 4))
        self.screen = pygame.display.set_mode((self.SCREEN_WIDTH, self.SCREEN_HEIGHT))
        pygame.display.set_caption("Scrollable & Zoomable Text Display")
        self.scroll_x = 0
        self.scroll_y = 0
        self.scroll_speed = 20
        self.signal_paths = []
        self.current_path_index = 0
        self.current_step_index = 0
        self.last_step_time = pygame.time.get_ticks()
        self.step_delay = 1000  # ms (1 second)
        self.automatic_signals = [s for s in self.signals if s.signal_type == "automatic"]
        self.current_auto_index = 0
        self.last_pair_time = pygame.time.get_ticks()
        self.pair_delay = 1000  # ms (1 second)
        self.line_height = 16

    def color_name_to_rgb(self, name):
        colors = {
            "red": (255, 0, 0),
            "green": (0, 255, 0),
            "blue": (0, 0, 255),
            "light blue": (0, 255, 255),
            "orange": (255, 165, 0),
            "yellow": (255, 255, 0),
            "white": (255, 255, 255),
            "black": (0, 0, 0),
            "gray": (128, 128, 128),
        }
        return colors.get(name.lower(), (255, 255, 255))

    def set_char_color_at_coord(self, x, y, color_name, text):
        lines = text.splitlines()
        if y < 0 or y >= len(lines):
            return
        line = lines[y]
        if x < 0 or x >= len(line):
            return
        idx = sum(len(l) + 1 for l in lines[:y]) + x
        self.char_colors[idx] = self.color_name_to_rgb(color_name)

    def get_char_color_at_coord(self, x, y, text):
        
        lines = text.splitlines()
        if y < 0 or y >= len(lines):
            return
        line = lines[y]
        if x < 0 or x >= len(line):
            return
        idx = sum(len(l) + 1 for l in lines[:y]) + x
        if idx not in self.char_colors:
            return None
        return self.char_colors[idx]
    def render_text_surface(self, font, text):
        lines = text.splitlines()
        # line_height = font.get_linesize()
        line_height = self.line_height
        char_width = font.size('M')[0]
        max_line_length = max(len(line) for line in lines) if lines else 0
        width = (char_width + self.char_spacing) * max_line_length
        height = line_height * len(lines)
        surf = pygame.Surface((width, height), pygame.SRCALPHA)
        surf.fill(self.BLACK)
        char_rects = []
        idx = 0
        y = 0
        for line in lines:
            x = 0
            
            for char in line:
                # if y == 0 and x <= 10:
                #     continue
                if idx in self.char_colors:
                    color = self.char_colors[idx]
                elif char == self.orange_char:
                    color = (255, 165, 0)
                # elif idx in self.green_indices:
                #     color = (0, 255, 0)
                else:
                    color = (128, 128, 128)  # Gray instead of white for default
                char_surf = font.render(char, True, color)
                char_rect = char_surf.get_rect(center=(x + char_width // 2, y + line_height // 2))
                char_rects.append((idx, pygame.Rect(x, y, char_width, line_height)))
                surf.blit(char_surf, char_rect.topleft)
                x += char_width + self.char_spacing
                idx += 1
            while x < width:
                # if y == 0 and x <= 10:
                #     continue
                char_surf = font.render(' ', True, (128, 128, 128))  # Gray for empty space
                char_rect = char_surf.get_rect(center=(x + char_width // 2, y + line_height // 2))
                surf.blit(char_surf, char_rect.topleft)
                x += char_width + self.char_spacing
                idx += 1
            idx += 1
            y += line_height
        return surf, width, height, char_rects
    
    def display_game_time(self, game_time_text, font):
        game_time_surface = font.render(game_time_text, True, (255, 255, 255))  # White color
        self.screen.blit(game_time_surface, (0, 0))  # Top-left corner with a small padding of 10 pixels

    def update_and_draw(self,game,signals,autos, text, time):
        # try:
        
        font = pygame.font.Font(self.FONT_PATH, self.font_size)
        redraw = False
        
        text_surface, text_width, text_height, char_rects = self.render_text_surface(font, text)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.KEYDOWN:
                mod = pygame.key.get_mods()
                shift_held = mod & pygame.KMOD_SHIFT
                if event.key == pygame.K_UP:
                    if shift_held:
                        self.scroll_x = max(self.scroll_x - self.scroll_speed, 0)
                    else:
                        self.scroll_y = max(self.scroll_y - self.scroll_speed, 0)
                    redraw = True

                # Press P to toggle pause state
                if event.key == pygame.K_p:
                    game.paused = not game.paused  # Toggle pause state
                    print(f"Game paused: {game.paused}")
                    redraw = True

                # Press + to increase time_speed
                elif event.key == pygame.K_PLUS or event.key == pygame.K_KP_PLUS:
                    game.time_speed += 1  # Increase time speed by 1
                    print(f"Time speed increased: {game.time_speed}")
                    redraw = True

                # Press - to decrease time_speed, but don't go below 1
                elif event.key == pygame.K_MINUS or event.key == pygame.K_KP_MINUS:
                    game.time_speed = max(1, game.time_speed - 1)  # Decrease time speed but not below 1
                    print(f"Time speed decreased: {game.time_speed}")
                    redraw = True
                elif event.key == pygame.K_DOWN:
                    if shift_held:
                        max_scroll_x = max(0, text_width - self.SCREEN_WIDTH)
                        self.scroll_x = min(self.scroll_x + self.scroll_speed, max_scroll_x)
                    else:
                        max_scroll_y = max(0, text_height - self.SCREEN_HEIGHT)
                        self.scroll_y = min(self.scroll_y + self.scroll_speed, max_scroll_y)
                    redraw = True

                if (pygame.key.get_mods() & pygame.KMOD_CTRL) and event.key == pygame.K_s:
                    game.save_game()
                    print("Game saved.")

                # Load game with Ctrl+L
                elif (pygame.key.get_mods() & pygame.KMOD_CTRL) and event.key == pygame.K_l:
                    try:
                        game.load_game()
                        print("Game loaded.")
                    except FileNotFoundError:
                        print("No saved game found.")
            elif event.type == pygame.MOUSEWHEEL:
                mod = pygame.key.get_mods()
                shift_held = mod & pygame.KMOD_SHIFT
                if shift_held:
                    max_scroll_y = max(0, text_height - self.SCREEN_HEIGHT)
                    self.scroll_y = min(max(self.scroll_y - event.y * self.scroll_speed, 0), max_scroll_y)                    
                else:
                    max_scroll_x = max(0, text_width - self.SCREEN_WIDTH)
                    self.scroll_x = min(max(self.scroll_x - event.y * self.scroll_speed, 0), max_scroll_x)

                redraw = True
            
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                
                mx, my = event.pos
                adjusted_x = mx + self.scroll_x
                adjusted_y = my + self.scroll_y
                clicked_idx = None
                for idx, rect in char_rects:
                    if rect.collidepoint(adjusted_x, adjusted_y):
                        clicked_idx = idx
                        break
                if clicked_idx is not None:
                    for signal in signals:
                        x = adjusted_x//(font.size('M')[0]+self.char_spacing)
                        y = adjusted_y//self.line_height
                        if signal.coord == (x, y) or signal.coord == (x+1, y) or signal.coord == (x-1, y):
                            if game.entry_signal is None and signal.signal_type == "manual":
                                game.entry_signal = signal
                                print("entry signal selected")
                            else:
                                game.exit_signal = signal
                                print("exit signal selected")
                    for auto in autos:
                        if auto.coord == (x, y) or auto.coord == (x+1, y) or auto.coord == (x-1, y):
                            if not auto.signal.route_set:
                                print("route not set on signal")
                            else:
                                print("auto button pressed at", auto.coord)
                                auto.pressed(text, game)
                                redraw = True
                            break
                    for train in game.trains:
                        if (adjusted_x//(font.size('M')[0]+self.char_spacing), adjusted_y//self.line_height) in train.coords:
                            game.open_timetable_window(train)
                            break
                mx, my = event.pos
                redraw = True
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                mx, my = event.pos
                adjusted_x = mx + self.scroll_x
                adjusted_y = my + self.scroll_y
                clicked_idx = None
                for idx, rect in char_rects:
                    if rect.collidepoint(adjusted_x, adjusted_y):
                        clicked_idx = idx
                        break
                if clicked_idx is not None:
                    x = adjusted_x//(font.size('M')[0]+self.char_spacing)
                    y = adjusted_y//self.line_height
                    for signal in signals:
                        if signal.coord == (x, y) or signal.coord == (x+1, y) or signal.coord == (x-1, y):
                            if signal.signal_type == "manual":
                                print("canceling route for signal at", signal.coord)
                                signal.cancel_route(self, text, autos, game)
                                redraw = True
                    for auto in autos:
                        
                        if auto.coord == (x, y) or auto.coord == (x+1, y) or auto.coord == (x-1, y):
                            
                            print("auto button depressed at", auto.coord)
                            auto.depressed(text, game)
                            redraw = True
                            break


        # Always redraw after events
        font = pygame.font.Font(self.FONT_PATH, self.font_size)
        # text_surface, text_width, text_height, char_rects = self.render_text_surface(font, text)
        
        self.screen.fill(self.BLACK)  # Fill the screen with black first
        
        self.screen.blit(text_surface, (-self.scroll_x, -self.scroll_y))  # Blit the text surface
        self.display_game_time(time, font)
        pygame.display.flip() 
        return True  # Continue main loop
        # except:
        #     print("error in event get")
    def display_signal_color(self, signals, text):
        """
        Loop through each signal, get the coord of the signal.
        If direction is right, x + 1; if left, x - 1.
        Then turn that coord the signal's color.
        """
        for signal in signals:
            if signal.buffer:
                continue
            x, y = signal.coord
            if signal.direction == "right":
                x += 1
            elif signal.direction == "left":
                x -= 1
            self.set_char_color_at_coord(x, y, signal.color, text)

    def display_auto_button_color(self, autos, text):
        for auto in autos:
            x, y = auto.coord
            if auto.direction == "right":
                x1 = x + 1
            elif auto.direction == "left":
                x1 = x - 1
            self.set_char_color_at_coord(x, y, "light blue", text)
            self.set_char_color_at_coord(x1, y, "light blue", text)