from src.assets.python.train.train import Train
from src.assets.python.layout.signals import Signal
from src.assets.python.display import Display_Class
import pygame
from io import StringIO
from src.assets.python.layout.auto import Auto
import pickle
import json
import time
import os # for JSON path because python is stupid:tm:
JSON_PATH = "src/json/" # pretent it is like const json_path = "src/json/"; in js
CWD = os.path.dirname(__file__) # CWD = Current Working Directory, pretend it is a const too
from src.assets.python.timetable.display_timetable import Timetable
class Game:
    def __init__(self, text):
        self.text = text
        self.trains = []
        self.signals = []  # Add signals to Game, not Display_Class
        self.autos = []
        self.entry_signal = None
        self.exit_signal = None
        self.switches = []  # List to store switch coordinates
        self.spawned_train = False
        self.game_seconds = 0.0          # Total in-game time in minutes
        self.time_speed = 1            # 1.0 = real time speed
        self.paused = False
        self._last_real_time = time.time()
        self.last_spawn_time = 10000000000000000
        self.headcode_suffix = {}
        self.timetables = None
        self.timetable_obj = None
        self.backlog_train_spawn = []

    #TODO : rework this to work better with file path
    def load_timetable_and_annotated_segments(self, filename=os.path.join(CWD, JSON_PATH, "timetable.json")):
        print("  | loading " + filename)
        with open(filename, "r") as f:
            self.timetables = json.load(f)
        with open(os.path.join(CWD, JSON_PATH, "annotated_segments.json"), "r") as f:
            self.annotated_segments = json.load(f)
        for seg in self.timetables:
            headcode_prefix = seg.get('headcode_prefix', '')
            if headcode_prefix and headcode_prefix not in self.headcode_suffix:
                self.headcode_suffix[headcode_prefix] = 0

    def get_tt_from_index(self, index):
        for template in self.timetables:
            if template.get("index") == index:
                print("found tt from index")
                return template["stops"], template["headcode_prefix"], template["direction"]
    def save_game(self, filename="save.pkl"):
        data = {
            "trains": self.trains,
            "signals": self.signals,
            "autos": self.autos,
            "text": self.text,
            "entry_signal": self.entry_signal,
            "exit_signal": self.exit_signal,
            "switches": self.switches,
            "spawned_train": self.spawned_train,
            # "display_class": self.display_class
            "game_seconds": self.game_seconds,
            "time_speed": self.time_speed,
            "paused": self.paused,
            "_last_real_time": self._last_real_time,
            "last_spawn_time": self.last_spawn_time,
            "headcode_suffix": self.headcode_suffix,
            "timetables": self.timetables,
            # "timetable_obj": self.timetable_obj
        }

        with open(filename, "wb") as f:
            pickle.dump(data, f)
        print("Game saved.")

    def load_game(self,filename="save.pkl"):
        with open(filename, "rb") as f:
            data = pickle.load(f)
        self.text = data["text"]
        # game = Game(text)
        self.trains = data["trains"]
        self.signals = data["signals"]
        self.autos = data["autos"]
        self.entry_signal = data["entry_signal"]
        self.exit_signal = data["exit_signal"]
        self.switches = data["switches"]
        self.spawned_train = data["spawned_train"]
        self.display_class = Display_Class()
        self.game_seconds = data.get("game_seconds", 0.0)
        self.time_speed = data.get("time_speed", 1.0)
        self.paused = data.get("paused", False)
        self._last_real_time = time.time()
        self.last_spawn_time = data.get("last_spawn_time", 0)
        self.headcode_suffix = data.get("headcode_suffix", {})
        self.timetables = data.get("timetables", None)
        self.timetable_obj = None

        print("Game loaded.")
        # return game

    def get_headcode_from_prefix(self, headcode_prefix):
        
        if headcode_prefix not in self.headcode_suffix:
                self.headcode_suffix[headcode_prefix] = 0  # Just in case, initialize to :0

        # Generate headcode with suffix
        suffix = f"{self.headcode_suffix[headcode_prefix]:02d}"
        if self.headcode_suffix[headcode_prefix] == 99:
            self.headcode_suffix[headcode_prefix] = 0
        else:
            self.headcode_suffix[headcode_prefix] += 1
        headcode = headcode_prefix + suffix
        return headcode
    def find_first_spawn_signal(self,spawn_coord, direction):
        x,y = spawn_coord
        while True:
            if direction == "left":
                x -= 1
            else:
                x += 1
            for signal in self.signals:
                if signal.coord == (x,y-1) and signal.direction == direction and signal.mount == "up":
                    print("found signal at ",x,y-1)
                    return (x,y)
                elif signal.coord == (x,y+1) and signal.direction == direction and signal.mount == "down":
                    print("found signal at ",x,y+1)
                    return (x,y)


    def update_spawn(self):
        spawned_positions_this_tick = set()
        current_time = int(self.game_seconds) # assume this is an int representing seconds since midnight
        if current_time == self.last_spawn_time:
            return
        for tt in self.timetables:
            spawn_times = tt.get('spawn_times', [])

            # Skip if no spawn_times defined
            if not spawn_times:
                continue

            # Convert spawn_times from "HH:MM:SS" to seconds
            spawn_seconds = set()
            for t in spawn_times:
                h, m, s = map(int, t.split(":"))
                total_seconds = h * 3600 + m * 60 + s
                spawn_seconds.add(total_seconds)
            # Only consider timetables that should spawn now
            if current_time not in spawn_seconds:
                continue

            start_seg = tt['start_location']
            # Determine spawn coordinate
            coord = tuple(start_seg['left'] if 'left' in start_seg else start_seg['right'])

            # Prevent duplicate spawns at same 
            
            if coord in spawned_positions_this_tick:
                continue
            headcode_prefix = tt['headcode_prefix']
            headcode = self.get_headcode_from_prefix(headcode_prefix)
            direction = tt['direction']
              # Example suffix
            train = self.spawn_train(
                length=6,
                start_coord=coord,
                direction=direction,
                headcode=headcode,
                timetable=tt['stops']
            )

            spawned_positions_this_tick.add(coord)
        self.last_spawn_time = current_time


    def spawn_train(self, length, start_coord, direction='right', headcode = "4H69", timetable = [], game_seconds = None, annotated_segments = None):
        if not game_seconds:
            game_seconds = self.game_seconds
        if not annotated_segments:
            annotated_segments = self.annotated_segments
        coords = [start_coord for _ in range(length)]
        signal_coord = self.find_first_spawn_signal(start_coord, direction)
        if not self.check_if_spawnable(signal_coord):
            self.backlog_train_spawn.append({"length": length, "coords": coords, "direction": direction, "headcode": headcode, "timetable": timetable, "game_seconds": game_seconds, "annotated_segments": annotated_segments})
            return
        train = Train(length, coords,direction, headcode, timetable, self.game_seconds, self.annotated_segments)
        self.trains.append(train)
        return train

    def check_backlog_train(self):
        for backlog_train in self.backlog_train_spawn:
            coord = backlog_train["coords"][0]
            signal_coord = self.find_first_spawn_signal(coord, backlog_train["direction"])
            if self.check_if_spawnable(signal_coord):
                self.backlog_train_spawn.remove(backlog_train)
                print('removed')
                self.spawn_train(backlog_train["length"], backlog_train["coords"][0], backlog_train["direction"], backlog_train["headcode"], backlog_train["timetable"])

    def check_if_spawnable(self, coord):
        # for coord in coords:
        if self.display_class.get_char_color_at_coord(coord[0], coord[1], self.text) != (128, 128, 128) and self.display_class.get_char_color_at_coord(coord[0], coord[1], self.text) != None:
            print("cant be spawned")
            return False
        return True

    def create_signals_from_file(self, target_chars, signal_type_map, direction_map, mount_map, buffer_map):
        signals = []
        f = StringIO(self.text)

        # Now you can use f like a file
        lines = f.readlines()
        i = 1
        for y, line in enumerate(lines):
            for x, char in enumerate(line.rstrip('\n')):
                if char in target_chars:
                    signal_type = signal_type_map.get(char, "automatic")
                    color = "red"  # Force all signals to be red
                    direction = direction_map.get(char, "right")
                    buffer = buffer_map.get(char, False)
                    if (direction == "right" and lines[y][x+1] not in "qsr") and not buffer:
                        continue
                    elif (direction == "left" and lines[y][x-1] not in "qsr") and not buffer:
                        continue
                    mount = mount_map.get(char, "up")
                    
                    name = f"i"
                    signal = Signal(
                        name=name,
                        coord=(x, y),
                        signal_type=signal_type,
                        color=color,
                        direction=direction,
                        mount=mount,
                        buffer=buffer
                    )
                    signals.append(signal)
                    i += 1
        self.signals = signals  # Store signals in Game
        return signals

    def define_auto_buttons(self):
        target_chars = {'à', 'ø', 'û','ã','â',"ù", "á", "©"}
        f = StringIO(self.text)
        lines = f.readlines()
        for y, line in enumerate(lines):
            for x, char in enumerate(line.rstrip('\n')):
                if x < len(line) - 3:  # Make sure we're not out of bounds
                    char_to_the_right = line[x+1]
                    char_two_to_the_right = line[x+2]
                    char_three_to_the_right = line[x+3]
                if x >= 3:
                    char_to_the_left = line[x-1]
                    char_two_to_the_left = line[x-2]
                    char_three_to_the_left = line[x-3]
                if char == "p" or char == "q":
                    # print("char to the right are", char_to_the_right)
                    if char_to_the_right == "A":
                        print("A to the right")
                        if char_two_to_the_right in target_chars:
                            signal_coord = (x + 2, y)
                            for s in self.signals:
                                if s.coord == signal_coord:
                                    signal = s
                            auto = Auto((x,y),signal, "right")
                            self.autos.append(auto)
                        elif char_three_to_the_right in target_chars:
                            signal_coord = (x + 3, y)
                            print("looking at at ",signal_coord)
                            for s in self.signals:
                                if s.coord == signal_coord:
                                    signal = s
                            auto = Auto((x,y),signal, "right")
                            self.autos.append(auto)
                    elif char_to_the_left == "A":
                        if char_two_to_the_left in target_chars:
                            signal_coord = (x - 2, y)
                            for s in self.signals:
                                if s.coord == signal_coord:
                                    signal = s
                            auto = Auto((x,y),signal, "left")
                            self.autos.append(auto)
                        elif char_three_to_the_left in target_chars:
                            signal_coord = (x - 3, y)
                            for s in self.signals:
                                if s.coord == signal_coord:
                                    
                                    signal = s
                            auto = Auto((x,y),signal, "left")
                            self.autos.append(auto)
                


    def define_switches(self):
        f = StringIO(self.text)
        lines = f.readlines()
        for y, line in enumerate(lines):
            for x, char in enumerate(line.rstrip('\n')):
                if y + 1 < len(lines):  # Make sure we're not out of bounds
                    next_line = lines[y + 1].rstrip('\n')  # Remove newline
                    if x < len(next_line):  # Make sure x is within the line
                        char_below = next_line[x]
                if y - 1 >= 0:  # Make sure we're not out of bounds
                    line_above = lines[y - 1].rstrip('\n')  # Remove newline
                    if x < len(line_above):  # Make sure x is within the line
                        char_above = line_above[x]
                if (char == "i" or char == "{") and char_below == "a":
                    self.switches.append([x,y+1, "h", "left"])
                    if char == "{":
                        print(x,y+1, "{")
                if (char == "h" or char == "}") and char_above == "a":
                    self.switches.append([x,y-1, "i", "right"])
                    if char == "}":
                        print(x,y-1, "}")
                if (char == "j" or char == "n" or char == "}") and char_below == "a":
                    self.switches.append([x,y+1, "k","right"])
                    if char == "}":
                        print(x,y+1, "}")
                if (char == "k" or char == "o" or char == "{") and char_above == "a":
                    self.switches.append([x,y-1, "j","left"])
                    if char == "{":
                        print(x,y-1, "{")

    def change_switch(self, switch_index, switch_direction = "normal", text = None):
        # Convert lines to a list of lists (mutable)
        if not text:
            text = self.text
        f = StringIO(text)
        lines = f.readlines()
        x, y, new_char, direction = self.switches[switch_index]
        if switch_direction == "normal":
            new_char = "a"
        grid = [list(line.rstrip('\n')) for line in lines]

        # Change the character (safely)
        if 0 <= y < len(grid) and 0 <= x < len(grid[y]):
            if switch_direction == "change":
                if grid[y][x] != "a":
                    grid[y][x] = "a"
                else:
                    grid[y][x] = new_char
            else:
                grid[y][x] = new_char

        # If you want the modified text back as a single string
        modified_text = '\n'.join(''.join(row) for row in grid)
        return modified_text  # Update the text in Game
    
    def get_switch_position(self, switch_index, text):
        f = StringIO(text)
        lines = f.readlines()
        x, y, new_char, direction = self.switches[switch_index]
        char = lines[y][x]
        if char == "a":
            return "normal"
        return "reverse"

    def find_next_signals(self, signals):
        signal_lookup = {(s.coord[0], s.coord[1]): s for s in signals}
        lines = self.text.splitlines()
        right_up = ['k','{']
        right_down = ["i","o"]
        left_up = ['h',"n"]
        left_down = ['j','}']
        both_up = ["z"]
        both_down = ["y"]
        
        
        last_char = "F"
        for signal in signals:
            # print(signal)
            if signal.signal_type != "automatic":
                continue
            if signal.buffer:
                continue
            x, y = signal.coord
            if signal.mount == 'up':
                y += 1
            elif signal.mount == 'down':
                y -= 1
            direction = signal.direction
            skip_parts_horizontal = False
            skip_parts_vertical = False
            block_horizontal = False
            block_vertical = False
            while 0 <= y < len(lines) and 0 <= x < len(lines[y]):
                
                char = lines[y][x]
                if char == "x":
                    # signal.next_signal = None
                    # break
                    break
                if char == "÷":
                    if not block_horizontal:
                        block_horizontal = True
                    else:
                        block_horizontal = False
                        skip_parts_horizontal = False
                if char == "ö":
                    if not block_vertical:
                        block_vertical = True
                    else:
                        block_vertical = False
                        skip_parts_vertical = False
                if char in "|ö":
                    if (last_char in right_up and direction == 'right') or (last_char in left_up and direction == 'left'):
                        direction = "up"
                    elif (last_char in right_down and direction == 'right') or (last_char in left_down and direction == 'left'):
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
                        print("up")
                        y -= 1
                    elif direction == "down":
                        print("down")
                        y += 1
                elif direction == "up" or direction == "down":
                    if char in "ik":
                        direction = "left"
                        x -= 1
                    elif char in "hj":
                        direction = "right"
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

                if not (0 <= y < len(lines) and 0 <= x < len(lines[y])):
                    break

                for dy in [-1, 0, 1]:
                    ny = y + dy
                    if 0 <= ny < len(lines):
                        candidate = signal_lookup.get((x, ny))
                        if candidate and not skip_parts_horizontal and not skip_parts_vertical:
                            signal.next_signal = candidate
                            break
                if signal.next_signal:
                    break
                last_char = char


    def set_route(self, game):
        self.display_class.set_char_color_at_coord(self.entry_signal.coord[0], self.entry_signal.coord[1], "gray", self.text)
        coords = self.entry_signal.get_coords_to_next_signal(self.exit_signal, self, self.switches, "test.txt", self.signals)
        if not coords:
            game.entry_signal = None
            game.exit_signal = None
            return
        self.entry_signal.next_signal = self.exit_signal
        self.entry_signal.route_set = True
        
        for coord in coords:
            self.display_class.set_char_color_at_coord(coord[0], coord[1], "white", self.text)
        self.entry_signal = None
        self.exit_signal = None


    def despawn_train(self, train):
        self.trains.remove(train)
        print("train removed")

    def open_timetable_window(self, train):
        self.timetable_obj = Timetable(train)
        self.timetable_obj.show_timetable_window()

    def color_entry_signal(self):
        if self.entry_signal:
            self.display_class.set_char_color_at_coord(self.entry_signal.coord[0], self.entry_signal.coord[1], "white", self.text)
    
    def run(self):
        running = True
        clock = pygame.time.Clock()
        
        # try:
        while running:
            total_seconds = int(self.game_seconds)
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d} *{self.time_speed}"
            running = self.display_class.update_and_draw(self, self.signals, self.autos, self.text, time_str)
            if self.paused:
                continue
            self.check_backlog_train()
            self.color_entry_signal()
            now = time.time()
            delta_real = now - self._last_real_time
            self._last_real_time = now
            if self.timetable_obj:
                self.timetable_obj.window.update()
            if not self.paused:
                self.game_seconds += delta_real * self.time_speed
            # Move all trains
            self.update_spawn()
            for train in self.trains:
                if not train.bounds_check(self.text, self.display_class, self):
                    self.despawn_train(train)
                    continue
                train.move(self.text, self, self.signals, self.display_class)
                # train.station_check(self.text)
                if train in self.trains:
                    train.display_on(self.display_class, self.text)
                

            # Draw signal colors using self.signals
            for signal in self.signals:
                signal.update_color(self.trains)
            self.display_class.display_signal_color(self.signals, self.text)
            self.display_class.display_auto_button_color(self.autos, self.text)
            # Draw and handle events
            
            if self.entry_signal and self.exit_signal:
                self.set_route(self)
            clock.tick(120)
            

# Python's best practice, only run the code if it is the main script
def main():
    # --- Setup code ---
    target_chars = {'à', 'ø', 'û','ã','â',"ù", "á", "©", "¨"}
    signal_type_map = {'à': 'manual','ã':"manual",'â':"manual", "á":"manual", 'ø': 'automatic', 'û': 'automatic', 'ù': 'automatic','©': 'automatic','¨': 'automatic'}
    direction_map = {'à': 'right', 'ø': 'right', 'â': 'right', 'û': 'left', 'ã': 'left', 'ù': 'left', 'á': 'left', '©': 'right', '¨': 'left'}
    mount_map = {'à': 'up', 'ø': 'up',"á":"up",'ù': 'up', 'û': 'down', 'ã': 'down', 'â': 'down','©':'2-right', '¨':'2-left'}
    buffer_map = {'à': False, 'ø': False, 'û': False, 'ã': False, 'â': False, 'ù': False, 'á': False, '©': True, '¨': True}
    #! TODO Rework this to be less tweaking moment
    with open("test.txt", "r", encoding="utf-8") as f:
        text = f.read()
    game = Game(text)
    signals = game.create_signals_from_file(target_chars, signal_type_map, direction_map, mount_map,buffer_map)

    game.display_class = Display_Class()
    game.load_timetable_and_annotated_segments(os.path.join(CWD, JSON_PATH, "timetable.json"))
    game.find_next_signals(signals)
    game.define_switches()
    game.define_auto_buttons()
    # game.spawn_train(6, (1, 10))
    game.run()

if __name__ == "__main__":
    main()
