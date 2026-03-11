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
            game_text = game.text
            restart = False
            lines = original_text.splitlines()
            while True:
                # lines = original_text.splitlines()
                
                # print("current location: ", (x,y), " current direction: ", direction, " last char: ", last_char)
                for i,switch in enumerate(switches):
                    if x == switch[0] and y == switch[1]:
                        if switch[3] == direction:
                            if switch != last_switch:
                                if self.duplicate_train_route_check(x, y, trains):
                                    if game.get_switch_position(i, game_text) == "normal":
                                        switch_stack.append((switch,i, direction, False, None))
                                        print("appened switch stack with normal at ", switch)
                                    else:
                                        switch_stack.append((switch,i,direction, False, None))
                                        x, y, last_switch, switch_stack, direction, original_text, coords = self.go_back_to_last_switch(trains, switch_stack, game, coords, original_text)
                                        lines = original_text.splitlines()
                                        restart = True
                                        break
                                else:
                                    switch_stack.append((switch,i, direction, False, None))
                                    # game_text = game.change_switch(i, text=game_text)
                                    print("pretend the switch is normal at ", switch)
                                    if direction == "left":
                                        x -= 1
                                    else:
                                        x += 1
                                    coords.append((x, y))
                                    restart = True
                                    break
                                # print("switch found")
                        else:
                            if last_char not in "a[]bc":
                                if game.get_switch_position(i, game_text) == "reverse" or not self.duplicate_train_route_check(x, y, trains):
                                    # game_text = game.change_switch(i, switch_direction = "reverse", text=game_text)
                                    switch_stack.append((switch,i, direction, True, "reverse"))
                                    print("change trailing switch to reverse at ", switch)
                                else:
                                    
                                    x, y, last_switch, switch_stack, direction, original_text, coords = self.go_back_to_last_switch(trains, switch_stack, game, coords, original_text)
                                    lines = original_text.splitlines()
                                    restart = True
                                    break
                            else:
                                if game.get_switch_position(i, game_text) == "normal" or not self.duplicate_train_route_check(x, y, trains):
                                    # game_text = game.change_switch(i, text=game_text)
                                    switch_stack.append((switch,i, direction, True, "normal"))
                                    print("change trailing switch to normal at ", switch)
                                else:
                                    x, y, last_switch, switch_stack, direction, original_text, coords = self.go_back_to_last_switch(trains, switch_stack, game, coords, original_text)
                                    lines = original_text.splitlines()
                                    restart = True
                                    break
                if last_char in "yz" and self.duplicate_train_route_check(x, y, trains):
                    x,y, last_switch, switch_stack, direction, original_text, coords = self.go_back_to_last_switch(trains, switch_stack, game, coords, original_text)
                    lines = original_text.splitlines()
                    restart = True
                if restart:
                    restart = False
                    continue
                x, y, direction, last_char, new_direction_change, last_last_char = game.path_find(lines, x, y, direction, self.direction, last_char, last_last_char)
                if x == -1 or last_char == "x":
                    x, y, last_switch, switch_stack, direction, original_text, coords = self.go_back_to_last_switch(trains, switch_stack, game, coords, original_text)
                    lines = original_text.splitlines()
                    last_char = "a"
                    print("NEW X IS ", x)
                    continue
                if new_direction_change:
                    direction_change = new_direction_change
                print(x,y, last_char)
                coords.append((x, y))
                values = self.duplicate_signal_route_check(x, y, exit_signal, direction, switch_stack, game, coords, original_text, signals, trains)
                if values:
                    x, y, last_switch, switch_stack, direction, original_text, coords = values
                    lines = original_text.splitlines()
                if (x+2,y) == exit_signal.coord and exit_signal.buffer:
                    break
                if (x-2,y) == exit_signal.coord and exit_signal.buffer:
                    break
                if (x,y) == exit_signal.overlap and exit_signal.direction == direction:
                    break
                elif (x > (exit_signal.coord[0] + 10) and exit_signal.direction == 'right' and direction == 'right') or (x < (exit_signal.coord[0] - 10) and exit_signal.direction == 'left' and direction == 'left') or not (0 <= y < len(lines) and 0 <= x < len(lines[y])):
                    x, y, last_switch, switch_stack, direction, original_text, coords = self.go_back_to_last_switch(trains, switch_stack, game, coords, original_text)
                    lines = original_text.splitlines()


            for switch in switch_stack:
                if switch[4] == "reverse":
                    switch_index = switch[1]
                    game_text = game.change_switch(switch_index, "reverse", text=game_text)
                    print("afterwards changing switch to reverse at ", switch)
                else:
                    switch_index = switch[1]
                    game_text = game.change_switch(switch_index, "normal", text=game_text)
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
                        game_text = game.change_switch(i, "reverse", text=game_text)
                        print("finally changing switch to reverse at ", switch)
            self.route_coords = list(set(coords))
            game.text = game_text
            game.update_lines()
            return list(set(coords))
        except Exception as e:
            game.display_class.add_log("route setting failed, please try again error message: ", str(e))

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
        
    def duplicate_signal_route_check(self, x, y, exit_signal, direction, switch_stack, game, coords, original_text, signals, trains):
        intersection = []
        for signal in signals:
            if signal != exit_signal and (x, y+1) == signal.coord and signal.direction == direction and signal.mount == "down":
                return (self.go_back_to_last_switch(trains, switch_stack, game, coords, original_text))
            elif signal != exit_signal and (x, y-1) == signal.coord and signal.direction == direction and signal.mount == "up":
                return (self.go_back_to_last_switch(trains, switch_stack, game, coords, original_text))
            coord_set = set(coords)
            if signal.route_coords is None:
                continue
            signal_coord_set = set(signal.route_coords)
            intersection =  coord_set & signal_coord_set
            if len(intersection) > 0:
                return (self.go_back_to_last_switch(trains, switch_stack, game, coords, original_text))

    def skip_parts(self, character, direction, x, y, lines):
        passed = False
        trash = False
        while passed == False:
            if direction == 'down':
                y += 1
            elif direction == 'up':
                y -= 1
            elif direction == 'left':
                x -= 1
            elif direction == 'right':
                x += 1
            char = lines[y][x]
            if char == character:
                if not trash:
                    trash = True
                else:
                    passed = True
                    break
        return x, y

    def cancel_route(self, display, text, lines, autos, game):
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
                    display.set_char_color_at_coord(x, y, "gray", text)
            for auto in autos:
                if auto.signal == self:
                    auto.depressed(text, game)
            self.route_coords = None
            # game.update_signals()

    def go_back_to_last_switch(self, trains, switch_stack, game, coords, original_text):
        is_trailing = True
        while is_trailing:
            last_switch_tuple = switch_stack.pop()
            is_trailing = last_switch_tuple[3]
        last_switch = last_switch_tuple[0]
        direction = last_switch_tuple[2]
        x = last_switch[0]
        y = last_switch[1]
        # x = switch_stack[0][0][0]
        # y = switch_stack[0][0][1]
        result = self.duplicate_train_route_check(x, y, trains)
        if result and game.get_switch_position(last_switch_tuple[1], game.text) == "normal":
            print("checked last switch and train occupied normal")
            return self.go_back_to_last_switch(trains, switch_stack, game, coords, original_text)
        
        
        print("going back to switch at location", last_switch)
        last_switch_index = last_switch_tuple[1]
        original_text = game.change_switch(last_switch_index, "reverse",text = original_text)
        print("reversing switch at", last_switch)
        for i in range(len(coords)):
            if coords.pop() == (x,y):
                coords.append((x, y))
                break
        print("finished go back to last switch, new location is ", (x,y))
        return x, y, last_switch, switch_stack, direction, original_text, coords

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
    
    def activate_TRTS(self, game, display, text, lines):
        if not self.TRTS_button_coord:
            return
        # lines = text.splitlines()
        grid = [list(line.rstrip('\n')) for line in lines]
        x,y = self.TRTS_button_coord
        grid[y][x] = "q"
        display.set_char_color_at_coord(x, y, "white", text)
        modified_text = '\n'.join(''.join(row) for row in grid)
        game.text = modified_text
        game.update_lines()

    def deactivate_TRTS(self, game, display, text, lines):
        if not self.TRTS_button_coord:
            return
        # lines = text.splitlines()
        grid = [list(line.rstrip('\n')) for line in lines]
        x,y = self.TRTS_button_coord
        grid[y][x] = "p"
        display.set_char_color_at_coord(x, y, "orange", text)
        modified_text = '\n'.join(''.join(row) for row in grid)
        game.text = modified_text
        game.update_lines()