
import pygame
import time

class Display_Class:
    def __init__(self, signals=None):
        pygame.init()
        self.SCREEN_WIDTH, self.SCREEN_HEIGHT = 1000, 600
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
        self.screen = pygame.display.set_mode(
            (self.SCREEN_WIDTH, self.SCREEN_HEIGHT),
            pygame.RESIZABLE
        )
        pygame.display.set_caption("Scrollable & Zoomable Text Display")
        self.scroll_x = 0
        self.scroll_y = 0
        self.scroll_speed = 70
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
        self.log_lines = []  # List of log messages
        self.max_log_lines = 4  # 4 below game_time, totaling 5 lines
        self.char_cache = {}
        self.font = pygame.font.Font(self.FONT_PATH, self.font_size)
        self.cached_surface = None
        self.cached_width = 0
        self.cached_height = 0
        self.cached_char_rects = None
        self.cached_lines = None
        self.cached_color_state = None
        # Pre-bake virtual TRTS white circle surface for instant blitting
        char_w = self.font.size('M')[0]
        circ_size = max(char_w, self.line_height)
        self.trts_circle_surf = pygame.Surface((circ_size, circ_size), pygame.SRCALPHA)
        pygame.draw.circle(
            self.trts_circle_surf, 
            (255, 255, 255), 
            (circ_size // 2, circ_size // 2), 
            min(char_w, self.line_height) // 2
        )

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
            "orange": (255, 165, 0),
        }
        return colors.get(name.lower(), (255, 255, 255))

    def set_char_color_at_coord(self, x, y, color_name, game, is_flashing_call=False):
        lines = game.lines
        if y < 0 or y >= len(lines):
            return
        line = lines[y]
        if x < 0 or x >= len(line):
            return
        if line[x] == "x":
            return
        idx = sum(len(l) + 1 for l in lines[:y]) + x
        rgb_color = self.color_name_to_rgb(color_name)
        self.char_colors[idx] = rgb_color

        if not is_flashing_call:
            signal = game.entry_signal
            if signal and signal.entry_flash_coord == (x, y):
                print("Updating entry flash color for signal at", (x, y), "to", rgb_color)
                signal.entry_flash_original_color = rgb_color

    def get_char_color_at_coord(self, x, y, lines):
        if y < 0 or y >= len(lines):
            return
        line = lines[y]
        if x < 0 or x >= len(line):
            return
        idx = sum(len(l) + 1 for l in lines[:y]) + x
        if idx not in self.char_colors:
            return None
        return self.char_colors[idx]
    
    def get_rendered_surface(self, font, lines):

        color_state = tuple(sorted(self.char_colors.items()))
        if (
            lines == self.cached_lines
            and color_state == self.cached_color_state
            and self.cached_surface is not None
        ):
            # print("Using cached surface")
            return (
                self.cached_surface,
                self.cached_width,
                self.cached_height,
                self.cached_char_rects,
            )
        surf, width, height, rects = self.render_text_surface(font, lines)
    
        self.cached_lines = [line[:] for line in lines]  # Deep copy of lines
        self.cached_color_state = color_state
        self.cached_surface = surf
        self.cached_width = width
        self.cached_height = height
        self.cached_char_rects = rects

        return surf, width, height, rects

    def render_text_surface(self, font, lines):

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

        # Alphanumeric platform characters allowed (0-9, A-Z)
        platform_chars_set = set("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ")

        for line in lines:
            x = 0
            line_chars = list(line)

            for char_index, char in enumerate(line_chars):
                bg = None

                if idx in self.char_colors:
                    color = self.char_colors[idx]

                elif char == self.orange_char:
                    color = (255, 165, 0)

                # Recognized platform character (digits and capital letters) between platform bars
                elif char in platform_chars_set:
                    left_has_orange_marker = char_index > 0 and line_chars[char_index - 1] == self.orange_char
                    right_has_orange_marker = char_index < len(line_chars) - 1 and line_chars[char_index + 1] == self.orange_char
                    if left_has_orange_marker or right_has_orange_marker:
                        color = (0, 0, 0)          # black number/letter
                        bg = (255, 165, 0)         # orange background
                    else:
                        color = (128, 128, 128)    # default gray character

                else:
                    color = (128, 128, 128)

                # cached render
                key = (char, color, bg)
                if key not in self.char_cache:
                    self.char_cache[key] = font.render(char, True, color, bg)

                char_surf = self.char_cache[key]

                char_rects.append((idx, pygame.Rect(x, y, char_width, line_height)))
                
                # direct blit (no get_rect)
                surf.blit(char_surf, (x, y))

                x += char_width + self.char_spacing
                idx += 1

            while x < width:
                key = (' ', (128, 128, 128))
                if key not in self.char_cache:
                    self.char_cache[key] = font.render(' ', True, (128, 128, 128))
                char_surf = self.char_cache[key]

                surf.blit(char_surf, (x, y))

                x += char_width + self.char_spacing
                idx += 1

            idx += 1
            y += line_height

        return surf, width, height, char_rects

    def display_game_time(self, game_time_text, font):
        game_time_surface = font.render(game_time_text, True, (255, 255, 255))  # White color
        self.screen.blit(game_time_surface, (0, 0))  # Top-left corner with a small padding of 10 pixels

    def add_log(self, *args):
        message = " ".join(str(arg) for arg in args).upper()
        self.log_lines.append(message)
        if len(self.log_lines) > self.max_log_lines:
            self.log_lines.pop(0)

    def update_and_draw(self, game, signals, autos, lines, time):

        font = self.font

        text_surface, text_width, text_height, char_rects = self.get_rendered_surface(font, lines)

        if not self.handle_events(game, signals, autos, lines, text_width, text_height, char_rects, font):
            return False

        self.draw(text_surface, text_width, text_height, time, font, game=game)

        return True



    def handle_events(self, game, signals, autos, lines, text_width, text_height, char_rects, font):

        reserved_height = self.line_height * (self.max_log_lines + 1)

        for event in pygame.event.get():

            if event.type == pygame.QUIT:
                return False

            elif event.type == pygame.KEYDOWN:
                self.handle_keydown(event, game, text_width, text_height, reserved_height)

            elif event.type == pygame.MOUSEWHEEL:
                self.handle_mousewheel(event, text_width, text_height, reserved_height)

            elif event.type == pygame.MOUSEBUTTONDOWN:

                if event.button == 1:
                    self.handle_left_click(event, game, signals, autos, lines, char_rects, font)
                elif event.button == 3:
                    self.handle_right_click(event, game, signals, autos, lines, char_rects, font)
            elif event.type == pygame.VIDEORESIZE:
                self.SCREEN_WIDTH, self.SCREEN_HEIGHT = event.w, event.h
                self.screen = pygame.display.set_mode(
                    (self.SCREEN_WIDTH, self.SCREEN_HEIGHT), pygame.RESIZABLE
                )

        return True


    def handle_keydown(self, event, game, text_width, text_height, reserved_height):

        mod = pygame.key.get_mods()
        shift_held = mod & pygame.KMOD_SHIFT

        if event.key == pygame.K_UP:

            if shift_held:
                max_scroll_x = max(0, text_width - self.SCREEN_WIDTH)
                self.scroll_x = max(self.scroll_x - self.scroll_speed, -self.SCREEN_WIDTH)
                self.scroll_x = min(self.scroll_x, max_scroll_x)
            else:
                self.scroll_y = max(self.scroll_y - self.scroll_speed, 0)

        elif event.key == pygame.K_DOWN:

            if shift_held:
                max_scroll_x = max(0, text_width - self.SCREEN_WIDTH)
                self.scroll_x = min(self.scroll_x + self.scroll_speed, max_scroll_x)
                self.scroll_x = max(self.scroll_x, -self.SCREEN_WIDTH)

            else:
                max_scroll_y = max(0, text_height - (self.SCREEN_HEIGHT - reserved_height))
                self.scroll_y = min(self.scroll_y + self.scroll_speed, max_scroll_y)

        elif event.key == pygame.K_p:
            game.paused = not game.paused
            if not game.paused:
                # When unpausing, reset the time tracker so the pause duration isn't added to the clock
                game._last_real_time = time.time()
            self.add_log(f"Game paused: {game.paused}")

        elif event.key in (pygame.K_PLUS, pygame.K_KP_PLUS):
            game.time_speed += 1
            self.add_log(f"Time speed increased: {game.time_speed}")

        elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            game.time_speed = max(1, game.time_speed - 1)
            self.add_log(f"Time speed decreased: {game.time_speed}")
        elif (pygame.key.get_mods() & pygame.KMOD_CTRL) and event.key == pygame.K_r:
            game.ars_on = not game.ars_on
        elif (pygame.key.get_mods() & pygame.KMOD_CTRL) and event.key == pygame.K_s:
            game.save_game()

        elif (pygame.key.get_mods() & pygame.KMOD_CTRL) and event.key == pygame.K_l:

            try:
                game.load_game()
                self.add_log("Game loaded")

            except FileNotFoundError:
                self.add_log("No saved game found")


    def handle_mousewheel(self, event, text_width, text_height, reserved_height):

        mod = pygame.key.get_mods()
        shift_held = mod & pygame.KMOD_SHIFT

        if shift_held:

            max_scroll_y = max(0, text_height - (self.SCREEN_HEIGHT - reserved_height))
            self.scroll_y = min(
                max(self.scroll_y - event.y * self.scroll_speed, 0),
                max_scroll_y
            )

        else:

            max_scroll_x = max(0, text_width - self.SCREEN_WIDTH)
            self.scroll_x = min(
                max(self.scroll_x - event.y * self.scroll_speed, -self.SCREEN_WIDTH),
                max_scroll_x
            )

    def handle_left_click(self, event, game, signals, autos, lines, char_rects, font):

        mx, my = event.pos

        adjusted_x = mx + self.scroll_x
        adjusted_y = my + self.scroll_y

        clicked_idx = None

        for idx, rect in char_rects:
            if rect.collidepoint(adjusted_x, adjusted_y):
                clicked_idx = idx
                break

        if clicked_idx is None:
            return

        x = adjusted_x // (font.size('M')[0] + self.char_spacing)
        y = adjusted_y // self.line_height - (self.max_log_lines + 1)

        # 1. Check for Via Button click first (if an entry signal is already selected)
        if game.entry_signal is not None:
            for via in getattr(game, "via_buttons", []):
                if via.coord in [(x, y), (x + 1, y), (x - 1, y)]:
                    if via not in getattr(game, "selected_via_buttons", []):
                        game.selected_via_buttons.append(via)
                        via.prepare_flash(self, lines)
                        self.add_log(f"via button selected at {via.coord}")
                    return

        # 2. Check for Signal click
        for signal in signals:

            if signal.coord in [(x, y), (x + 1, y), (x - 1, y)]:

                if game.entry_signal is None and signal.signal_type == "manual":
                    game.entry_signal = signal
                    game.selected_via_buttons = []
                    signal.prepare_entry_flash(self, lines)
                    self.add_log("entry signal selected")

                elif game.entry_signal is not None:
                    game.exit_signal = signal
                    self.add_log("exit signal selected")
                    # Trigger set_route right away on exit signal click
                    game.set_route()
                return

        # 3. Check for Auto button click
        for auto in autos:

            if auto.coord in [(x, y), (x + 1, y), (x - 1, y)]:

                if not auto.signal.route_set:
                    self.add_log("route not set on signal")

                else:
                    self.add_log("auto button pressed at", auto.coord)
                    auto.pressed(game)

                break

        # 4. Check for Train click
        for train in game.trains:

            if (adjusted_x // (font.size('M')[0] + self.char_spacing),
                adjusted_y // self.line_height - 5) in train.headcode_coords:

                game.open_timetable_window(train)
                break

    def handle_right_click(self, event, game, signals, autos, lines, char_rects, font):

        mx, my = event.pos

        adjusted_x = mx + self.scroll_x
        adjusted_y = my + self.scroll_y

        clicked_idx = None

        for idx, rect in char_rects:
            if rect.collidepoint(adjusted_x, adjusted_y):
                clicked_idx = idx
                break

        if clicked_idx is None:
            return

        x = adjusted_x // (font.size('M')[0] + self.char_spacing)
        y = adjusted_y // self.line_height - (self.max_log_lines + 1)

        for signal in signals:

            if signal.coord in [(x, y), (x + 1, y), (x - 1, y)]:

                if signal.signal_type == "manual":
                    self.add_log("canceling route for signal at", signal.coord)
                    signal.cancel_route(self, lines, autos, game)

        for auto in autos:

            if auto.coord in [(x, y), (x + 1, y), (x - 1, y)]:
                self.add_log("auto button depressed at", auto.coord)
                auto.depressed(game)
                break


    def draw(self, text_surface, text_width, text_height, time, font, game=None):

        self.screen.fill(self.BLACK)

        reserved_height = self.line_height * 5

        text_display_area = pygame.Rect(
            0,
            reserved_height,
            self.SCREEN_WIDTH,
            self.SCREEN_HEIGHT - reserved_height
        )

        self.screen.set_clip(text_display_area)

        self.screen.blit(
            text_surface,
            (-self.scroll_x, reserved_height - self.scroll_y)
        )

        # Draw any virtual TRTS circle overlays on top of the text
        if game:
            self.draw_virtual_trts_indicators(game, font)

        self.screen.set_clip(None)

        self.display_game_time(time, font)

        for i, line in enumerate(self.log_lines):

            log_surface = font.render(line, True, (200, 200, 200))

            self.screen.blit(
                log_surface,
                (0, self.line_height * (i + 1))
            )

        pygame.display.flip()

    def display_via_button_color(self, via_buttons, game):
        for via in via_buttons:
            if getattr(via, "colored", False):
                continue
            x, y = via.coord
            self.set_char_color_at_coord(x, y, "light blue", game)
            via.colored = True

    def display_signal_color(self, signals, game):
        """
        Restore the actual signal lamp color at the signal coord itself,
        and separately color the adjacent tile next to the lamp based on route state.
        """
        for signal in signals:
            if signal.buffer:
                continue

            x, y = signal.coord
            self.set_char_color_at_coord(x, y, signal.color, game)
            signal.last_colored_color = signal.color

            if signal.direction == "right":
                target_x = x + 1
            elif signal.direction == "left":
                target_x = x - 1

            target_color = "white" if signal.route_set else "gray"
            self.set_char_color_at_coord(target_x,y, signal.color, game)
            self.set_char_color_at_coord(x, y, target_color, game)
            signal.route_highlight_color = target_color

    def update_entry_signal_flash(self, game, lines):
        flash_color = "white" if int(game.game_seconds * 2) % 2 == 0 else "black"

        # 1. Update Entry Signal Overlap Flash
        for signal in game.signals:
            if signal is game.entry_signal:
                if signal.entry_flash_coord is None:
                    signal.prepare_entry_flash(self, lines)
                x, y = signal.entry_flash_coord
                self.set_char_color_at_coord(x, y, flash_color, game, is_flashing_call=True)
            elif signal.entry_flash_coord is not None:
                signal.clear_entry_flash(self, lines)

        # 2. Update Selected Via Buttons Track Flashes (x, y + 1)
        selected_vias = getattr(game, "selected_via_buttons", [])
        for via in getattr(game, "via_buttons", []):
            if via in selected_vias and game.entry_signal is not None:
                if via.flash_original_color is None:
                    via.prepare_flash(self, lines)
                vx, vy = via.flash_coord
                self.set_char_color_at_coord(vx, vy, flash_color, game, is_flashing_call=True)
            elif via.flash_original_color is not None:
                via.clear_flash(self, lines)

    def display_auto_button_color(self, autos, game):
        for auto in autos:
            if auto.colored:
                continue
            x, y = auto.coord
            if auto.direction == "right":
                x1 = x + 1
            elif auto.direction == "left":
                x1 = x - 1
            self.set_char_color_at_coord(x, y, "light blue", game)
            self.set_char_color_at_coord(x1, y, "light blue", game)
            auto.colored = True

    def draw_virtual_trts_indicators(self, game, font):
        active_trts = getattr(game, "active_virtual_trts", None)
        if not active_trts:
            return

        char_width = font.size('M')[0]
        char_w_space = char_width + self.char_spacing
        line_height = self.line_height
        reserved_height = line_height * 5
        radius = min(char_width, line_height) // 2

        for gx, gy, flash_on in active_trts.values():
            if not flash_on:
                continue  # Transparent state

            # Exact pixel center of character (gx, gy) in text display coordinates
            center_x = gx * char_w_space + (char_width // 2) - self.scroll_x
            center_y = reserved_height + (gy * line_height) + (line_height // 2) - self.scroll_y

            # Draw circle only when visible in the viewport
            if (0 <= center_x <= self.SCREEN_WIDTH and 
                reserved_height <= center_y <= self.SCREEN_HEIGHT):
                pygame.draw.circle(self.screen, (255, 255, 255), (center_x, center_y), radius)
