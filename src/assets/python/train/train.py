from collections import deque
from io import StringIO
from unittest import signals
import winsound
import threading
NOTIFIED_SOUND = r"C:\Windows\Media\chord.wav"
TRTS_SOUND = r"C:\Windows\Media\Windows Notify.wav"



class Train:
    def __init__(self, head_coord, direction, headcode, timetable, game_seconds_at_spawn, annotated_segments, wait_time=1):
        self.coords = [[head_coord]]  # List of (x, y) tuples
        self.last_move_time = game_seconds_at_spawn  # Timestamp for last move
        self.last_signal = []
        self.direction = direction
        self.headcode = headcode
        self.headcode_element = []
        self.headcode_coords = []
        self.wait_time = wait_time
        self.timetable = timetable
        self.game_seconds_at_spawn = game_seconds_at_spawn
        self.annotated_segments = annotated_segments
        self.current_stop_index = 0
        self.start_to_stop_time = 0
        self.route_coords = []
        self.notified = False
        self.last_action = "remove train tail"
        self.notify_TRTS = False
        self.direction_change = None
        self.despawn = False
        self.temporary_characters = []

    def _get_stop_coord(self, stop):
        """
        Returns the coord (x, y) from annotated segments matching station & platform.
        """
        target_station = stop.get("station")
        stop_coords = []
        for segment in self.annotated_segments:
            if segment.get("station") == target_station:
                # Return one end of the platform (use left or right based on train direction)
                if self.direction == "right":
                    stop_coords.append(segment.get("right", segment.get("end")))
                else:
                    stop_coords.append(segment.get("left", segment.get("start")))
        return stop_coords
        
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
    
    def _past_stop_coord(self, stop_coords, direction):
        coord = self.coords[0][0]
        x = coord[0]
        y = coord[1]
        lowest_x = min([c[0] for c in stop_coords])
        highest_x = max([c[0] for c in stop_coords])
        lowest_y = min([c[1] for c in stop_coords])
        highest_y = max([c[1] for c in stop_coords])
        lowest_y -= 1
        highest_y += 1

        if direction == "right" and x > highest_x and lowest_y <= y <= highest_y:
            return True
        elif direction == "left" and x < lowest_x and lowest_y <= y <= highest_y:
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
            arr_offset = current_stop.get('arrival_offset', 0)
            despawn = current_stop.get('despawn', False)
            if dep_offset == arr_offset and not despawn:
                self.current_stop_index += 1
                return True
            if self.last_action == "move train":
                last_last_signal = self.last_last_signal_check(game)
                self.delete_train_tail(display, game, last_last_signal)
                text = game.text
                lines = game.lines
                self.last_action = "remove train tail"
            if "change_timetable" in current_stop:
                tt_index = current_stop["change_timetable"]
                self.timetable, tt_headcode_prefix, new_direction = game.get_tt_from_index(tt_index)
                if self.direction != new_direction:
                    self.direction = new_direction
                    self.coords[0].reverse()
                self.headcode = game.get_headcode_from_prefix(tt_headcode_prefix)
                self.current_stop_index = 0
                self.route_coords = []
                self.temporary_characters = []
                self.last_signal = []
                self.direction_change = None
                self.last_three_directions = deque(maxlen=3)
                self.game_seconds_at_spawn += dep_offset
                time_since_spawn = current_game_time - self.game_seconds_at_spawn
                self.start_to_stop_time = time_since_spawn
                self.notified = False
                self.notify_TRTS = False
                # # self.set_headcode(text, game)
                self.move_headcode(text, lines, game, game.signals, display)

            if current_stop.get("reverse_direction"):
                if self.direction == "right":
                    self.direction = "left"
                else:
                    self.direction = "right"
                print("train direction reversed to ", self.direction)
                # self.reversed_direction = True
                # self.real_first_coord = self.coords[0][0]
                self.coords[0].reverse()
            # else:
                # self.reversed_direction = False
            if current_stop.get("despawn"):
                self.despawn = True
                # self.despawn_train(text, display, game)
                # game.despawn_train(self)
                return False
            self.TRTS(dep_offset-time_since_spawn, game.signals, game, display, text, lines)
            if time_since_spawn < dep_offset:
                
                return False
            
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
        elif self._past_stop_coord(stop_coords, self.direction):
            self.current_stop_index += 1
            display.add_log(f"train {self.headcode} missed stop at {current_stop.get('station')}")
            return False
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
        if self.despawn:
            last_last_signal = self.last_last_signal_check(game)
            self.delete_train_tail(display, game, last_last_signal)
            text = game.text
            lines = game.lines
            self.last_action = "remove train tail"
            self.last_move_time = now
            return
        elif self.timetable and self.current_stop_index < len(self.timetable):
            if not self.timetable_check(game, text, lines, display, signals):
                return
            self.notify_TRTS = False
            x, y = self.coords[0][0]  # Head of the train
            # Check for blocking signals above (y+1) and below (y-1)
            if signals:
                # print("coord", self.coords[-1][0])
                for signal in signals:
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
                                    self.temporary_characters = signal.temporary_characters.copy()
                                    signal.temporary_characters = []
                                else:
                                    self.route_coords = []
                                    self.temporary_characters = []
                            self.last_signal.insert(0, signal)
                            break
            
            self.last_move_time = now  # Update timestamp
            # lines = text.splitlines()
            
            if self.last_action == "move train":
                last_last_signal = self.last_last_signal_check(game)
                self.delete_train_tail(display, game, last_last_signal)
                text = game.text
                lines = game.lines
                self.last_action = "remove train tail"
            elif self.last_action == "remove train tail":
                if not self.despawn:
                    self.move_train(x, y, lines, game, signals, display)
                self.last_action = "move train"
                

            self.move_headcode(text, lines, game, signals, display)

    def last_last_signal_check(self, game):
        # print("train headcode is ", self.headcode, "its direction is ", self.direction)
        if len(self.last_signal) == 0:
            print("last signal len is 0")
            return
        if self.direction_change:
            # direction = self.last_three_directions[-1]
            direction_change_coord = self.direction_change[0]
            direction_change_direction = self.direction_change[1]
            if direction_change_coord in self.coords[0]:
                if direction_change_direction == "right":
                    direction = "left"
                else:
                    direction = "right"
            else:
                direction = self.direction
        else:
            direction = self.direction
        print("last signal length", len(self.last_signal), "last last coord", self.coords[-1], "overlap", self.last_signal[0].overlap, "direction", self.last_signal[0].direction, "last action", self.last_action)
        if len(self.last_signal) > 0 and self.signal_condition_check(self.last_signal[0], self.coords[-1][0][0], self.coords[-1][0][1], direction) and self.last_action == "move train" and (len(self.last_signal) >= 2 or self.last_signal[-1].signal_type == "manual"):
            last_last_signal = self.last_signal.pop()
            print("last last signal check passed ", last_last_signal.coord, self.coords[-1])
            last_last_signal.train_in_block = False
            return last_last_signal
        else:
            print(len(self.last_signal) > 0, self.signal_condition_check(self.last_signal[0], self.coords[-1][0][0], self.coords[-1][0][1], direction), self.last_action == "move train", len(self.last_signal) >= 2 or self.last_signal[-1].signal_type == "manual")
            print(self.last_signal[0].overlap, self.coords[-1][0][0], self.coords[-1][0][1], direction)
            

    def delete_train_tail(self, display, game, last_last_signal):
        if len(self.coords) < 2 and not self.despawn:
            print("self.despawn is : ", self.despawn)
            return
        last_last_coord = self.coords.pop()
        print("deleting train tail at coords ", last_last_coord)
        if self.direction_change and self.direction_change[0] in last_last_coord:
            print("direction change removed")
            self.direction_change = None

        result = []
        
        for coord in last_last_coord:
            for temp_char in self.temporary_characters:
                if temp_char[0] == coord:
                    result.append(temp_char)
                    self.temporary_characters.remove(temp_char)
            if coord in self.route_coords:
                self.route_coords.remove(coord)

            if last_last_signal and last_last_signal.route_set and coord in last_last_signal.route_coords:
                display.set_char_color_at_coord(coord[0], coord[1], "white", game.text)
            
            else:
                
                set_to_white = False
                for signal in game.signals:
                    if signal.route_set and coord in signal.route_coords:
                        display.set_char_color_at_coord(coord[0], coord[1], "white", game.text)
                        set_to_white = True
                        break
                if not set_to_white:
                    display.set_char_color_at_coord(coord[0], coord[1], "gray", game.text)

        
        game_text = game.reset_temporary_characters(result, game.text)
        game.text = game_text
        game.update_lines()
        print("temporary character left: ", self.temporary_characters)

        if self.coords == [] and self.despawn:
            for signal in self.last_signal:
                signal.train_in_block = False
            game.despawn_train(self)

    def move_train(self,x, y, lines, game, signals, display):
        if len(self.coords) >= 2:
            return
        coords = []
        direction = self.direction
        last_char = "F"
        last_last_char = "F"
        while True:
            x, y, direction, last_char, direction_change, last_last_char, temporary_characters = game.path_find(lines, x, y, direction, self.direction, last_char, last_last_char, [])
            if x == -1:
                return
            print("move train x, y, is ", x, y)
            coords.insert(0,(x,y))
            if direction_change:
                self.direction_change = direction_change
                print("direction change is ", direction_change)
            if direction == "right":
                amended_x = x+1
                if (amended_x >= len(lines[y])) or (lines[y][x] in "b]nl" or (lines[y][amended_x] in "c[om" and lines[y][x] in "a")):
                    self.coords.insert(0, coords)
                    self.direction = direction
                    print("blocked by ", lines[y][x], " or ", lines[y][amended_x], " at ", (x,y), " or ", (amended_x,y))
                    return
            else:
                amended_x = x-1
                if (amended_x < 0) or (lines[y][x] in "c[om" or (lines[y][amended_x] in "b]nl" and lines[y][x] in "a")):
                    print("blocked by ", lines[y][x], " or ", lines[y][amended_x], " at ", (x,y), " or ", (amended_x,y))
                    self.coords.insert(0, coords)
                    self.direction = direction
                    return
            if last_char == "x" and len(self.coords[0]) > 1:
                self.despawn = True
                # print("blocked by last char at ", (x,y))
                self.coords.insert(0, coords)
                self.direction = direction
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
        last_char = "F"
        last_last_char = "F"
        last_message = None
        while True:
            
            if last_message != f"move headcode {x},{y}, direction is {direction}":
                print(f"move headcode {x},{y}, direction is {direction}")
                last_message = f"move headcode {x},{y}, direction is {direction}"
            for signal in signals:
                if (x,y) == signal.overlap and signal.direction == direction:
                    if signal.buffer:
                        if direction == "right":
                            x -= 6
                        else:
                            x += 2
                    else:
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
            x, y, direction, last_char, direction_change, last_last_char, temporary_characters = game.path_find(lines, x, y, direction, self.direction, last_char, last_last_char, [])
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

    def bounds_check(self, text,display, game):
        x, y = self.coords[0][0]
        f = StringIO(text)
        lines = f.readlines()
        grid = [list(line.rstrip('\n')) for line in lines]
        if x < 0 or x > len(lines[y]):
            display.add_log("failed bounds check")
            # self.despawn_train(text, display, game)
            self.despawn = True
            return False
        return True
    
    def color_route_coords(self, display, text):
        # if self.last_colored_route_coords == self.route_coords:
        #     return
        for coord in self.route_coords:
            if coord:
                x, y = coord
                # print("coloring", x, y, "white")
                if display.get_char_color_at_coord(x, y, text) != (255, 255, 255):
                    display.set_char_color_at_coord(x, y, "white",text)
        # self.last_colored_route_coords = self.route_coords.copy()
        
        
