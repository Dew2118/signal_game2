from collections import deque
from io import StringIO
from unittest import signals
import os
import winsound
import threading
NOTIFIED_SOUND = os.path.join("src", "assets", "sounds", "chord.wav")
TRTS_SOUND = os.path.join("src", "assets", "sounds", "Windows Notify.wav")



class Train:
    def __init__(self, head_coord, direction, headcode, timetable, game_seconds_at_spawn, annotated_segments, timetable_index, wait_time=1):
        self.coords = [[head_coord]]  # List of (x, y) tuples
        self.timetable_index = timetable_index
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
        self.movement_path = [] # NEW
        self.route_coords_direction_dict = {}
        
        self.notified = False
        self.last_action = "remove train tail"
        self.notify_TRTS = False
        self.direction_change = None
        self.despawn = False
        self.temporary_characters = []
        self.last_ars_time = 0

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

    
    def TRTS(self, time_difference, signals, game, display, lines):
        if time_difference >= 30:
            return
        if signals:
            x, y = self.coords[0][0]
            for signal in signals:
                if self.signal_condition_check(signal, x, y, self.direction):
                    if not self.notify_TRTS:
                        threading.Thread(target=winsound.PlaySound, args=(TRTS_SOUND, winsound.SND_FILENAME)).start()
                        display.add_log(f"{self.headcode} train TRTS at {signal.coord}")
                        self.notify_TRTS = True
                    if int(time_difference) % 2 == 1:
                        signal.activate_TRTS(game, display)
                    else:
                        signal.deactivate_TRTS(game, display)

    def timetable_check(self, game, lines, display, signals):
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
                lines = game.clone_lines(game.lines)
                self.last_action = "remove train tail"
            if "change_timetable" in current_stop:
                self.delete_train_tail(display, game, last_last_signal)
                tt_index = current_stop["change_timetable"]
                self.timetable, tt_headcode_prefix, new_direction, self.timetable_index = game.get_tt_from_index(tt_index)
                if self.direction != new_direction:
                    self.direction = new_direction
                    self.coords[0].reverse()
                    # print(f"{self.headcode} from change timetable train direction changed to {self.direction}")
                self.headcode = game.get_headcode_from_prefix(tt_headcode_prefix)
                self.current_stop_index = 0
                self.route_coords = []
                self.route_coords_direction_dict = {}
                self.temporary_characters = []
                # self.last_signal = []
                self.direction_change = None
                self.game_seconds_at_spawn += dep_offset
                time_since_spawn = current_game_time - self.game_seconds_at_spawn
                self.start_to_stop_time = time_since_spawn
                self.notified = False
                self.notify_TRTS = False
                # print(f"{self.headcode} timetable changed will call move headcode")
                self.move_headcode(game, game.signals, display)

            elif current_stop.get("reverse_direction"):
                if self.direction == "right":
                    self.direction = "left"
                else:
                    self.direction = "right"
                # print(f"{self.headcode} train direction reversed to {self.direction}")
                self.coords[0].reverse()
            elif current_stop.get("despawn"):
                self.despawn = True
                return False
            self.TRTS(dep_offset-time_since_spawn, game.signals, game, display, lines)
            if time_since_spawn < dep_offset:
                return False
            
            elif (time_since_spawn - self.start_to_stop_time) < 30:
                self.TRTS(dep_offset-time_since_spawn, game.signals, game, display, lines)
                return False
            x, y = self.coords[0][0]
            for signal in signals:
                if self.signal_condition_check(signal, x, y, self.direction) and signal.color == "red":
                    if (current_game_time - self.last_ars_time) > 1:
                        # game.ars_manager.try_set_route_for_signal(game, signal, self.timetable_index)
                        self.last_ars_time = current_game_time
                    return False
                    
                
            self.current_stop_index += 1
        elif self._past_stop_coord(stop_coords, self.direction):
            self.current_stop_index += 1
            display.add_log(f"{self.headcode} missed stop at {current_stop.get('station')}")
            return False
        else:
            self.start_to_stop_time = 0
        return True
    
    def move(self, lines, game, signals, display):
        ars = False
        now = int(game.game_seconds)
        
        # 1. The Wait Time Trap
        if now - self.last_move_time < self.wait_time:
            # Uncomment the next line if you want to see it spamming "Waiting..."
            # print(f"{self.headcode} Waiting... ({now - self.last_move_time} < {self.wait_time})")
            return  
            
        self.wait_time = len(self.coords[0])/2
        if not self.coords:
            return
            
        if self.despawn:
            last_last_signal = self.last_last_signal_check(game)
            self.delete_train_tail(display, game, last_last_signal)
            lines = game.clone_lines(game.lines)
            self.last_action = "remove train tail"
            self.last_move_time = now
            return
        elif self.timetable and self.current_stop_index < len(self.timetable):
            if not self.timetable_check(game, lines, display, signals):
                return
                
            self.notify_TRTS = False
            x, y = self.coords[0][0]
            
            if signals:
                for signal in signals:
                    if self.signal_condition_check(signal, x, y, self.direction):
                        if signal.color == "red" and self.last_action == "remove train tail":
                            if signal.signal_type == "manual" and hasattr(game, "ars_manager"):
                                if game.game_seconds - self.last_ars_time > 1:
                                    self.last_ars_time = game.game_seconds
                                else:
                                    ars = False
                            if not self.notified and not ars:
                                threading.Thread(target=winsound.PlaySound, args=(NOTIFIED_SOUND, winsound.SND_FILENAME)).start()
                                self.notified = True
                                display.add_log(f"{self.headcode} stopped at red signal at {signal.coord}")
                            ars = False
                            return
                            
                        self.notified = False
                        if self.last_action == "remove train tail":
                            signal.train_in_block = True
                            signal.deactivate_TRTS(game, display)
                            lines = game.clone_lines(game.lines)
                            
                            # --- HANDOFF ---
                            if signal.signal_type == "manual":
                                if not signal.auto:
                                    signal.route_set = False
                                    
                                if signal.route_coords:
                                    # print(f"{self.headcode} route coords are {signal.route_coords} and ordered route coords are {signal.ordered_route_coords}")
                                    self.route_coords = signal.route_coords.copy()
                                    self.movement_path = signal.ordered_route_coords.copy()
                                    # print(f"{self.headcode} the movement path is {self.movement_path}")
                                    self.route_coords_direction_dict = signal.route_coords_direction_dict.copy()
                                    self.temporary_characters = signal.temporary_characters.copy()
                                    
                                    if not signal.auto:
                                        signal.route_coords = []
                                        signal.ordered_route_coords = []
                                        signal.route_coords_direction_dict = {}
                                        signal.temporary_characters = []
                                else:
                                    self.route_coords = []
                                    self.movement_path = []
                                    self.temporary_characters = []
                            else: 
                                if getattr(signal, "auto_route_coords", None):
                                    self.route_coords = signal.auto_route_coords.copy()
                                    self.movement_path = signal.ordered_auto_route_coords.copy()
                                    self.route_coords_direction_dict = getattr(signal, "auto_route_coords_direction_dict", {}).copy()
                                
                            self.last_signal.insert(0, signal)
                            break
            
            self.last_move_time = now 
            # print(f"{self.headcode} last action is {self.last_action}")
            if self.last_action == "move train":
                last_last_signal = self.last_last_signal_check(game)
                self.delete_train_tail(display, game, last_last_signal)
                lines = game.clone_lines(game.lines)
                self.last_action = "remove train tail"
            elif self.last_action == "remove train tail":
                if not self.despawn:
                    self.move_train(x, y, lines, game, signals, display)
                    self.display_on(display, lines, game)
                self.last_action = "move train"
                
            self.move_headcode(game, signals, display)

    def last_last_signal_check(self, game):
        # print(f"{self.headcode} train headcode is {self.headcode}, its direction is {self.direction}")
        if len(self.last_signal) == 0:
            print(f"{self.headcode} last signal len is 0")
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
        # print(f"{self.headcode} last signal length {len(self.last_signal)} last last coord {self.coords[-1]} overlap {self.last_signal[0].overlap} direction {self.last_signal[0].direction} last action {self.last_action}")
        if len(self.last_signal) > 0 and self.signal_condition_check(self.last_signal[0], self.coords[-1][0][0], self.coords[-1][0][1], direction) and self.last_action == "move train" and (len(self.last_signal) >= 2 or self.last_signal[-1].signal_type == "manual"):
            last_last_signal = self.last_signal.pop()
            # print(f"{self.headcode} last last signal check passed {last_last_signal.coord} {self.coords[-1]}")
            last_last_signal.train_in_block = False
            return last_last_signal
        # else:
            # print(f"{self.headcode} last signal check failed: last_signal_exists={len(self.last_signal) > 0}, signal_condition={self.signal_condition_check(self.last_signal[0], self.coords[-1][0][0], self.coords[-1][0][1], direction)}, last_action_move={self.last_action == 'move train'}, signal_ok={len(self.last_signal) >= 2 or self.last_signal[-1].signal_type == 'manual'}")
            # print(f"{self.headcode} overlap={self.last_signal[0].overlap} coord={self.coords[-1][0][0]}, {self.coords[-1][0][1]} direction={direction}")
            

    def delete_train_tail(self, display, game, last_last_signal):
        if len(self.coords) < 2 and not self.despawn:
            return
        last_last_coord = self.coords.pop()
        # print(f"{self.headcode} deleting train tail at coords {last_last_coord}")
        if self.direction_change and self.direction_change[0] in last_last_coord:
            # print(f"{self.headcode} direction change removed")
            self.direction_change = None

        result = []
        
        for coord in last_last_coord:
            for temp_char in self.temporary_characters:
                if temp_char[0] == coord:
                    result.append(temp_char)
                    self.temporary_characters.remove(temp_char)
            if coord in self.route_coords:
                self.route_coords.remove(coord)

            if coord in self.headcode_coords:
                display.set_char_color_at_coord(coord[0], coord[1], "gray", game)
                continue

            if last_last_signal and last_last_signal.route_set and coord in last_last_signal.route_coords:
                display.set_char_color_at_coord(coord[0], coord[1], "white", game)
            
            else:
                
                set_to_white = False
                for signal in game.signals:
                    if signal.route_set and coord in signal.route_coords:
                        display.set_char_color_at_coord(coord[0], coord[1], "white", game)
                        set_to_white = True
                        break
                if not set_to_white and not (self.despawn and len(self.coords) == 0 and coord == last_last_coord[0]):
                    display.set_char_color_at_coord(coord[0], coord[1], "gray", game)
        for temporary_character in result.copy():
            for signal in game.signals:
                if signal.route_coords and temporary_character[0] in signal.route_coords:
                    result.remove(temporary_character)
                    # print("removing: ", temporary_character[0])
        game.reset_temporary_characters(result)
        # print(f"{self.headcode} temporary character left: {self.temporary_characters}")

        if self.coords == [] and self.despawn:
            for signal in self.last_signal:
                signal.train_in_block = False
            game.despawn_train(self)

    def move_train(self, x, y, lines, game, signals, display):
        if len(self.coords) >= 2:
            return
        
        if not self.movement_path:
            return
            
        # print(f"{self.headcode} CALL MOVE TRAIN with path: {self.movement_path}")
        
        # --- SAFE SLICING FIX ---
        # Only slice the path if the train head is found AND the slice doesn't 
        # completely empty the newly acquired path (which happens on a fresh handoff).
        head_coord = self.coords[0][0]
        if head_coord in self.movement_path:
            idx = self.movement_path.index(head_coord)
            temp_path = self.movement_path[idx + 1:]
            if temp_path: # Only apply if it leaves remaining coords
                self.movement_path = temp_path
        # ------------------------

        # Check again in case the path is genuinely empty
        if not self.movement_path:
            return

        coords = []
        direction = self.direction

        while self.movement_path:
            # 1. Pop the next valid coordinate
            next_x, next_y = self.movement_path.pop(0)
            coords.insert(0, (next_x, next_y))
            
            # 2. Update local variables
            x, y = next_x, next_y
            current_char = lines[y][x]

            # 3. Handle Direction Changes
            new_dir = self.route_coords_direction_dict.get((x, y), direction)
            if new_dir != direction:
                self.direction_change = [(x, y), new_dir]
                direction = new_dir

            # 4. Check for Blocking Characters
            blocked = False
            if direction == "right":
                amended_x = x + 1
                if amended_x >= len(lines[y]) or current_char in "b]nl" or (amended_x < len(lines[y]) and lines[y][amended_x] in "c[om" and current_char == "a"):
                    blocked = True
            else:
                amended_x = x - 1
                if amended_x < 0 or current_char in "c[om" or (amended_x >= 0 and lines[y][amended_x] in "b]nl" and current_char == "a"):
                    blocked = True

            # Check for derailment/end of track
            if current_char == "x":
                if len(self.coords[0]) > 1:
                    self.despawn = True
                blocked = True

            # 5. If Blocked, save the chunk and break the loop for this tick
            if blocked:
                self.coords.insert(0, coords)
                self.direction = direction
                return
                
        # 6. If the path empties perfectly, save the gathered coords
        if coords:
            self.coords.insert(0, coords)
            self.direction = direction


    def signal_condition_check(self, signal, x, y, direction):
        return (signal.overlap == (x,y) and signal.direction == direction)

    def move_headcode(self, game, signals, display):
        direction = self.direction
        if len(self.headcode_coords) >= 4:
            for i,element in enumerate(self.headcode_element):
                x,y = self.headcode_coords[i]
                game.lines[y][x] = element

                display.set_char_color_at_coord(x, y, "red", game)

            self.headcode_coords = []
            self.headcode_element = []
        (x,y) = self.coords[0][0]
        element = game.lines[y][x]
        last_char = "F"
        last_last_char = "F"
        last_message = None
        while True:
            if last_message != f"{self.headcode} move headcode {x},{y}, direction is {direction}":
                last_message = f"{self.headcode} move headcode {x},{y}, direction is {direction}"
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
                        if (game.lines[y][x+i] in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"):
                            self.headcode_element.append('a')
                        else:
                            self.headcode_element.append(game.lines[y][x+i])
                        self.headcode_coords.append((x+i,y))
                        char = self.headcode[i]
                        game.lines[y][x+i] = char
                        display.set_char_color_at_coord(x+i, y, "light blue", game)

                    return
            x, y, direction, last_char, direction_change, last_last_char, temporary_characters = game.path_find(game.lines, x, y, direction, self.direction, last_char, last_last_char, [])
            if x == -1:
                return
            if last_char == "x":
                return
    def display_on(self, display, lines, game):
        """
        Turn every coord in the train red on the display.
        """
        for coords in self.coords:
            for i,coord in enumerate(coords):
                x,y = coord
                if (x,y) in self.route_coords:
                    self.route_coords.remove((x,y))
                if lines[y][x] == "x":
                    continue
                if display.get_char_color_at_coord(x,y,lines) != (0, 255, 255):
                    display.set_char_color_at_coord(x, y, "red", game)
        for coord in self.headcode_coords:
            x,y = coord
            if lines[y][x] == "x":
                continue
            display.set_char_color_at_coord(x, y, "light blue", game)

    
    def color_route_coords(self, display, lines, game):
        for coord in self.route_coords:
            if coord:
                x, y = coord
                if display.get_char_color_at_coord(x, y, lines) != (255, 255, 255):
                    display.set_char_color_at_coord(x, y, "white", game)

        
