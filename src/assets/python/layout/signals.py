from collections import deque
class Signal:
    def __init__(
        self, name, coord, signal_type, color, direction, mount,
        possible_next_signals=None, next_signal=None, train_in_block=False, buffer = False
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
        self.route_coords = None
        self.auto = False

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
                self.color = "yellow"
            else:
                self.color = "green"
        else:
            self.color = "red"
            

    def get_coords_to_next_signal(self, exit_signal, game, switches, filename, signals):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                original_text = f.read()
            right_up = ['k','{']
            right_down = ["i","o"]
            left_up = ['h',"n"]
            left_down = ['j','}']
            both_up = ["z"]
            both_down = ["y"]
            switch_stack = deque()
            skip_parts_horizontal = False
            skip_parts_vertical = False
            block_horizontal = False
            block_vertical = False
            direction = self.direction
            last_char = "F"
            direction_change = None
            if not exit_signal:
                return []

            x, y = self.coord
            coords = deque()
            
            if self.mount == 'up':
                y += 1
            elif self.mount == 'down':
                y -= 1
            last_switch = None
            game_text = game.text
            while True:
                lines = original_text.splitlines()
                # if not (0 <= y < len(lines) and 0 <= x < len(lines[y])):
                #     break
                
                for i,switch in enumerate(switches):
                    if x == switch[0] and y == switch[1]:
                        if switch[3] == direction:
                            if switch != last_switch:
                                switch_stack.append((switch,i, direction))
                                game_text = game.change_switch(i, text=game_text)
                                print("change switch to normal at ", switch)
                                # print("switch found")
                        else:
                            if char != "a":
                                game_text = game.change_switch(i, switch_direction = "reverse", text=game_text)
                                print("change trailing switch to reverse at ", switch)
                            else:
                                game_text = game.change_switch(i, text=game_text)
                                print("change trailing switch to normal at ", switch)
                char = lines[y][x]
                if char == "÷":
                    if not block_horizontal:
                        block_horizontal = True
                    else:
                        block_horizontal = False
                        skip_parts_horizontal = False
                if char == "ö":
                    if not block_vertical:
                        # print("block vertical")
                        block_vertical = True
                    else:
                        # print("skip parts false")
                        block_vertical = False
                        skip_parts_vertical = False
                if char in "|ö":
                    print(direction)
                    if (last_char in right_up and direction == 'right') or (last_char in left_up and direction == 'left'):
                        direction = "up"
                    elif (last_char in right_down and direction == 'right') or (last_char in left_down and direction == 'left'):
                        print("direction is down")
                        direction = "down"
                if direction == "right":
                    next_char = lines[y][x+1]
                elif direction == "left":
                    next_char = lines[y][x-1]
                elif direction == "up":
                    next_char = lines[y-1][x]
                elif direction == "down":
                    next_char = lines[y+1][x]
                if next_char == "÷":
                    skip_parts_horizontal = True
                elif next_char == "ö":
                    skip_parts_vertical = True
                if skip_parts_horizontal:
                    if direction == 'right':
                        x += 1
                    elif direction == 'left':
                        x -= 1
                    continue
                elif skip_parts_vertical:
                    if direction == 'up':
                        y -= 1
                    elif direction == 'down':
                        y += 1
                    continue
                if (char in right_up and direction == 'right') or (char in left_up and direction == 'left'):
                    y -= 1
                elif (char in right_down and direction == 'right') or (char in left_down and direction == 'left'):
                    y += 1
                elif char in "|ö":
                    if direction == "up":
                        y -= 1
                    elif direction == "down":
                        y += 1
                elif direction == "up" or direction == "down":
                    if char in "ik":
                        direction = "left"
                        if direction != self.direction:
                            direction_change = [(x,y), direction]
                        x -= 1
                    elif char in "hj":
                        direction = "right"
                        if direction != self.direction:
                            direction_change = [(x,y), direction]
                        x += 1
                else:
                    # print("move")
                    if char in both_up:
                        y -= 1
                    elif char in both_down:
                        y += 1
                    if direction == 'right':
                        x += 1
                    elif direction == 'left':
                        x -= 1
                coords.append((x, y))

                intersection = []
                for signal in signals:
                    if signal != exit_signal and (x, y+1) == signal.coord and signal.direction == direction and signal.mount == "down":
                        # print(0 <= y < len(lines) and 0 <= x < len(lines[y]))
                        print(x, exit_signal.coord[0], exit_signal.direction)
                        last_switch_tuple = switch_stack.pop()
                        last_switch = last_switch_tuple[0]
                        direction = last_switch_tuple[2]
                        print("going back to switch at location", last_switch)
                        last_switch_index = last_switch_tuple[1]
                        original_text = game.change_switch(last_switch_index, "reverse",text = original_text)
                        # game_text = game.change_switch(last_switch_index, "reverse", text=game_text)
                        print("reversing switch at", last_switch)
                        x = last_switch[0]
                        y = last_switch[1]
                        for i in range(len(coords)):
                            if coords.pop() == (x,y):
                                coords.append((x, y))
                                break
                    elif signal != exit_signal and (x, y-1) == signal.coord and signal.direction == direction and signal.mount == "up":
                        # print(0 <= y < len(lines) and 0 <= x < len(lines[y]))
                        print(x, exit_signal.coord[0], exit_signal.direction)
                        last_switch_tuple = switch_stack.pop()
                        last_switch = last_switch_tuple[0]
                        direction = last_switch_tuple[2]
                        print("going back to switch at location", last_switch)
                        last_switch_index = last_switch_tuple[1]
                        original_text = game.change_switch(last_switch_index, "reverse",text = original_text)
                        # game_text = game.change_switch(last_switch_index, "reverse", text=game_text)
                        print("reversing switch at", last_switch)
                        x = last_switch[0]
                        y = last_switch[1]
                        for i in range(len(coords)):
                            if coords.pop() == (x,y):
                                coords.append((x, y))
                                break
                    if signal == self:
                        continue
                    coord_set = set(coords)
                    if signal.route_coords is None:
                        continue
                    signal_coord_set = set(signal.route_coords)
                    intersection =  coord_set & signal_coord_set
                    if len(intersection) > 0:
                        print("intersection", intersection)
                        break
                if (x+2,y) == exit_signal.coord and exit_signal.buffer:
                    break
                if (x-2,y) == exit_signal.coord and exit_signal.buffer:
                    break
                if (x, y+1) == exit_signal.coord:
                    break
                elif (x, y-1) == exit_signal.coord:
                    break
                
                elif (x > exit_signal.coord[0] and exit_signal.direction == 'right' and direction == 'right') or (x < exit_signal.coord[0] and exit_signal.direction == 'left' and direction == 'left') or (len(intersection) > 0) or not (0 <= y < len(lines) and 0 <= x < len(lines[y])):
                    # print(0 <= y < len(lines) and 0 <= x < len(lines[y]))
                    print(x, exit_signal.coord[0], exit_signal.direction)
                    last_switch_tuple = switch_stack.pop()
                    last_switch = last_switch_tuple[0]
                    direction = last_switch_tuple[2]
                    print("going back to switch at location", last_switch)
                    last_switch_index = last_switch_tuple[1]
                    original_text = game.change_switch(last_switch_index, "reverse",text = original_text)
                    # game_text = game.change_switch(last_switch_index, "reverse", text=game_text)
                    print("reversing switch at", last_switch)
                    x = last_switch[0]
                    y = last_switch[1]
                    for i in range(len(coords)):
                        if coords.pop() == (x,y):
                            coords.append((x, y))
                            break
                last_char = char
            for switch in switch_stack:
                switch_index = switch[1]
                # switch_position = game.get_switch_position(switch_index, original_text)
                game_text = game.change_switch(switch_index, "normal", text=game_text)
            for coord in coords:
                x,y = coord
                direction_to_test_change = False
                for i,switch in enumerate(switches):
                    if direction_change and ((x,y) == direction_change[0] or direction_to_test_change):
                        direction_to_test = ["left","right"].remove(self.direction)
                    else:
                        direction_to_test = self.direction
                    if x == switch[0] and y == switch[1] and switch[3] == direction_to_test and (switch,i,direction_to_test) not in switch_stack:
                        game_text = game.change_switch(i, "reverse", text=game_text)
                    else:
                        print(switch, i, direction, switch_stack, x, y)
            self.route_coords = coords
            game.text = game_text
            return coords
        except:
            print("route setting failed, please try again")

    def cancel_route(self, display, text, autos, game):
        if self.signal_type == "manual" and self.route_set and self.route_coords:
            self.route_set = False
            self.next_signal = None
            self.color = "red"
            for coord in self.route_coords:
                x, y = coord
                if display.get_char_color_at_coord(x, y, text) == (255, 255, 255):
                    display.set_char_color_at_coord(x, y, "gray", text)
            for auto in autos:
                if auto.signal == self:
                    auto.depressed(text, game)
            self.route_coords = None


    def check_for_trains_in_section(self, trains):
        if not self.route_coords:
            return False
        if self.signal_type == "manual":
            for train in trains:
                if train.coords[0] in self.route_coords or train.coords[-1] in self.route_coords:
                    return True
        return False