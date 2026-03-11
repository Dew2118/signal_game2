from collections import deque
from io import StringIO
from unittest import signals
import winsound
import threading
NOTIFIED_SOUND = r"C:\Windows\Media\chord.wav"
TRTS_SOUND = r"C:\Windows\Media\Windows Notify.wav"



class Train:
    def __init__(self, length, head_coord, direction, headcode, timetable, game_seconds_at_spawn,annotated_segments):
        self.length = length
        self.head_coord = head_coord
        self.coords = [[head_coord]]  # List of (x, y) tuples
        self.last_move_time = game_seconds_at_spawn  # Timestamp for last move
        self.last_signal = deque()
        self.direction = direction
        self.headcode = headcode
        self.headcode_element = []
        self.headcode_coords = []
        self.wait_time = 1
        self.timetable = timetable
        self.game_seconds_at_spawn = game_seconds_at_spawn
        self.annotated_segments = annotated_segments
        self.current_stop_index = 0
        self.start_to_stop_time = 0
        self.waiting_for_departure = False
        self.last_char = "F"
        self.last_last_char = "F"
        self.real_first_coord = self.coords[0][0]
        self.skip_parts_horizontal = False
        self.skip_parts_vertical = False
        self.block_horizontal = False
        self.block_vertical = False
        self.route_coords = []
        self.notified = False
        self.last_action = "remove train tail"
        self.notify_TRTS = False
        self.last_last_signal = None
        # self.last_colored_route_coords = []
        self.last_last_coord = [(0,0)]
        self.direction_change = None
        self.last_three_directions = deque(maxlen=3)

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
        coords = self.coords[0]
        for coord in coords:
            x, y = coord
            for stop_coord in stop_coords:
                sx, sy = stop_coord
                if (x == sx and abs(y - sy) <= 1):
                    return True
        return False
    
    def TRTS(self, time_difference, signals, game, display, text, lines):
        
        if time_difference >= 30:
            return
        if signals:
            x, y = self.coords[0][0]
            for signal in signals:
                if self.signal_condition_check(signal, x, y, self.direction):
                    if not self.notify_TRTS:
                        threading.Thread(target=winsound.PlaySound, args=(TRTS_SOUND, winsound.SND_FILENAME)).start()
                        display.add_log(f"train {self.headcode} TRTS at {signal.coord}")
                        self.notify_TRTS = True
                    if int(time_difference) % 2 == 1:
                        signal.activate_TRTS(game, display, text, lines)
                    else:
                        signal.deactivate_TRTS(game, display, text, lines)

    def timetable_check(self, game, text, lines, display, signals):
        current_stop = self.timetable[self.current_stop_index]
        stop_coords = self._get_stop_coord(current_stop)  # defined below
        # Only apply timing logic if head is at the stop
        if self._at_stop_coord(stop_coords):
            current_game_time = game.game_seconds
            time_since_spawn = current_game_time - self.game_seconds_at_spawn
            if not self.start_to_stop_time:
                self.start_to_stop_time = time_since_spawn
            dep_offset = current_stop.get('departure_offset', 0)
            if self.last_action == "move train":
                self.last_last_signal_check(game)
                self.delete_train_tail(display, game)
                self.last_action = "remove train tail"
            if "change_timetable" in current_stop:
                tt_index = current_stop["change_timetable"]
                self.timetable, tt_headcode_prefix, new_direction = game.get_tt_from_index(tt_index)
                if self.direction != new_direction:
                    self.direction = new_direction
                    self.real_first_coord = self.coords[0][0]
                    self.coords[0].reverse()
                # self.last_signal = deque()
                self.headcode = game.get_headcode_from_prefix(tt_headcode_prefix)
                self.current_stop_index = 0
                self.route_coords = []
                self.game_seconds_at_spawn += dep_offset
                time_since_spawn = current_game_time - self.game_seconds_at_spawn
                self.start_to_stop_time = time_since_spawn
                # # self.set_headcode(text, game)
                self.move_headcode(text, lines, game, game.signals, display)
                # print("new game second at spawn is ", self.game_seconds_at_spawn)
            if current_stop.get("reverse_direction"):
                if self.direction == "right":
                    self.direction = "left"
                else:
                    self.direction = "right"
                print("train direction reversed to ", self.direction)
                self.real_first_coord = self.coords[0][0]
                self.coords[0].reverse()
            if current_stop.get("despawn"):
                self.despawn_train(text, display, game)
                game.despawn_train(self)
                return False
            self.TRTS(dep_offset-time_since_spawn, game.signals, game, display, text, lines)
            if time_since_spawn < dep_offset:
                
                return False # ⛔ Guard: Not time to leave yet
            
            elif (time_since_spawn - self.start_to_stop_time) < 2:
                # print(time_since_spawn, self.start_to_stop_time)
                self.TRTS(dep_offset-time_since_spawn, game.signals, game, display, text, lines)
                return False
            # ✅ Time to leave, move to next stop
            x, y = self.coords[0][0]
            for signal in signals:
                if self.signal_condition_check(signal, x, y, self.direction) and signal.color == "red":
                    return False
                
            self.current_stop_index += 1
        else:
            self.start_to_stop_time = 0
        return True
    def move(self, text, lines, game, signals, display):
        """
        Move the train by pathfinding from the current head position.
        Uses the same rules as signal pathfinding.
        If display is provided, reset the color of the popped coord.
        Only move if 1 second has passed since last move.
        Before moving, check for blocking signals above/below.
        """
        now = int(game.game_seconds)
        if now - self.last_move_time < self.wait_time:
            return  # Don't move yet
        # if self.wait_time != 2:
        self.wait_time = len(self.coords[0])/2
        if not self.coords:
            return
        # 🚦 Timetable departure check
        if self.timetable and self.current_stop_index < len(self.timetable):
            if not self.timetable_check(game, text, lines, display, signals):
                return
            self.notify_TRTS = False
            x, y = self.coords[0][0]  # Head of the train
            # Check for blocking signals above (y+1) and below (y-1)
            if signals:
                # print("coord", self.coords[-1][0])
                for signal in signals:
                    # if signal.buffer:
                        # print(signal.overlap)
                        
                    if self.signal_condition_check(signal, x, y, self.direction):
                        if signal.color == "red" and self.last_action == "remove train tail":
                            if not self.notified:
                                threading.Thread(target=winsound.PlaySound, args=(NOTIFIED_SOUND, winsound.SND_FILENAME)).start()
                                self.notified = True
                                display.add_log(f"train {self.headcode} stopped at red signal at {signal.coord}")
                            return
                        self.notified = False
                        if self.last_action == "remove train tail":
                            signal.train_in_block = True
                            lines = signal.deactivate_TRTS(game, display, text, lines)
                            
                            # game.update_signals()
                            if not signal.auto:
                                signal.route_set = False
                                # game.update_signals()
                                if signal.route_coords:
                                    self.route_coords = signal.route_coords.copy()
                                    signal.route_coords = []
                                else:
                                    self.route_coords = []
                            self.last_signal.append(signal)
                            break
            self.last_last_signal_check(game)
            self.last_move_time = now  # Update timestamp
            # lines = text.splitlines()
            
            if self.last_action == "move train":
                self.delete_train_tail(display, game)
                self.last_action = "remove train tail"
            elif self.last_action == "remove train tail":
                self.move_train(x, y, lines, game, signals, display)
                self.last_action = "move train"
                print("finished move train")

            self.move_headcode(text, lines, game, signals, display)
            print("finished move")

    def last_last_signal_check(self, game):
        # print("train headcode is ", self.headcode, "its direction is ", self.direction)
        if self.direction_change:
            direction = self.last_three_directions[0]
            # print("the last direction is ", direction)
        else:
            direction = self.direction
        if len(self.last_signal) > 0 and self.signal_condition_check(self.last_signal[0], self.last_last_coord[0][0], self.last_last_coord[0][1], direction) and self.last_action == "move train":
            self.last_last_signal = self.last_signal.popleft()
            # print("last last signal check passed ", self.last_last_signal.coord)
            self.last_last_signal.train_in_block = False
            # game.update_signals()
            

    def delete_train_tail(self, display, game):
        if len(self.coords) < 2:
            return
        self.last_last_coord = self.coords.pop()
        if self.direction_change and self.direction_change[0] in self.last_last_coord:
            print("direction change removed")
            self.direction_change = None
        # print("deleting train tail at coords ", self.last_last_coord)
        for coord in self.last_last_coord:
            
            if coord in self.route_coords:
                self.route_coords.remove(coord)
                # print("removed ", coord, " from route coords, now ", self.route_coords)
            # if coord in self.last_colored_route_coords:
            #     self.last_colored_route_coords.remove(coord)
            if self.last_last_signal and self.last_last_signal.route_set and coord in self.last_last_signal.route_coords:
                display.set_char_color_at_coord(coord[0], coord[1], "white", game.text)
            
            else:
                
                set_to_white = False
                for signal in game.signals:
                    if signal.route_set and coord in signal.route_coords:
                        display.set_char_color_at_coord(coord[0], coord[1], "white", game.text)
                        set_to_white = True
                        break
                # for train in game.trains:
                #     # print("checking train ", train == self, train.route_coords, " for coord ", coord)
                #     if train != self and coord in train.route_coords:
                #         # print("setting coord ", coord, " to white because of train ", train.headcode)
                #         display.set_char_color_at_coord(coord[0], coord[1], "white", game.text)
                #         set_to_white = True
                #         break
                if not set_to_white:
                    display.set_char_color_at_coord(coord[0], coord[1], "gray", game.text)

    def move_train(self,x, y, lines, game, signals, display):
        if len(self.coords) >= 2:
            return
        coords = []
        while True:
            x, y, self.direction, self.last_char, direction_change, self.last_last_char = game.path_find(lines, x, y, self.direction, self.direction, self.last_char, self.last_last_char)
            if x == -1:
                return
            print("move train x, y, is ", x, y)
            coords.insert(0,(x,y))
            if direction_change:
                self.direction_change = direction_change
                print("direction change is ", direction_change)
            self.add_last_direction()
            if self.direction == "right":
                amended_x = x+1
                opposite_direction = "left"
                if (amended_x >= len(lines[y])) or (lines[y][x] in "b" or (lines[y][amended_x] in "c" and lines[y][x] in "a")):
                    self.coords.insert(0, coords)
                    print("blocked by ", lines[y][x], " or ", lines[y][amended_x], " at ", (x,y), " or ", (amended_x,y))
                    return
            else:
                amended_x = x-1
                opposite_direction = "right"
                if (amended_x < 0) or (lines[y][x] in "c" or (lines[y][amended_x] in "b" and lines[y][x] in "a")):
                    print("blocked by ", lines[y][x], " or ", lines[y][amended_x], " at ", (x,y), " or ", (amended_x,y))
                    self.coords.insert(0, coords)
                    return
            for signal in signals:
                if self.signal_condition_check(signal, x, y, self.direction) or self.signal_condition_check(signal, amended_x, y, opposite_direction):
                    # print("blocked by signal at ", signal.coord, " with color ", signal.color)
                    self.coords.insert(0, coords)
                    return
            if self.last_char == "x":
                # print("blocked by last char at ", (x,y))
                self.coords.insert(0, coords)
                return
                

    def signal_condition_check(self, signal, x, y, direction):
        return (signal.overlap == (x,y) and signal.direction == direction)

    def move_headcode(self, text, lines, game, signals, display):
        # lines = text.splitlines()
        grid = [list(line.rstrip('\n')) for line in lines]
        direction = self.direction
        if len(self.headcode_coords) >= 4:
            for i,element in enumerate(self.headcode_element):
                x,y = self.headcode_coords[i]
                grid[y][x] = element
                display.set_char_color_at_coord(x, y, "gray", text)
            modified_text = '\n'.join(''.join(row) for row in grid)
            game.text = modified_text
            game.update_lines()
            self.headcode_coords = []
            self.headcode_element = []
            text = modified_text
            # lines = text.splitlines()
            lines = game.lines
            grid = [list(line.rstrip('\n')) for line in lines]
        (x,y) = self.coords[0][0]
        element = grid[y][x]
        last_char = self.last_char
        last_last_char = self.last_last_char
        # for signal in signals:
        #     if (x,y) == signal.overlap:
        #         return
        last_message = None
        while True:
            
            if last_message != f"move headcode {x},{y}, direction is {direction}":
                print(f"move headcode {x},{y}, direction is {direction}")
                last_message = f"move headcode {x},{y}, direction is {direction}"
            for signal in signals:
                if (x,y) == signal.overlap:
                    x = signal.coord[0]
                    y = signal.coord[1]
                    if signal.mount == "up":
                        y += 1
                    elif signal.mount == "down":
                        y -= 1
                    if signal.direction == "right":
                        x -= 3
                    for i in range(4):
                        self.headcode_element.append(lines[y][x+i])
                        self.headcode_coords.append((x+i,y))
                        char = self.headcode[i]
                        grid[y][x+i] = char
                        display.set_char_color_at_coord(x+i, y, "light blue", text)

                    modified_text = '\n'.join(''.join(row) for row in grid)
                    game.text = modified_text
                    game.update_lines()

                    return
            x, y, direction, last_char, direction_change, last_last_char = game.path_find(lines, x, y, direction, self.direction, last_char, last_last_char)
            if x == -1:
                return
            if last_char == "x":
                return
    def display_on(self, display, text, lines):
        """
        Turn every coord in the train red on the display.
        """
        for coords in self.coords:
            for i,coord in enumerate(coords):
                x,y = coord
                # if i >= 1 and i <= 4:
                #     display.set_char_color_at_coord(x, y, "light blue", text)
                # else:
                if display.get_char_color_at_coord(x,y,lines) != (0, 255, 255):
                    display.set_char_color_at_coord(x, y, "red", text)
        for coord in self.headcode_coords:
            x,y = coord
            display.set_char_color_at_coord(x, y, "light blue", text)

    # def station_check(self, text):
    #     x, y = self.coords[0][0]
    #     lines = text.splitlines()
    #     if self.direction == 'right':
    #         additive = 1
    #     else:
    #         additive = -1
    #     if x-3 < 0:
    #         return
    #     if lines[y+1][x] == "¯" and lines[y+1][x + additive] != "¯":
    #         self.wait_time = 2
    #     elif lines[y-1][x] == "¯" and lines[y-1][x + additive] != "¯":
    #         self.wait_time = 2
    
    def bounds_check(self, text,display, game):

        x, y = self.coords[0][0]
        f = StringIO(text)
        lines = f.readlines()
        grid = [list(line.rstrip('\n')) for line in lines]
        if x < 0 or x > len(lines[y]):
            display.add_log("failed bounds check")
            self.despawn_train(text, display, game)
            return False
        return True
    
    def color_route_coords(self, display, text):
        # if self.last_colored_route_coords == self.route_coords:
        #     return
        for coord in self.route_coords:
            if coord:
                x, y = coord
                if display.get_char_color_at_coord(x, y, text) == (255, 255, 255):
                    display.set_char_color_at_coord(x, y, "white",text)
        # self.last_colored_route_coords = self.route_coords.copy()
    
    def despawn_train(self, text, display, game):
        f = StringIO(text)
        lines = f.readlines()
        grid = [list(line.rstrip('\n')) for line in lines]
        for coords in self.coords:
            for i,coord in enumerate(coords):
                x, y = coord
                if self.last_signal and self.last_signal[0].route_set and (x,y) in self.last_signal[0].route_coords:
                    display.set_char_color_at_coord(x, y, "white",text)
                else:
                    display.set_char_color_at_coord(x, y, "gray",text)
        
        for last_signal in self.last_signal:
            last_signal.train_in_block = False
            # game.update_signals()
        
    def add_last_direction(self):
        if not self.last_three_directions or self.direction != self.last_three_directions[-1]:
            self.last_three_directions.append(self.direction)
        
        
