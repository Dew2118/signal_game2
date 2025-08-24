from collections import deque
from io import StringIO
import winsound
NOTIFIED_SOUND = r"C:\Windows\Media\chord.wav"
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
        self.real_first_coord = self.coords[0][0]
        self.skip_parts_horizontal = False
        self.skip_parts_vertical = False
        self.block_horizontal = False
        self.block_vertical = False
        self.route_coords = []
        self.notified = False
        self.last_action = "remove train tail"

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
    
    def timetable_check(self, game, text, display):
        current_stop = self.timetable[self.current_stop_index]
        stop_coords = self._get_stop_coord(current_stop)  # defined below
        # Only apply timing logic if head is at the stop
        if self._at_stop_coord(stop_coords):
            current_game_time = game.game_seconds
            time_since_spawn = current_game_time - self.game_seconds_at_spawn
            if not self.start_to_stop_time:
                self.start_to_stop_time = time_since_spawn
            dep_offset = current_stop.get('departure_offset', 0)
            self.delete_train_tail(display, game)
            self.last_action = "remove train tail"
            if "change_timetable" in current_stop:
                # print("found change tt")
                tt_index = current_stop["change_timetable"]
                self.timetable, tt_headcode_prefix, new_direction = game.get_tt_from_index(tt_index)
                if self.direction != new_direction:
                    self.direction = new_direction
                    self.real_first_coord = self.coords[0][0]
                self.coords[0].reverse()
                self.last_signal = deque()
                # print("headcode prefix is ", tt_headcode_prefix)
                self.headcode = game.get_headcode_from_prefix(tt_headcode_prefix)
                self.current_stop_index = 0
                self.game_seconds_at_spawn += dep_offset
                time_since_spawn = current_game_time - self.game_seconds_at_spawn
                self.start_to_stop_time = time_since_spawn
                # # self.set_headcode(text, game)
                self.move_headcode(text, game, game.signals, display)
                # print("new game second at spawn is ", self.game_seconds_at_spawn)
            if current_stop.get("reverse_direction"):
                self.direction = "left" if self.direction == "right" else "right"
                self.real_first_coord = self.coords[0][0]
            if current_stop.get("despawn"):
                self.despawn_train(text, display, game)
                game.despawn_train(self)
                return False
            if time_since_spawn < dep_offset:
                return False # ⛔ Guard: Not time to leave yet
            
            elif (time_since_spawn - self.start_to_stop_time) < 2:
                # print(time_since_spawn, self.start_to_stop_time)
                return False
            # ✅ Time to leave, move to next stop
            self.current_stop_index += 1
        else:
            self.start_to_stop_time = 0
        return True
    def move(self, text, game, signals, display):
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
            if not self.timetable_check(game, text, display):
                return
            x, y = self.coords[0][0]  # Head of the train
            # Check for blocking signals above (y+1) and below (y-1)
            if signals:
                for signal in signals:
                    if self.signal_condition_check(signal, x, y, self.direction):
                        if signal.color == "red" and self.last_action == "remove train tail":
                            print("stopping at red signal")
                            if not self.notified:
                                winsound.PlaySound(NOTIFIED_SOUND, winsound.SND_FILENAME)
                                self.notified = True
                                display.add_log(f"train {self.headcode} stopped at red signal at {signal.coord}")
                            return
                        self.notified = False
                        if self.last_action == "remove train tail":
                            signal.train_in_block = True
                            if not signal.auto:
                                signal.route_set = False
                                if signal.route_coords:
                                    self.route_coords = signal.route_coords.copy()
                                    signal.route_coords = []
                                else:
                                    self.route_coords = []
                            self.last_signal.append(signal)
                            break
                    
                    elif self.signal_condition_check(signal, self.coords[-1][0][0], self.coords[-1][0][1], self.direction) and len(self.last_signal) > 1:
                        last_signal = self.last_signal.popleft()
                        last_signal.train_in_block = False
            self.last_move_time = now  # Update timestamp
            lines = text.splitlines()
            self.move_headcode(text, game, signals, display)
            if self.last_action == "move train":
                self.delete_train_tail(display, game)
                self.last_action = "remove train tail"
            elif self.last_action == "remove train tail":
                self.move_train(x, y, lines, game, signals, display)
                self.last_action = "move train"

            
    def delete_train_tail(self, display, game):
        if len(self.coords) < 2:
            return
        coords = self.coords.pop()
        for coord in coords:
            display.set_char_color_at_coord(coord[0], coord[1], "gray", game.text)

    def move_train(self,x, y, lines, game, signals, display):
        if len(self.coords) >= 2:
            return
        coords = []
        while True:
            x, y, self.direction, self.last_char, direction_change = game.path_find(lines, x, y, self.direction, self.direction, self.last_char)
            coords.insert(0,(x,y))
            if self.direction == "right":
                amended_x = x+1
                opposite_direction = "left"
                if (lines[y][x] == "b" or lines[y][amended_x] == "c"):
                    self.coords.insert(0, coords)
                    return
            else:
                amended_x = x-1
                opposite_direction = "right"
                if (lines[y][x] == "c" or lines[y][amended_x] == "b"):
                    self.coords.insert(0, coords)
                    return
            for signal in signals:
                if self.signal_condition_check(signal, x, y, self.direction) or self.signal_condition_check(signal, amended_x, y, opposite_direction):
                    self.coords.insert(0, coords)
                    return
            if self.last_char == "x":
                self.coords.insert(0, coords)
                return
            # elif self.last_char == "c"
                

    def signal_condition_check(self, signal, x, y, direction):
        return (signal.overlap == (x,y) and signal.direction == direction)

    def move_headcode(self, text, game, signals, display):
        lines = text.splitlines()
        grid = [list(line.rstrip('\n')) for line in lines]
        direction = self.direction
        if len(self.headcode_coords) >= 4:
            for i,element in enumerate(self.headcode_element):
                x,y = self.headcode_coords[i]
                grid[y][x] = element
                display.set_char_color_at_coord(x, y, "gray", text)
            modified_text = '\n'.join(''.join(row) for row in grid)
            game.text = modified_text
            self.headcode_coords = []
            self.headcode_element = []
            text = modified_text
            lines = text.splitlines()
            grid = [list(line.rstrip('\n')) for line in lines]
        if self.last_signal:
            (x,y) = self.last_signal[-1].overlap
            last_char = "a"
        else:
            (x,y) = self.coords[0][-1]
            
            last_char = self.last_char
        
        while True:
            x, y, direction, last_char, direction_change = game.path_find(lines, x, y, direction, direction, last_char)
            for signal in signals:
                if ((signal.coord == (x,y-1) and signal.mount == "up") or (signal.coord == (x,y+1) and signal.mount == "down") or ((signal.coord == (x+2,y) or signal.coord == (x-2,y)) and signal.buffer)) and signal.direction == direction:
                    if direction == "left":
                        x += 1
                    else:
                        x -= 4
                    
                    for i in range(4):
                        self.headcode_element.append(lines[y][x+i])
                        self.headcode_coords.append((x+i,y))
                        char = self.headcode[i]
                        grid[y][x+i] = char
                        display.set_char_color_at_coord(x+i, y, "light blue", text)

                    modified_text = '\n'.join(''.join(row) for row in grid)
                    game.text = modified_text

                    return
            if last_char == "x":
                return
    def display_on(self, display, text):
        """
        Turn every coord in the train red on the display.
        """
        for coords in self.coords:
            for i,coord in enumerate(coords):
                x,y = coord
                # if i >= 1 and i <= 4:
                #     display.set_char_color_at_coord(x, y, "light blue", text)
                # else:
                if display.get_char_color_at_coord(x,y,text) != (0, 255, 255):
                    display.set_char_color_at_coord(x, y, "red", text)

    def station_check(self, text):
        x, y = self.coords[0][0]
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

        x, y = self.coords[0][0]
        f = StringIO(text)
        lines = f.readlines()
        grid = [list(line.rstrip('\n')) for line in lines]
        if x <= 0 or x > len(lines[y]):
            display.add_log("failed bounds check")
            self.despawn_train(text, display, game)
            return False
        return True
    
    def color_route_coords(self, display, text):
        for coord in self.route_coords:
            if coord:
                x, y = coord
                if display.get_char_color_at_coord(x, y, text) == (255, 255, 255):
                    display.set_char_color_at_coord(x, y, "white",text)
    
    def despawn_train(self, text, display, game):
        f = StringIO(text)
        lines = f.readlines()
        grid = [list(line.rstrip('\n')) for line in lines]
        for coords in self.coords:
            for i,coord in enumerate(coords):
                x, y = coord
                if i >= 1 and i <= 4:
                    char = self.headcode_element.pop()
                    grid[y][x] = char
            modified_text = '\n'.join(''.join(row) for row in grid)
            game.text = modified_text
        for coords in self.coords:
            for i,coord in enumerate(coords):
                x, y = coord
                if self.last_signal and self.last_signal[0].route_set:
                    display.set_char_color_at_coord(x, y, "white",modified_text)
                else:
                    display.set_char_color_at_coord(x, y, "gray",modified_text)
        
        for last_signal in self.last_signal:
            last_signal.train_in_block = False
        
        
        
