from collections import deque
class Signal:
    def __init__(
        self, name, coord, signal_type, color, direction, mount,
        possible_next_signals=None, next_signal=None, train_in_block=False, buffer = False, shunt = False
    ):
        self.name = name  # string
        self.coord = coord  # tuple (x, y)
        self.signal_type = signal_type  # "automatic" or "manual"
        self.color = color  # "red", "yellow", or "green"
        self.direction = direction  # "right" or "left"
        self.mount = mount  # "up" or "down"
        self.possible_next_signals = possible_next_signals if possible_next_signals is not None else []
        self.next_signal = next_signal  # Signal or None
        self.train_in_block = train_in_block  # New attribute
        self.route_set = False
        self.buffer = buffer
        self.shunt = shunt
        self.route_coords = None
        self.auto = False
        self.overlap = (0,0)
        self.TRTS_button_coord = None
        self.last_colored_color = None
        self.route_highlight_color = None
        self.entry_flash_coord = None
        self.entry_flash_original_color = None
        self.temporary_characters = []

    def __repr__(self):
        return (f"Signal(name={self.name!r}, coord={self.coord}, "
                f"type={self.signal_type!r}, color={self.color!r}, "
                f"direction={self.direction!r}, mount={self.mount!r}, "
                f"possible_next_signals={self.possible_next_signals}, "
                f"next_signal={self.next_signal!r}")

    def update_color(self, trains):
        trains_in_section = self.check_for_trains_in_section(trains)
        if self.signal_type == "automatic" or self.route_set:
            if (self.signal_type == "automatic" and self.train_in_block) or (self.signal_type == "manual" and trains_in_section):
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

    def get_coords_to_next_signal(self, exit_signal, game, switches, filename, signals, trains):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                original_text = f.read()
            lines = [list(line.rstrip('\n')) for line in original_text.splitlines()].copy()
            switch_stack = deque()
            direction = self.direction
            last_char = "F"
            last_last_char = "F"
            direction_change = None
            if not exit_signal:
                return []

            x,y = self.overlap
            coords = deque()
            last_switch = None
            restart = False
            while True:
                
                # print("current location: ", (x,y), " current direction: ", direction, " last char: ", last_char)
                for i,switch in enumerate(switches):
                    if x == switch[0] and y == switch[1]:
                        if switch[3] == direction:
                            if switch != last_switch:
                                if self.duplicate_train_route_check(x, y, trains):
                                    if game.get_switch_position(i, game.lines) == "normal":
                                        switch_stack.append((switch,i, direction, False, None))
                                        print("appened switch stack with normal at ", switch)
                                    else:
                                        lines = game.change_switch(i, "reverse", lines)
                                        switch_stack.append((switch,i,direction, False, "reverse"))
                                        # x, y, last_switch, switch_stack, direction, lines, coords = self.go_back_to_last_switch(trains, switch_stack, game, coords, lines)
                                        # restart = True
                                        # break
                                else:
                                    switch_stack.append((switch,i, direction, False, None))
                                    print("pretend the switch is normal at ", switch)
                                    if direction == "left":
                                        x -= 1
                                    else:
                                        x += 1
                                    coords.append((x, y))
                                    restart = True
                                    break
                        else:
                            if last_char not in "a[]bc":
                                if game.get_switch_position(i, game.lines) == "reverse" or not self.duplicate_train_route_check(x, y, trains):
                                    switch_stack.append((switch,i, direction, True, "reverse"))
                                    print("change trailing switch to reverse at ", switch)
                                else:
                                    x, y, last_switch, switch_stack, direction, lines, coords = self.go_back_to_last_switch(trains, switch_stack, game, coords, lines)
                                    restart = True
                                    break
                            else:
                                if game.get_switch_position(i, game.lines) == "normal" or not self.duplicate_train_route_check(x, y, trains):
                                    switch_stack.append((switch,i, direction, True, "normal"))
                                    print("change trailing switch to normal at ", switch)
                                else:
                                    x, y, last_switch, switch_stack, direction, lines, coords = self.go_back_to_last_switch(trains, switch_stack, game, coords, game.lines)
                                    restart = True
                                    break
                if last_char in "yz" and self.duplicate_train_route_check(x, y, trains):
                    x,y, last_switch, switch_stack, direction, lines, coords = self.go_back_to_last_switch(trains, switch_stack, game, coords, lines)
                    restart = True
                if restart:
                    restart = False
                    continue
                x, y, direction, last_char, new_direction_change, last_last_char, self.temporary_characters = game.path_find(lines, x, y, direction, self.direction, last_char, last_last_char, self.temporary_characters)
                game.handle_temporary_characters(self.temporary_characters)
                if x == -1 or last_char == "x":
                    x, y, last_switch, switch_stack, direction, lines, coords = self.go_back_to_last_switch(trains, switch_stack, game, coords, lines)
                    last_char = "a"
                    continue
                if new_direction_change:
                    direction_change = new_direction_change
                print(x,y, last_char)
                coords.append((x, y))
                values = self.duplicate_signal_route_check(x, y, exit_signal, direction, switch_stack, game, coords, lines, signals, trains)
                if values:
                    x, y, last_switch, switch_stack, direction, lines, coords = values
                if (x+2,y) == exit_signal.coord and exit_signal.buffer:
                    break
                if (x-2,y) == exit_signal.coord and exit_signal.buffer:
                    break
                if (x,y) == exit_signal.overlap and exit_signal.direction == direction:
                    break
                elif (x > (exit_signal.coord[0] + 10) and exit_signal.direction == 'right' and direction == 'right') or (x < (exit_signal.coord[0] - 10) and exit_signal.direction == 'left' and direction == 'left') or not (0 <= y < len(lines) and 0 <= x < len(lines[y])):
                    x, y, last_switch, switch_stack, direction, lines, coords = self.go_back_to_last_switch(trains, switch_stack, game, coords, lines)


            for switch in switch_stack:
                if switch[4] == "reverse":
                    switch_index = switch[1]
                    game.lines = game.change_switch(switch_index, "reverse", game.lines)
                    print("afterwards changing switch to reverse at ", switch, game.lines[switch[0][1]][switch[0][0]])
                else:
                    switch_index = switch[1]
                    game.lines = game.change_switch(switch_index, "normal", game.lines)
                    print("afterwards changing switch to normal at ", switch)
            direction_to_test_change = False
            for coord in coords:
                x,y = coord
                
                for i,switch in enumerate(switches):
                    if direction_change and ((x,y) == direction_change[0] or direction_to_test_change):
                        if self.direction == "left":
                            direction_to_test = "right"
                        else:
                            direction_to_test = "left"
                        direction_to_test_change = True
                    else:
                        direction_to_test = self.direction
                    if x == switch[0] and y == switch[1] and switch[3] == direction_to_test and (switch,i,direction_to_test, False, None) not in switch_stack:
                        game.lines = game.change_switch(i, "reverse", game.lines)
                        print("finally changing switch to reverse at ", switch, game.lines[switch[1]][switch[0]])
            self.route_coords = list(set(coords))
            return list(set(coords))
        except Exception as e:
            game.display_class.add_log("route setting failed, please try again error message: ", str(e))
            game.reset_temporary_characters(self.temporary_characters)
            self.temporary_characters = []

    def duplicate_train_route_check(self, x, y, trains):
        for train in trains:
            if train.route_coords:
                if (x, y) in train.route_coords:
                    print(train.route_coords)
                    print("route collision detected at ", (x,y))
                    return True
            for coord_list in train.coords:
                if (x, y) in coord_list:
                    print("train collision detected at ", (x,y))
                    return True
        return False
        
    def duplicate_signal_route_check(self, x, y, exit_signal, direction, switch_stack, game, coords, lines, signals, trains):
        intersection = []
        for signal in signals:
            if signal != exit_signal and (x, y+1) == signal.coord and signal.direction == direction and signal.mount == "down":
                return (self.go_back_to_last_switch(trains, switch_stack, game, coords, lines))
            elif signal != exit_signal and (x, y-1) == signal.coord and signal.direction == direction and signal.mount == "up":
                return (self.go_back_to_last_switch(trains, switch_stack, game, coords, lines))
            coord_set = set(coords)
            if signal.route_coords is None:
                continue
            signal_coord_set = set(signal.route_coords)
            intersection =  coord_set & signal_coord_set
            if len(intersection) > 0:
                return (self.go_back_to_last_switch(trains, switch_stack, game, coords, lines))

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

        game.reset_temporary_characters(self.temporary_characters)
        self.temporary_characters = []

    def go_back_to_last_switch(self, trains, switch_stack, game, coords, lines):
        is_trailing = True
        while is_trailing:
            last_switch_tuple = switch_stack.pop()
            is_trailing = last_switch_tuple[3]
        last_switch = last_switch_tuple[0]
        direction = last_switch_tuple[2]
        x = last_switch[0]
        y = last_switch[1]
        result = self.duplicate_train_route_check(x, y, trains)
        if result and game.get_switch_position(last_switch_tuple[1], game.lines) != last_switch_tuple[4]:
            print("checked last switch and train occupied normal")
            return self.go_back_to_last_switch(trains, switch_stack, game, coords, lines)
        
        
        print("going back to switch at location", last_switch)
        last_switch_index = last_switch_tuple[1]
        lines = game.change_switch(last_switch_index, "reverse", lines)
        print("reversing switch at", last_switch)
        for i in range(len(coords)):
            if coords.pop() == (x,y):
                coords.append((x, y))
                break
        print("finished go back to last switch, new location is ", (x,y))
        return x, y, last_switch, switch_stack, direction, lines, coords

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
        if not self.route_coords:
            return False
        if self.signal_type == "manual":
            for train in trains:
                flattened_train_coords = set([coord for sublist in train.coords for coord in sublist])
                route_coords_set = set(self.route_coords)
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