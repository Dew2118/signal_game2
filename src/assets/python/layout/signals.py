from collections import deque
import copy

class Signal:
    def __init__(
        self, name, coord, signal_type, color, direction, mount,
        possible_next_signals=None, next_signal=None, train_in_block=False, buffer=False, shunt=False
    ):
        self.name = name
        self.coord = coord
        self.signal_type = signal_type
        self.color = color
        self.direction = direction
        self.mount = mount
        self.possible_next_signals = possible_next_signals if possible_next_signals is not None else []
        self.next_signal = next_signal
        self.train_in_block = train_in_block
        self.route_set = False
        self.buffer = buffer
        self.shunt = shunt
        
        self.route_coords = None
        self.ordered_route_coords = [] # Ordered for train movement (Manual)
        self.auto_route_coords = None  # Cached paths for Automatic signals
        self.ordered_auto_route_coords = [] # Ordered for train movement (Automatic)
        self.route_coords_direction_dict = {}
        
        self.auto = False
        self.overlap = (0,0)
        self.TRTS_button_coord = None
        self.last_colored_color = None
        self.route_highlight_color = None
        self.entry_flash_coord = None
        self.entry_flash_original_color = None
        self.temporary_characters = []
        
        # --- CACHING ATTRIBUTES ---
        self.cached_routes_to_signals = {}
        self.routes_cached = False

    def __repr__(self):
        return (f"Signal(name={self.name!r}, coord={self.coord}, "
                f"type={self.signal_type!r}, color={self.color!r}, "
                f"direction={self.direction!r}, mount={self.mount!r}, "
                f"possible_next_signals={self.possible_next_signals}, "
                f"next_signal={self.next_signal!r}")

    def update_color(self, trains):
        trains_in_section = self.check_for_trains_in_section(trains)
        
        if self.signal_type == "automatic" or self.route_set:
            # Both types now rely on the physical collision check
            if trains_in_section:
                self.color = "red"
            elif self.next_signal and self.next_signal.color == "red":
                if self.shunt:
                    self.color = "white"
                else:
                    self.color = "yellow"
            else:
                if self.shunt:
                    self.color = "white"
                else:
                    self.color = "green"
        else:
            self.color = "red"

    def build_route_cache(self, game, switches, filename, signals, max_depth=2000):
        with open(filename, "r", encoding="utf-8") as f:
            original_text = f.read()
        base_lines = [list(line.rstrip('\n')) for line in original_text.splitlines()]

        start_x, start_y = self.overlap
        if self.direction == "right":
            start_x += 1
        else:
            start_x -= 1

        queue = deque([(
            start_x, start_y, self.direction, "F", "F", 
            base_lines, 
            [(start_x, start_y)], 
            {(start_x, start_y): self.direction}, 
            None, 
            {}, 
            0,
            [] # temp_chars tracking
        )])

        while queue:
            (x, y, current_dir, last_char, last_last_char, current_lines, 
             coords_path, dir_dict, dir_change, required_switches, depth, temp_chars) = queue.popleft()

            if depth > max_depth:
                continue

            reached_signal = None
            for sig in signals:
                if sig != self:
                    if (x, y) == sig.overlap and sig.direction == current_dir:
                        reached_signal = sig
                    elif (x+2, y) == sig.coord and sig.buffer and sig.direction == current_dir:
                        reached_signal = sig
                    elif (x-2, y) == sig.coord and sig.buffer and sig.direction == current_dir:
                        reached_signal = sig

            if reached_signal:
                if reached_signal not in self.cached_routes_to_signals:
                    self.cached_routes_to_signals[reached_signal] = []
                    
                self.cached_routes_to_signals[reached_signal].append({
                    "coords": coords_path,
                    "dir_dict": dir_dict,
                    "dir_change": dir_change,
                    "required_switches": required_switches,
                    "temp_chars": temp_chars
                })
                continue 

            on_switch = False
            for i, switch in enumerate(switches):
                if x == switch[0] and y == switch[1]:
                    if switch[3] == current_dir:
                        on_switch = True
                        
                        # Branch A: Normal
                        req_sw_norm = required_switches.copy()
                        req_sw_norm[i] = "normal"
                        lines_norm = game.change_switch(i, "normal", [row[:] for row in current_lines])
                        tc_norm = temp_chars.copy()
                        
                        nx_n, ny_n, ndir_n, nlc_n, ndc_n, nllc_n, tc_norm = game.path_find(
                            lines_norm, x, y, current_dir, self.direction, last_char, last_last_char, tc_norm
                        )
                        
                        if nx_n != -1 and nlc_n != "x" and (0 <= ny_n < len(lines_norm) and 0 <= nx_n < len(lines_norm[ny_n])):
                            new_coords_n = coords_path + [(nx_n, ny_n)]
                            new_dir_dict_n = dir_dict.copy()
                            new_dir_dict_n[(nx_n, ny_n)] = ndir_n
                            queue.append((nx_n, ny_n, ndir_n, nlc_n, nllc_n, 
                                          lines_norm, new_coords_n, new_dir_dict_n, ndc_n or dir_change, req_sw_norm, depth + 1, tc_norm))

                        # Branch B: Reverse
                        req_sw_rev = required_switches.copy()
                        req_sw_rev[i] = "reverse"
                        lines_rev = game.change_switch(i, "reverse", [row[:] for row in current_lines])
                        tc_rev = temp_chars.copy()
                        
                        nx_r, ny_r, ndir_r, nlc_r, ndc_r, nllc_r, tc_rev = game.path_find(
                            lines_rev, x, y, current_dir, self.direction, last_char, last_last_char, tc_rev
                        )
                        
                        if nx_r != -1 and nlc_r != "x" and (0 <= ny_r < len(lines_rev) and 0 <= nx_r < len(lines_rev[ny_r])):
                            new_coords_r = coords_path + [(nx_r, ny_r)]
                            new_dir_dict_r = dir_dict.copy()
                            new_dir_dict_r[(nx_r, ny_r)] = ndir_r
                            queue.append((nx_r, ny_r, ndir_r, nlc_r, nllc_r, 
                                          lines_rev, new_coords_r, new_dir_dict_r, ndc_r or dir_change, req_sw_rev, depth + 1, tc_rev))
                        break
                    else:
                        req_sw_trail = required_switches.copy()
                        if last_char not in "a[]bc" and ((last_char not in "hljn" and current_dir == "right") or (last_char not in "koim" and current_dir == "left")):
                            req_sw_trail[i] = "reverse"
                            current_lines = game.change_switch(i, "reverse", current_lines)
                        else:
                            req_sw_trail[i] = "normal"
                            current_lines = game.change_switch(i, "normal", current_lines)
                        required_switches = req_sw_trail

            if on_switch:
                continue

            tc_standard = temp_chars.copy()
            new_x, new_y, new_dir, new_last_char, new_dir_change, new_last_last_char, tc_standard = game.path_find(
                current_lines, x, y, current_dir, self.direction, last_char, last_last_char, tc_standard
            )

            if new_x == -1 or new_last_char == "x":
                continue
            if not (0 <= new_y < len(current_lines) and 0 <= new_x < len(current_lines[new_y])):
                continue

            new_coords_path = coords_path + [(new_x, new_y)]
            new_dir_dict = dir_dict.copy()
            new_dir_dict[(new_x, new_y)] = new_dir
            current_dir_change = new_dir_change if new_dir_change else dir_change
            
            queue.append((new_x, new_y, new_dir, new_last_char, new_last_last_char, 
                          current_lines, new_coords_path, new_dir_dict, current_dir_change, required_switches, depth + 1, tc_standard))

    def get_coords_to_next_signal(self, exit_signal, game, switches, filename, signals, trains, dont_set=False, ordered=False):
        try:
            import copy
            
            # 1. Lazy load route cache if not cached during startup
            if not self.routes_cached:
                self.build_route_cache(game, switches, filename, signals)
                self.routes_cached = True

            if not exit_signal or exit_signal not in self.cached_routes_to_signals:
                return []

            # 2. Scan pre-calculated cache to find the first safe, collision-free route permutation
            available_routes = self.cached_routes_to_signals[exit_signal]
            valid_route = None
            
            for route in available_routes:
                collision = False
                
                # Check each tile of the route against train positions and directions
                for x, y in route["coords"]:
                    if self.duplicate_train_route_check(x, y, trains):
                        collision = True
                        break
                    direction = route["dir_dict"].get((x,y))
                    if direction and self.duplicate_train_direction_route_check(x, y, trains, direction):
                        collision = True
                        break
                
                # Check for conflicts with routes set by other signals
                if not collision:
                    if self.check_signal_route_collision(route["coords"], route["dir_dict"], exit_signal, signals):
                        collision = True

                if not collision:
                    valid_route = route
                    break

            if not valid_route:
                return [] # No safe path currently available

            # --- Build return variables independently of game state ---
            ordered_coords_to_return = []
            for coord in valid_route["coords"]:
                if coord not in ordered_coords_to_return:
                    ordered_coords_to_return.append(coord)
            unordered_coords_to_return = list(set(valid_route["coords"]))
            # --------------------------------------------------------

            # 3. Apply the valid route configuration ONLY if we are actually setting it
            if not dont_set:
                # Instantly align all switches along the calculated path
                for switch_idx, state in valid_route["required_switches"].items():
                    game.lines = game.change_switch(switch_idx, state, game.lines)
                
                # Bind the route coordinates to the signal's live state
                self.route_coords = unordered_coords_to_return
                self.ordered_route_coords = ordered_coords_to_return
                self.route_coords_direction_dict = valid_route["dir_dict"]

                # Restore and map temporary characters (curves, crossovers, etc.)
                self.temporary_characters = copy.deepcopy(valid_route["temp_chars"])
                for temporary_character in self.temporary_characters.copy():
                    if temporary_character[0] not in valid_route["coords"]:
                        self.temporary_characters.remove(temporary_character)
                
                game.handle_temporary_characters(self.temporary_characters)

                # Handle direction change logic and ensure trailing switch alignments
                direction_to_test_change = False
                for coord in valid_route["coords"]:
                    x, y = coord
                    for i, switch in enumerate(switches):
                        if valid_route["dir_change"] and ((x,y) == valid_route["dir_change"][0] or direction_to_test_change):
                            direction_to_test = "right" if self.direction == "left" else "left"
                            direction_to_test_change = True
                        else:
                            direction_to_test = self.direction
                            
                        # Ensure exit trailing switches are aligned in reverse if required
                        if x == switch[0] and y == switch[1] and switch[3] == direction_to_test and i not in valid_route["required_switches"]:
                             game.lines = game.change_switch(i, "reverse", game.lines)

            else:
                # If dont_set is true, explicitly guarantee temporary_characters is empty/unaffected
                self.temporary_characters = []

            # If the caller (like ARS timing route-setting) needs the chronological path
            if ordered:
                return ordered_coords_to_return
                
            return unordered_coords_to_return

        except Exception as e:
            if not dont_set:
                game.display_class.add_log("route setting failed, please try again error message: ", str(e))
            print(f"signal get coords to next signal error from {self.coord} to {exit_signal.coord}, {e}")
            return []


    # --- SIMPLIFIED COLLISION CHECKER (replaces the messy backtracker) ---
    def check_signal_route_collision(self, coords, dir_dict, exit_signal, signals):
        coord_set = set(coords)
        for signal in signals:
            if signal == exit_signal:
                continue
            for x, y in coords:
                direction = dir_dict.get((x,y))
                if (x, y+1) == signal.coord and signal.direction == direction and signal.mount == "down":
                    return True
                elif (x, y-1) == signal.coord and signal.direction == direction and signal.mount == "up":
                    return True
            if signal.route_coords:
                if len(coord_set & set(signal.route_coords)) > 0:
                    return True
        return False

    def temporary_character_broken_check(self, last_last_char, last_char, char, direction):
        return True

    def duplicate_train_route_check(self, x, y, trains):
        for train in trains:
            if train.route_coords:
                if (x, y) in train.route_coords:
                    # print("route collision detected at ", (x,y), f"from train {train.headcode}")
                    return True
            for coord_list in train.coords:
                if (x, y) in coord_list:
                    # print("train collision detected at ", (x,y), f"from train {train.headcode}")
                    return True
        return False

    def duplicate_train_direction_route_check(self, x, y, trains, direction):
            for train in trains:
                if train.route_coords:
                    if (x, y) in train.route_coords and train.route_coords_direction_dict.get((x,y)) and train.route_coords_direction_dict.get((x,y)) != direction:
                        return True
                if (x,y) in train.coords[0] or (len(train.coords) > 1 and (x,y) in train.coords[1]):
                    if not train.direction_change and direction != train.direction:
                        return True
                    elif train.direction_change:
                        all_train_coord = [coord for coord_list in train.coords for coord in coord_list]
                        train_direction = train.direction
                        for coord in all_train_coord:
                            if coord == (x,y) and direction == train_direction:
                                return True
                            if coord == train.direction_change[0]:
                                if train_direction == "left":
                                    train_direction = "right"
                                else:
                                    train_direction = "left"
            return False

    def cancel_route(self, display, lines, autos, game):
        if self.signal_type == "manual" and self.route_set and self.route_coords:
            self.route_set = False
            self.next_signal = None
            self.color = "red"
            train_route_coords_list = []
            for train in game.trains:
                if train.route_coords:
                    train_route_coords_list.extend(train.route_coords) 
            for coord in self.route_coords:
                x, y = coord
                if display.get_char_color_at_coord(x, y, lines) == (255, 255, 255) and (x,y) not in train_route_coords_list:
                    display.set_char_color_at_coord(x, y, "gray", game)
            for auto in autos:
                if auto.signal == self:
                    auto.depressed(game)
                    lines = [row[:] for row in game.lines]
            self.route_coords = None
        for temporary_character in self.temporary_characters.copy():
            for train in game.trains:
                if temporary_character[0] in train.coords[0] or (len(train.coords) > 1 and temporary_character[0] in train.coords[1]) or temporary_character[0] in train.route_coords:
                    self.temporary_characters.remove(temporary_character)
            for signal in game.signals:
                if signal != self and signal.route_coords != None and len(signal.route_coords) >  0 and temporary_character[0] in signal.route_coords:
                    self.temporary_characters.remove(temporary_character)
        game.reset_temporary_characters(self.temporary_characters)
        self.temporary_characters = []

    # Note: go_back_to_last_switch and duplicate_signal_route_check were removed as they are obsolete with caching!

    def prepare_entry_flash(self, display, lines):
        if self.entry_flash_coord is not None:
            return
        x, y = self.overlap
        if self.direction == "left":
            flash_coord = (x - 1, y)
        elif self.direction == "right":
            flash_coord = (x + 1, y)
        else:
            flash_coord = (x, y)
        self.entry_flash_coord = flash_coord
        current_color = display.get_char_color_at_coord(*flash_coord, lines)
        self.entry_flash_original_color = current_color if current_color is not None else (128, 128, 128)

    def clear_entry_flash(self, display, lines):
        if self.entry_flash_coord is None:
            return
        x, y = self.entry_flash_coord
        if self.entry_flash_original_color is not None:
            idx = sum(len(line) + 1 for line in lines[:y]) + x
            display.char_colors[idx] = self.entry_flash_original_color
        self.entry_flash_coord = None
        self.entry_flash_original_color = None

    def check_for_trains_in_section(self, trains):
        # We need to check whichever route coordinates this signal uses
        coords_to_check = self.route_coords if self.signal_type == "manual" else self.auto_route_coords
        
        if not coords_to_check:
            return False
            
        for train in trains:
            flattened_train_coords = set([coord for sublist in train.coords for coord in sublist])
            route_coords_set = set(coords_to_check)
            
            # If the train's body intersects the signal's path, the block is occupied
            if flattened_train_coords & route_coords_set:
                return True
                
        return False
    
    def activate_TRTS(self, game, display):
        lines = [row[:] for row in game.lines]
        if not self.TRTS_button_coord:
            return
        x,y = self.TRTS_button_coord
        lines[y][x] = "q"
        display.set_char_color_at_coord(x, y, "white", game)
        game.lines = [row[:] for row in lines]

    def deactivate_TRTS(self, game, display):
        lines = [row[:] for row in game.lines]
        if not self.TRTS_button_coord:
            return lines
        x,y = self.TRTS_button_coord
        lines[y][x] = "p"
        display.set_char_color_at_coord(x, y, "orange", game)
        game.lines =  [row[:] for row in lines]
