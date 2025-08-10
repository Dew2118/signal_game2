import pygame
from collections import deque
from io import StringIO
class Train:
    def __init__(self, length, coords, direction, headcode, timetable, game_seconds_at_spawn,annotated_segments):
        self.length = length
        self.coords = coords  # List of (x, y) tuples
        self.last_move_time = game_seconds_at_spawn  # Timestamp for last move
        self.last_signal = deque()
        self.direction = direction
        self.headcode = headcode
        self.headcode_element = deque()
        self.wait_time = 1
        self.timetable = timetable
        self.game_seconds_at_spawn = game_seconds_at_spawn
        self.annotated_segments = annotated_segments
        self.current_stop_index = 0
        self.start_to_stop_time = 0
        self.waiting_for_departure = False
        self.last_char = "F"
        self.real_first_coord = self.coords[0]
        self.skip_parts_horizontal = False
        self.skip_parts_vertical = False
        self.block_horizontal = False
        self.block_vertical = False
    def _get_stop_coord(self, stop):
        """
        Returns the coord (x, y) from annotated segments matching station & platform.
        """
        target_station = stop.get("station")
        target_platform = stop.get("platform")
        if target_platform == '':
            stop_coords = []
            for segment in self.annotated_segments:
                if segment.get("station") == target_station:
                    # Return one end of the platform (use left or right based on train direction)
                    if self.direction == "right":
                        stop_coords.append(segment.get("right", segment.get("end")))
                    else:
                        stop_coords.append(segment.get("left", segment.get("start")))
            return stop_coords
        for segment in self.annotated_segments:
            if segment.get("station") == target_station and segment.get("platform") == target_platform:
                # Return one end of the platform (use left or right based on train direction)
                if self.direction == "right":
                    return [segment.get("right", segment.get("end"))]
                else:
                    return [segment.get("left", segment.get("start"))]
        
        return None  # 🚨 Not found
    def _at_stop_coord(self, stop_coords):
        """
        Check if train's head is at stop_coord, or one tile above or below.
        """
        if not stop_coords or not self.coords:
            return False
        x, y = self.coords[0]
        for stop_coord in stop_coords:
            sx, sy = stop_coord
            if (x == sx and abs(y - sy) <= 1):
                return True
        return False
    
    def move(self, text, game, signals, display):
        """
        Move the train by pathfinding from the current head position.
        Uses the same rules as signal pathfinding.
        If display is provided, reset the color of the popped coord.
        Only move if 1 second has passed since last move.
        Before moving, check for blocking signals above/below.
        """
        right_up = ['k','{']
        right_down = ["i","o"]
        left_up = ['h',"n"]
        left_down = ['j','}']
        both_up = ["z"]
        both_down = ["y"]
        
        now = game.game_seconds
        # print(now, self.last_move_time, self.wait_time)
        if now - self.last_move_time < self.wait_time:
            return  # Don't move yet
        if self.wait_time == 2:
            self.wait_time = 1
        if not self.coords:
            return

        # 🚦 Timetable departure check
        # print(self.timetable)
        if self.timetable and self.current_stop_index < len(self.timetable):
            current_stop = self.timetable[self.current_stop_index]
            stop_coords = self._get_stop_coord(current_stop)  # defined below
            # Only apply timing logic if head is at the stop
            if self._at_stop_coord(stop_coords):
                current_game_time = game.game_seconds
                time_since_spawn = current_game_time - self.game_seconds_at_spawn
                if not self.start_to_stop_time:
                    self.start_to_stop_time = time_since_spawn
                dep_offset = current_stop.get('departure_offset', 0)
                if "change_timetable" in current_stop:
                    print("found change tt")
                    tt_index = current_stop["change_timetable"]
                    self.timetable, tt_headcode_prefix, new_direction = game.get_tt_from_index(tt_index)
                    if self.direction != new_direction:
                        self.direction = new_direction
                        self.coords.reverse()
                        self.real_first_coord = self.coords[0]
                    print("headcode prefix is ", tt_headcode_prefix)
                    self.headcode = game.get_headcode_from_prefix(tt_headcode_prefix)
                    self.current_stop_index = 0
                    self.game_seconds_at_spawn += dep_offset
                    time_since_spawn = current_game_time - self.game_seconds_at_spawn
                    self.start_to_stop_time = time_since_spawn
                    self.set_headcode(text, game)
                    print("new game second at spawn is ", self.game_seconds_at_spawn)
                if current_stop.get("reverse_direction"):
                    self.direction = "left" if self.direction == "right" else "right"
                    self.coords.reverse()
                    self.real_first_coord = self.coords[0]
                if current_stop.get("despawn"):
                    self.despawn_train(text, display, game)
                    game.despawn_train(self)
                    return
                if time_since_spawn < dep_offset:
                    return  # ⛔ Guard: Not time to leave yet
                
                elif (time_since_spawn - self.start_to_stop_time) < 2:
                    # print(time_since_spawn, self.start_to_stop_time)
                    return
                # ✅ Time to leave, move to next stop
                self.current_stop_index += 1
            else:
                self.start_to_stop_time = 0
            x, y = self.coords[0]  # Head of the train
            # Check for blocking signals above (y+1) and below (y-1)
            if signals:
                for signal in signals:
                    # if signal.coord == (x+2,y) and signal.buffer:
                    #     self.direction = 'left'
                    #     self.coords.reverse()
                    #     return
                    if signal.coord == (x, y - 1):
                        if (signal.mount == "up" and signal.direction == self.direction):
                            if signal.color == "red":
                                return
                            signal.train_in_block = True
                            if not signal.auto:
                                signal.route_set = False
                                signal.route_coords = []
                            self.last_signal.append(signal)
                    elif signal.coord == (x, y + 1):
                        if (signal.mount == "down" and signal.direction == self.direction):
                            if signal.color == "red":
                                return
                            signal.train_in_block = True
                            if not signal.auto:
                                signal.route_set = False
                                signal.route_coords = []
                            self.last_signal.append(signal)
                    elif (signal.coord == (x-self.length,y - 1) and self.direction == 'right') or (signal.coord == (x+self.length,y - 1) and self.direction == 'left'):
                        if (signal.mount == "up" and signal.direction == self.direction and len(self.last_signal) > 1):
                            last_signal = self.last_signal.popleft()
                            last_signal.train_in_block = False
                            
                    elif (signal.coord == (x-self.length,y + 1) and self.direction == 'right') or (signal.coord == (x+self.length,y + 1) and self.direction == 'left'):
                        if (signal.mount == "down" and signal.direction == self.direction and len(self.last_signal) > 1):
                            last_signal = self.last_signal.popleft()
                            last_signal.train_in_block = False


            self.last_move_time = now  # Update timestamp
            if self.real_first_coord != self.coords[0]:
                x,y = self.real_first_coord
            signal_lookup = {coord: True for coord in self.coords}
            lines = text.splitlines()

            # Pathfinding logic (single step)
            char = lines[y][x]
            if char == "÷":
                if not self.block_horizontal:
                    self.block_horizontal = True
                    print("block horizontal")
                else:
                    # self.real_first_coord = self.coords[0]
                    print("skip parts false")
                    self.block_horizontal = False
                    self.skip_parts_horizontal = False
            if char == "ö":
                if not self.block_vertical:
                    # print("block vertical")
                    self.block_vertical = True
                else:
                    # print("skip parts false")
                    self.block_vertical = False
                    self.skip_parts_vertical = False
            elif char in "|ö":
                if (self.last_char in right_up and self.direction == 'right') or (self.last_char in left_up and self.direction == 'left'):
                    self.direction = "up"
                elif (self.last_char in right_down and self.direction == 'right') or (self.last_char in left_down and self.direction == 'left'):
                    self.direction = "down"
            if self.direction == "right":
                next_char = lines[y][x+1]
            elif self.direction == "left":
                next_char = lines[y][x-1]
            elif self.direction == "up":
                next_char = lines[y-1][x]
            elif self.direction == "down":
                next_char = lines[y+1][x]
            if next_char == "÷":
                print("skip part horizontal")
                passed = False
                trash = False
                while passed == False:
                    if self.direction == 'right':
                        print('mov right')
                        x += 1
                    elif self.direction == 'left':
                        print('mov left')
                        x -= 1
                    # x += 1
                    char = lines[y][x]
                    if char == "÷":
                        if not trash:
                            trash = True
                        else:
                            passed = True
                            break
                # self.skip_parts_horizontal = True
            elif next_char == "ö":
                print("skip part horizontal")
                passed = False
                trash = False
                while passed == False:
                    if self.direction == 'down':
                        print('mov right')
                        y += 1
                    elif self.direction == 'up':
                        print('mov left')
                        y -= 1
                    # x += 1
                    char = lines[y][x]
                    if char == "ö":
                        if not trash:
                            trash = True
                        else:
                            passed = True
                            break
                # self.skip_parts_vertical = True
            # print(self.skip_parts_horizontal)
            # if self.skip_parts_horizontal:
            #     if self.direction == 'right':
            #         print('mov right')
            #         x += 1
            #     elif self.direction == 'left':
            #         print('mov left')
            #         x -= 1
            #     self.real_first_coord = (x,y)
            #     return
            # elif self.skip_parts_vertical:
            #     if self.direction == 'up':
            #         y -= 1
            #     elif self.direction == 'down':
            #         y += 1
            #     self.real_first_coord = (x,y)
            #     return
            if (char in right_up and self.direction == 'right') or (char in left_up and self.direction == 'left'):
                y -= 1
            elif (char in right_down and self.direction == 'right') or (char in left_down and self.direction == 'left'):
                y += 1
            elif char in "|ö":
                if self.direction == "up":
                    y -= 1
                elif self.direction == "down":
                    y += 1
            elif self.direction == "up" or self.direction == "down":
                if char in "ik":
                    self.direction = "left"
                    x -= 1
                elif char in "hj":
                    self.direction = "right"
                    x += 1
            else:
                # print("move")
                if char in both_up:
                    y -= 1
                elif char in both_down:
                    y += 1
                if self.direction == 'right':
                    x += 1
                elif self.direction == 'left':
                    x -= 1
            self.last_char = char
            # Check bounds
            if 0 <= y < len(lines) and -10 <= x < len(lines[y]) + 10:
                new_head = (x, y)
                self.real_first_coord = new_head
                self.coords.insert(0, new_head)
                if len(self.coords) > self.length:
                    popped = self.coords.pop()
                    if display is not None:
                        set_to_white = False
                        for signal in signals:
                            if not popped or not signal.route_coords:
                                continue
                            if popped in signal.route_coords or (self.last_signal and self.last_signal[0].auto):
                                set_to_white = True
                                display.set_char_color_at_coord(popped[0], popped[1], "white",text)
                                break
                        if not set_to_white:
                            display.set_char_color_at_coord(popped[0], popped[1], "gray",text)
                self.get_new_headcode_element(text, game)

    def get_new_headcode_element(self, text, game):
        x,y = self.coords[1]
        f = StringIO(text)
        lines = f.readlines()
        char = lines[y][x]
        self.headcode_element.append(char)
        grid = [list(line.rstrip('\n')) for line in lines]
        if len(self.headcode_element) > 4:
            last_char = self.headcode_element.popleft()
            x,y = self.coords[5]
            grid[y][x] = last_char
        for i,coords in enumerate(self.coords):
            if i >= 1 and i <= 4:
                if self.direction == 'right':
                    char = self.headcode[-i]
                else:
                    char = self.headcode[i-1]
                x, y = coords
                grid[y][x] = char

        modified_text = '\n'.join(''.join(row) for row in grid)
        game.text = modified_text
        
    def set_headcode(self, text, game):
        f = StringIO(text)
        lines = f.readlines()
        grid = [list(line.rstrip('\n')) for line in lines]
        for i,coords in enumerate(self.coords):
            if i >= 1 and i <= 4:
                if self.direction == 'right':
                    char = self.headcode[-i]
                else:
                    char = self.headcode[i-1]
                x, y = coords
                grid[y][x] = char

        modified_text = '\n'.join(''.join(row) for row in grid)
        game.text = modified_text
        

    def display_on(self, display, text):
        """
        Turn every coord in the train red on the display.
        """
        for i,coord in enumerate(self.coords):
            x,y = coord
            if i >= 1 and i <= 4:
                display.set_char_color_at_coord(x, y, "light blue", text)
            else:
                display.set_char_color_at_coord(x, y, "red", text)

    def station_check(self, text):
        x, y = self.coords[0]
        lines = text.splitlines()
        if self.direction == 'right':
            additive = 1
        else:
            additive = -1
        if x-3 < 0:
            return
        if lines[y+1][x] == "¯" and lines[y+1][x + additive] != "¯":
            self.wait_time = 2
        elif lines[y-1][x] == "¯" and lines[y-1][x + additive] != "¯":
            self.wait_time = 2
    
    def bounds_check(self, text,display, game):

        x, y = self.coords[0]
        f = StringIO(text)
        lines = f.readlines()
        grid = [list(line.rstrip('\n')) for line in lines]
        if x <= 0 or x > len(lines[y]):
            print("failed bounds check")
            self.despawn_train(text, display, game)
            return False
        return True
    
    def despawn_train(self, text, display, game):
        f = StringIO(text)
        lines = f.readlines()
        grid = [list(line.rstrip('\n')) for line in lines]
        for i,coords in enumerate(self.coords):
            x, y = coords
            if i >= 1 and i <= 4:
                char = self.headcode_element.pop()
                grid[y][x] = char
        modified_text = '\n'.join(''.join(row) for row in grid)
        game.text = modified_text
        for i,coords in enumerate(self.coords):
            x, y = coords
            if self.last_signal and self.last_signal[0].route_set:
                display.set_char_color_at_coord(x, y, "white",modified_text)
            else:
                display.set_char_color_at_coord(x, y, "gray",modified_text)
        
        for last_signal in self.last_signal:
            last_signal.train_in_block = False
        
        
        
