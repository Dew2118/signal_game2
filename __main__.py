import cProfile
import traceback
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
import winsound
import threading
import easygui
import math
import tkinter as tk
import os
from pathlib import Path
from src.assets.python.layout.ars import ARSManager

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(BASE_DIR, "src", "json")
SPAWN_SOUND = os.path.join(BASE_DIR, "src", "assets", "sounds", "Speech On.wav")

# Create a "saves" folder in the current directory if it doesn't exist
if not os.path.exists('saves'):
    os.makedirs('saves')
CWD = BASE_DIR # CWD = Current Working Directory, pretend it is a const too
from src.assets.python.timetable.display_timetable import Timetable
class Game:
    def __init__(self, text, display_class, layout_file, scenario):
        self.ars_on = False
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
        self.spawned_start_coords = set()
        self.approach_map = {}
        self.approach_displayed = {}
        self.last_sent = {}
        self.last_sent_coords = {}
        self.ars_manager = ARSManager(routes_path=os.path.join(JSON_PATH, f"{scenario}_ars_routes.json"))
        self.display_class = display_class
        self.snapshot = False
        self.last_snapshot_interval = -1  # Track the last 5-minute interval we created a snapshot for
        self.lines = self.clone_lines(self.text.splitlines())
        self.layout_file = layout_file
        self.portals = []
        self.wait_time = 1

    @staticmethod
    def clone_lines(lines):
        if lines is None:
            return []
        return [list(row) for row in lines]

    #TODO : rework this to work better with file path
    def load_timetable_and_annotated_segments(self, filename, annotated_segments_file):
        self.display_class.add_log("  | loading " + filename)

        # Load timetables
        with open(filename, "r") as f:
            self.timetables = json.load(f)

        # Load annotated segments (new format only)
        with open(os.path.join(CWD, JSON_PATH, annotated_segments_file), "r") as f:
            data = json.load(f)
            self.annotated_segments = data.get("segments", [])
            self.portals = data.get("portals", [])
            self.wait_time = data.get("wait_time", 1)

        ars_path = os.path.join(JSON_PATH, "ars_routes.json")
        if os.path.exists(ars_path):
            self.ars_manager.load(ars_path)

        # Initialize headcode suffixes
        for seg in self.timetables:
            headcode_prefix = seg.get('headcode_prefix', '')
            if headcode_prefix and headcode_prefix not in self.headcode_suffix:
                self.headcode_suffix[headcode_prefix] = 0

    def get_tt_from_index(self, index):
        for template in self.timetables:
            if template.get("index") == index:
                # self.display_class.add_log("found tt from index")
                return template["stops"], template["headcode_prefix"], template["direction"], template["index"]


    # Function to save the game, defaulting to the "saves" folder
    def save_game(self, name=None):
        # Set the default directory to 'saves' folder
        default_directory = os.path.join(os.getcwd(), 'saves')

        # Open save file dialog with the default directory
        if name:
            filename = os.path.join(default_directory, name)
        else:
            filename = easygui.filesavebox(default=os.path.join(default_directory, "game_save.pkl"),
                                            filetypes=["*.pkl"])
        if filename:  # Check if the user selected a file (not canceled)
            data = {
                "text": self.text,
                "trains": self.trains,
                "signals": self.signals,
                "autos": self.autos,
                "entry_signal": self.entry_signal,
                "exit_signal": self.exit_signal,
                "switches": self.switches,
                "spawned_train": self.spawned_train,
                "game_seconds": self.game_seconds,
                "time_speed": self.time_speed,
                "paused": self.paused,
                "_last_real_time": self._last_real_time,
                "last_spawn_time": self.last_spawn_time,
                "headcode_suffix": self.headcode_suffix,
                "timetables": self.timetables,
                # "timetable_obj": self.timetable_obj,
                "backlog_train_spawn": self.backlog_train_spawn,
                "approach_map": self.approach_map,
                "last_sent": self.last_sent,
                "last_sent_coords": getattr(self, "last_sent_coords", {}),
                "snapshot": self.snapshot,
                "lines": self.lines,
                "layout_file": self.layout_file,
                "portals": self.portals,
                "wait_time": self.wait_time

            }

            with open(filename, "wb") as f:
                pickle.dump(data, f)
            self.display_class.add_log(f"Game saved.")

    # Function to load the game, defaulting to the "saves" folder
    def load_game(self):
        # Set the default directory to 'saves' folder
        default_directory = os.path.join(os.getcwd(), 'saves', "*.pkl")

        # Open open file dialog with the default directory
        print(default_directory)
        filename = easygui.fileopenbox(default=default_directory)
        
        if filename:  # Check if the user selected a file (not canceled)
            try:
                with open(filename, "rb") as f:
                    data = pickle.load(f)

                self.text = data["text"]
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
                self.backlog_train_spawn = data.get("backlog_train_spawn", [])
                self.approach_map = data.get("approach_map", {})
                self.last_sent = data.get("last_sent", {})
                self.last_sent_coords = data.get("last_sent_coords", {})
                self.display_class = Display_Class(self.signals)
                self.snapshot = data.get("snapshot", False)
                self.last_snapshot_interval = -1  # Reset snapshot interval tracker on load
                self.lines = data.get("lines", [])
                self.layout_file = data.get("layout_file", None)
                self.portals = data.get("portals", [])
                self.wait_time = data.get("wait_time", 1)
                for signal in self.signals:
                    signal.last_colored_color = None
                    signal.deactivate_TRTS(self, self.display_class)
                    if signal.route_coords:
                        for coord in signal.route_coords:
                            self.display_class.set_char_color_at_coord(coord[0], coord[1], "white", self)

                for train in self.trains:
                    print("train route_coord is ", train.route_coords)
                    train.move_headcode(self, self.signals, self.display_class)
                    if train.route_coords:
                        for coord in train.route_coords:
                            self.display_class.set_char_color_at_coord(coord[0], coord[1], "white", self)
                for auto in self.autos:
                    auto.colored = False
                self.display_class.add_log(f"Game loaded")
            
            except FileNotFoundError:
                self.display_class.add_log(f"Error: file not found!")
                
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
        spawn_coords = []
        while True:
            if direction == "left":
                x -= 1
            else:
                x += 1
            # self.display_class.add_log(x,y)
            spawn_coords.append((x,y))
            for signal in self.signals:
                if signal.overlap == (x,y) and signal.direction == direction:
                    return spawn_coords


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
            
            start_seg = tt.get('start_location', {})
            direction = tt.get('direction', 'right')

            coord = None
            start_type = start_seg.get('type')
            start_station = start_seg.get('station')
            start_platform = start_seg.get('platform')
            if start_type is not None and start_station and start_platform:
                for segment in self.annotated_segments:
                    if (
                        segment.get('type') == start_type
                        and segment.get('station') == start_station
                        and segment.get('platform') == start_platform
                    ):
                        if direction == 'right':
                            coord = tuple(segment.get('right', segment.get('left', (0, 0))))
                        else:
                            coord = tuple(segment.get('left', segment.get('right', (0, 0))))
                        break

            if coord is None:
                coord = tuple(start_seg.get('left') if 'left' in start_seg else start_seg.get('right', (0, 0)))

            # Prevent duplicate spawns at same 
            if coord in spawned_positions_this_tick:
                continue
            headcode_prefix = tt['headcode_prefix']
            headcode = self.get_headcode_from_prefix(headcode_prefix)
              # Example suffix
            train = self.spawn_train(
                start_coord=coord,
                direction=direction,
                headcode=headcode,
                timetable=tt['stops'],
                timetable_index=tt.get('index', 1),
            )

            spawned_positions_this_tick.add(coord)
        self.last_spawn_time = current_time


    def spawn_train(self, start_coord, direction='right', headcode = "4H69", timetable = [], timetable_index = 1, game_seconds = None, annotated_segments = None):
        if not game_seconds:
            game_seconds = self.game_seconds
        if not annotated_segments:
            annotated_segments = self.annotated_segments
        # coords = [start_coord for _ in range(length)]
        signal_coords = self.find_first_spawn_signal(start_coord, direction)
        if start_coord in self.spawned_start_coords:
            self.backlog_train_spawn.append({"start_coord": start_coord, "direction": direction, "headcode": headcode, "timetable": timetable, "timetable_index": timetable_index, "game_seconds": game_seconds, "annotated_segments": annotated_segments})
            return
        elif not self.check_if_spawnable(signal_coords):
            self.backlog_train_spawn.append({"start_coord": start_coord, "direction": direction, "headcode": headcode, "timetable": timetable, "timetable_index": timetable_index, "game_seconds": game_seconds, "annotated_segments": annotated_segments})
            return
        if start_coord not in self.approach_map:
            threading.Thread(target=winsound.PlaySound, args=(SPAWN_SOUND, winsound.SND_FILENAME)).start()
            self.display_class.add_log(f"train {headcode} spawned at {start_coord}")
        train = Train(start_coord,direction, headcode, timetable, int(self.game_seconds), self.annotated_segments, timetable_index, self.wait_time)
        print("signal coords is ", signal_coords)
        train.route_coords = signal_coords
        # train.color_route_coords(self.display_class, self.text)
        self.trains.append(train)
        self.spawned_start_coords.add(start_coord)
        return train

    def check_backlog_train(self):
        self.spawned_start_coords.clear()
        for backlog_train in list(self.backlog_train_spawn):
            coord = backlog_train["start_coord"]
            signal_coords = self.find_first_spawn_signal(coord, backlog_train["direction"])
            if self.check_if_spawnable(signal_coords):
                self.backlog_train_spawn.remove(backlog_train)
                self.spawn_train(backlog_train["start_coord"], backlog_train["direction"], backlog_train["headcode"], backlog_train["timetable"], backlog_train["timetable_index"])

    def get_entrance_coords_for_coord(self, x, y):
        if not (0 <= y < len(self.lines) and 0 <= x < len(self.lines[y])):
            return None, None

        left_char = self.lines[y][x - 1] if x > 0 else None
        right_char = self.lines[y][x + 1] if x + 1 < len(self.lines[y]) else None

        if left_char == "\\":
            return [(x - offset, y) for offset in range(4, 0, -1)], "left"
        if right_char == "\\":
            return [(x + offset, y) for offset in range(1, 5)], "right"
        return None, None

    def matches_timetable_start_location(self, segment):
        segment_type = segment.get("type")
        segment_station = segment.get("station")
        segment_platform = segment.get("platform")
        if segment_type is None or not segment_station or not segment_platform:
            return False

        for tt in self.timetables or []:
            start_seg = tt.get("start_location", {})
            if not start_seg:
                continue
            if (
                start_seg.get("type") == segment_type
                and start_seg.get("station") == segment_station
                and start_seg.get("platform") == segment_platform
            ):
                return True
        return False

    def setup_approach_and_last_sent(self):
        self.approach_map = {}
        self.approach_displayed = {}
        self.last_sent = {}
        self.last_sent_coords = {}  # Store coords for last_sent separately
        print("[APPROACH] setup_approach_and_last_sent starting")

        for segment in getattr(self, "annotated_segments", []):
            if segment.get("type") != "entrance_exit":
                continue

            left_coord = tuple(segment.get("left", (0, 0))) if segment.get("left") is not None else None
            right_coord = tuple(segment.get("right", (0, 0))) if segment.get("right") is not None else None
            entrance_coords = []
            if left_coord is not None:
                entrance_coords.append(left_coord)
            if right_coord is not None and right_coord != left_coord:
                entrance_coords.append(right_coord)

            for x, y in entrance_coords:
                coords, direction = self.get_entrance_coords_for_coord(x, y)
                if coords is None:
                    continue

                if self.matches_timetable_start_location(segment):
                    self.approach_map[(x, y)] = {
                        "coords": coords,
                        "direction": direction,
                    }
                    print(f"[APPROACH] mapped entrance {(x, y)} to coords {coords} (direction={direction})")
                else:
                    self.last_sent[(x, y)] = None
                    self.last_sent_coords[(x, y)] = coords  # Store coords for display
                    print(f"[LAST_SENT] mapped entrance {(x, y)} to last_sent default (direction={direction})")

                for coord_x, coord_y in coords:
                    self.display_class.set_char_color_at_coord(coord_x, coord_y, "gray", self)
                    self.lines[coord_y][coord_x] = "\\"

    def get_approach_preview_headcode(self, headcode_prefix):
        current_suffix = self.headcode_suffix.get(headcode_prefix, 0)
        return f"{headcode_prefix}{current_suffix:02d}"

    def get_next_approach_spawn(self, entrance_coord):
        if not self.timetables:
            # print(f"[APPROACH] no timetables for {entrance_coord}")
            return None

        current_time = int(self.game_seconds) % 86400
        best = None
        # print(f"[APPROACH] checking next spawn for {entrance_coord} at {current_time}s")

        for tt in self.timetables:
            start_seg = tt.get("start_location", {})
            if not start_seg:
                continue

            coord = None
            start_type = start_seg.get("type")
            start_station = start_seg.get("station")
            start_platform = start_seg.get("platform")
            if start_type is not None and start_station and start_platform:
                for segment in self.annotated_segments:
                    if (
                        segment.get("type") == start_type
                        and segment.get("station") == start_station
                        and segment.get("platform") == start_platform
                    ):
                        direction = tt.get("direction", "right")
                        if direction == "right":
                            coord = tuple(segment.get("right", segment.get("left", (0, 0))))
                        else:
                            coord = tuple(segment.get("left", segment.get("right", (0, 0))))
                        break

            if coord is None:
                if "left" in start_seg:
                    coord = tuple(start_seg.get("left"))
                else:
                    coord = tuple(start_seg.get("right", (0, 0)))

            if tuple(coord) != tuple(entrance_coord):
                continue

            for spawn_time in tt.get("spawn_times", []):
                h, m, s = map(int, spawn_time.split(":"))
                total_seconds = h * 3600 + m * 60 + s
                wait_seconds = (total_seconds - current_time) % 86400
                if 0 <= wait_seconds <= 30:
                    candidate = {
                        "headcode": self.get_approach_preview_headcode(tt.get("headcode_prefix", "")),
                        "wait_seconds": wait_seconds,
                    }
                    if best is None or candidate["wait_seconds"] < best["wait_seconds"]:
                        best = candidate
                    # print(f"[APPROACH] candidate at {entrance_coord}: {candidate['headcode']} in {candidate['wait_seconds']}s")

        if best:
            # print(f"[APPROACH] selected {best['headcode']} for {entrance_coord} (next in {best['wait_seconds']}s)")
            return best["headcode"]
        # print(f"[APPROACH] no timetable spawn within 30s for {entrance_coord}")
        return None

    def _display_approach_headcode(self, coords, headcode):
        display_chars = list(headcode[:4]) if headcode else []
        if len(display_chars) < len(coords):
            display_chars.extend(["\\"] * (len(coords) - len(display_chars)))

        for idx, (coord_x, coord_y) in enumerate(coords):
            char = display_chars[idx] if idx < len(display_chars) else "\\"
            self.lines[coord_y][coord_x] = char
            color = "light blue" if headcode else "gray"
            self.display_class.set_char_color_at_coord(coord_x, coord_y, color, self)


    def check_approach(self):
        for train in self.trains:
            if not getattr(train, "coords", None):
                continue
            if not train.coords:
                continue
            for coord in train.coords[0]:
                if coord in self.last_sent:
                    self.last_sent[coord] = train.headcode
                    print("REPLACED with ", train.headcode, "at", coord)

        for entrance_coord, approach_data in self.approach_map.items():
            coords = approach_data["coords"]

            previous_headcode = self.approach_displayed.get(entrance_coord)

            matching_live_train_at_approach = False
            for train in self.trains:
                if not getattr(train, "coords", None):
                    continue
                if entrance_coord in train.coords[0]:
                    matching_live_train_at_approach = True
                    break

            if matching_live_train_at_approach:
                self.approach_displayed[entrance_coord] = None
                continue

            backlog_headcode = None
            for backlog_train in self.backlog_train_spawn:
                if backlog_train.get("start_coord") == entrance_coord:
                    backlog_headcode = backlog_train.get("headcode")
                    break

            if backlog_headcode:
                if backlog_headcode != previous_headcode:
                    threading.Thread(target=winsound.PlaySound, args=(SPAWN_SOUND, winsound.SND_FILENAME)).start()
                    self.display_class.add_log(f"train {backlog_headcode} approaching at {entrance_coord}")
                self.approach_displayed[entrance_coord] = backlog_headcode
                self._display_approach_headcode(coords, backlog_headcode)
                continue

            timetable_headcode = self.get_next_approach_spawn(entrance_coord)
            if timetable_headcode:
                if timetable_headcode != previous_headcode:
                    threading.Thread(target=winsound.PlaySound, args=(SPAWN_SOUND, winsound.SND_FILENAME)).start()
                    self.display_class.add_log(f"train {timetable_headcode} approaching at {entrance_coord}")
                self.approach_displayed[entrance_coord] = timetable_headcode
                self._display_approach_headcode(coords, timetable_headcode)
            else:
                if previous_headcode is not None:
                    print(f"[APPROACH] no train, resetting approach at {entrance_coord} to backslashes")
                self.approach_displayed[entrance_coord] = None
                self._display_approach_headcode(coords, None)

            for train in self.trains:
                if getattr(train, "headcode", None) == timetable_headcode and getattr(train, "coords", None):
                    current_head = train.coords[0][0]
                    if current_head != entrance_coord:
                        print(f"[APPROACH] clearing preview at {entrance_coord}: same headcode train has moved beyond entrance coord")
                        self.approach_displayed[entrance_coord] = None
                        self._display_approach_headcode(coords, None)
                        break

        for entrance_coord, last_headcode in list(self.last_sent.items()):
            if entrance_coord in self.approach_map:
                continue
            coords = self.last_sent_coords.get(entrance_coord)
            if coords is None:
                continue
            self._display_approach_headcode(coords, last_headcode)

    def check_if_spawnable(self, coords):
        for coord in coords:
            color = self.display_class.get_char_color_at_coord(coord[0], coord[1], self.lines)
            if color != (128, 128, 128) and color != None:
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
                    shunt = False
                    signal_type = signal_type_map.get(char, "automatic")
                    color = "red"  # Force all signals to be red
                    direction = direction_map.get(char, "right")
                    buffer = buffer_map.get(char, False)
                    if direction == "right" and not buffer:
                        if lines[y][x+1] in "sr":
                            shunt = True
                        elif lines[y][x+1] not in "qÂ":
                            continue
                    elif direction == "left" and not buffer:
                        if lines[y][x-1] in "sr":
                            self.display_class.add_log("shunt to the left")
                            shunt = True
                        elif lines[y][x-1] not in "qÂ":
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
                        buffer=buffer,
                        shunt = shunt
                    )
                    signals.append(signal)
                    i += 1
        self.signals = signals  # Store signals in Game
        return signals

    def define_auto_and_TRTS_buttons(self):
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
                    # self.display_class.add_log("char to the right are", char_to_the_right)
                    if char_to_the_right == "A":
                        if char_two_to_the_right in target_chars:
                            signal_coord = (x + 2, y)
                            for s in self.signals:
                                if s.coord == signal_coord:
                                    signal = s
                            auto = Auto((x,y),signal, "right")
                            self.autos.append(auto)
                        elif char_three_to_the_right in target_chars:
                            signal_coord = (x + 3, y)
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
                    elif char == "p":
                        if char_three_to_the_left in target_chars:
                            signal_coord = (x - 3, y)
                            for s in self.signals:
                                if s.coord == signal_coord:
                                    s.TRTS_button_coord = (x,y)
                        elif char_three_to_the_right in target_chars:
                            signal_coord = (x + 3, y)
                            for s in self.signals:
                                if s.coord == signal_coord:
                                    s.TRTS_button_coord = (x,y)
                
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
                        self.display_class.add_log(x,y+1, "{")
                if (char == "h" or char == "}") and char_above == "a":
                    self.switches.append([x,y-1, "i", "right"])
                    if char == "}":
                        self.display_class.add_log(x,y-1, "}")
                if (char == "j" or char == "n" or char == "}") and char_below == "a":
                    self.switches.append([x,y+1, "k","right"])
                    if char == "}":
                        self.display_class.add_log(x,y+1, "}")
                if (char == "k" or char == "o" or char == "{") and char_above == "a":
                    self.switches.append([x,y-1, "j","left"])
                    if char == "{":
                        self.display_class.add_log(x,y-1, "{")

    def change_switch(self, switch_index, switch_direction, lines):
        x, y, new_char, direction = self.switches[switch_index]
        if switch_direction == "normal":
            new_char = "a"

        if 0 <= y < len(lines) and 0 <= x < len(lines[y]):
            if switch_direction == "change":
                if lines[y][x] != "a":
                    lines[y][x] = "a"
                else:
                    lines[y][x] = new_char
            else:
                print("BEFORE CHANGE SWITCH", self.lines[y][x], "NEW CHAR IS", new_char)
                lines[y][x] = new_char
                print("AFTER CHANGE SWITCH", self.lines[y][x])
        return lines
    
    def get_switch_position(self, switch_index, lines):
        x, y, new_char, direction = self.switches[switch_index]
        print("getswitchpos is", x,y, lines[y][x])
        char = lines[y][x]
        if char == "a":
            return "normal"
        return "reverse"

    def find_next_signals(self, signals):
        signal_lookup = {(s.coord[0], s.coord[1]): s for s in signals}
        last_char = "F"
        last_last_char = "F"
        for signal in signals:
            if signal.buffer:
                x,y = signal.coord
                if signal.direction == "right":
                    x -= 2
                elif signal.direction == "left":
                    x += 2
                signal.overlap = (x,y)
                continue
            x, y = signal.coord
            print("signal coord is ", x,y)
            if signal.mount == 'up':
                y += 1
            elif signal.mount == 'down':
                y -= 1
            direction = signal.direction
            while 0 <= y < len(self.lines) - 1 and 0 <= x < len(self.lines[y]) - 1:
                self.display_class.add_log(x,y)
                x, y, direction, last_char, direction_change, last_last_char, temporary_characters = self.path_find(self.lines, x, y, direction, signal.direction, last_char, last_last_char, [])
                # print(x,y)
                if not (0 <= y < len(self.lines) and 0 <= x < len(self.lines[y])):
                    break
                if (((self.lines[y][x] in "[c" or self.lines[y][x-1] == "b") and signal.direction == "left") or ((self.lines[y][x] in "]b" or self.lines[y][x+1] == "c") and signal.direction == "right")) and signal.overlap == (0,0):
                    signal.overlap = (x,y)
                    if signal.signal_type != "automatic":
                        break
                for dy in [-1, 0, 1]:
                    ny = y + dy
                    if dy == -1: 
                        mount = "up" 
                    else: 
                        mount = "down"
                    if 0 <= ny < len(self.lines):
                        candidate = signal_lookup.get((x, ny))
                        if candidate and candidate.direction == direction and candidate.mount == mount:
                            if signal.signal_type == "automatic":
                                signal.next_signal = candidate
                                print("found next signal at", candidate.coord)
                            break
                if signal.next_signal:
                    break

    def handle_temporary_characters(self, temporary_characters):
        for temporary_character in temporary_characters:
            (x,y), original_char, new_char = temporary_character
            self.lines[y][x] = new_char
            print("handling temporary character at", (x,y), "to", new_char)

    def reset_temporary_characters(self, temporary_characters):
        for temporary_character in temporary_characters:
            (x,y), original_char, new_char = temporary_character
            self.lines[y][x] = original_char
            print("resetting temporary character at", (x,y), "to", original_char)

    def set_route(self, dont_set = False):
        coords = self.entry_signal.get_coords_to_next_signal(self.exit_signal, self, self.switches, self.layout_file, self.signals, self.trains, dont_set)
        if not dont_set:
            if not coords:
                self.entry_signal = None
                self.exit_signal = None
                return
            self.entry_signal.next_signal = self.exit_signal
            self.entry_signal.route_set = True
            train_coords = []
            for train in self.trains:
                for coord_list in train.coords:
                    train_coords.extend(coord_list)
                train_coords.extend(train.route_coords)
            filtered_coords = set(coords) - set(train_coords)
            for coord in filtered_coords:
                self.display_class.set_char_color_at_coord(coord[0], coord[1], "white", self)
            self.entry_signal = None
            self.exit_signal = None
        return coords

    def despawn_train(self, train):
        self.trains.remove(train)
        self.display_class.add_log("train removed")

    def open_timetable_window(self, train):
        self.timetable_obj = Timetable(train)
        self.timetable_obj.show_timetable_window(self)

    def color_entry_signal(self):
        # The entry-signal highlight is handled by the flashing adjacent tile only.
        # Do not force the signal lamp itself to white.
        return

    def path_find(self, lines, x, y, direction, main_direction, last_char, last_last_char, temporary_characters = []):
        right_up = 'ko'
        right_down = "im"
        left_up = "hl"
        left_down = 'jn'
        both_up = "z"
        both_down = "y"
        vertical = "|ö"
        direction_change = None
        char = lines[y][x]
        # print("char is", char)
        if char in vertical:
            # self.display_class.add_log(direction)
            if (last_char in right_up and direction == 'right') or (last_char in left_up and direction == 'left'):
                direction = "up"
                print("direction is up")
            elif (last_char in right_down and direction == 'right') or (last_char in left_down and direction == 'left'):
                # self.display_class.add_log("direction is down")
                direction = "down"
        next_char = self.get_next_char_from_direction(direction, x, y,char, lines)
        print("next char is", next_char)
        if next_char == "÷":
            if hasattr(self, 'portals'):
                # Step 1: Compute tentative next position
                amended_x = x + (1 if direction == "right" else -1 if direction == "left" else 0)
                print("moving one step, position is", x, y)

                # Step 2: Check all portals
                for portal in self.portals:
                    (x1, y1), (x2, y2), portal_dir = portal

                    # Step 3: Check if we're on either side of the portal
                    if (amended_x, y) == (x1, y1):
                        target_x, target_y = x2, y2
                    elif (amended_x, y) == (x2, y2):
                        target_x, target_y = x1, y1
                    else:
                        continue  # not a portal match

                    # Step 4: Apply portal teleport
                    amended_x, y = target_x, target_y

                    # Step 5: Flip direction if "opposite"
                    if portal_dir == "opposite":
                        if direction == "right":
                            direction = "left"
                        elif direction == "left":
                            direction = "right"
                        direction_change = [(amended_x, y), direction]

                    # Step 6: Adjust position for movement after teleport (same logic as before)
                    if direction == "right":
                        amended_x += 1
                    elif direction == "left":
                        amended_x -= 1

                    

                    print("teleported to", amended_x, y, "new direction is", direction)
                    return amended_x, y, direction, last_char, direction_change, last_last_char, temporary_characters
            x, y = self.skip_parts("÷", direction, x, y, lines)
        elif next_char == "ö":
            x, y = self.skip_parts("ö", direction, x, y, lines)

        if (char in right_up and direction == 'right') or (char in left_up and direction == 'left'):
            y -= 1
        elif (char in right_down and direction == 'right') or (char in left_down and direction == 'left'):
            y += 1

        elif char in vertical:
            if direction == "up":
                y -= 1
            elif direction == "down":
                y += 1
        elif direction == "up" or direction == "down":
            if char in right_down or char in right_up:
                direction = "left"
                if direction != main_direction:
                    direction_change = [(x,y), direction]
                x -= 1
            elif char in left_down or char in left_up:
                direction = "right"
                if direction != main_direction:
                    direction_change = [(x,y), direction]
                x += 1
        
            
        elif char == "e" and last_char == "d":
            if direction == "right":
                if last_last_char in right_down:
                    direction = "down"
                    temporary_characters.append([(x-1,y), "d", "h"])
                    temporary_characters.append([(x,y), "e", "i"])
                    y += 1
                else:
                    direction = "right"
                    temporary_characters.append([(x-1,y), "d", "a"])
                    temporary_characters.append([(x,y), "e", "a"])
                    
                    x += 1
        elif char == "d" and last_char == "e":
            if direction == "left":
                if last_last_char in left_up:
                    direction = "up"
                    temporary_characters.append([(x,y), "d", "h"])
                    temporary_characters.append([(x+1,y), "e", "i"])
                    y -= 1
                else:
                    direction = "left"
                    temporary_characters.append([(x,y), "d", "a"])
                    temporary_characters.append([(x+1,y), "e", "a"])
                    x -= 1

        elif char == "g" and last_char == "f":
            if direction == "right":
                if last_last_char in right_up:
                    direction = "up"
                    temporary_characters.append([(x-1,y), "f", "j"])
                    temporary_characters.append([(x,y), "g", "k"])
                    y -= 1
                else:
                    direction = "right"
                    temporary_characters.append([(x-1,y), "f", "a"])
                    temporary_characters.append([(x,y), "g", "a"])
                    x += 1
        elif char == "f" and last_char == "g":
            if direction == "left":
                if last_last_char in left_down:
                    direction = "down"
                    temporary_characters.append([(x,y), "f", "j"])
                    temporary_characters.append([(x+1,y), "g", "k"])
                    y += 1
                else:
                    direction = "left"
                    temporary_characters.append([(x,y), "f", "a"])
                    temporary_characters.append([(x+1,y), "g", "a"])
                    x -= 1
                
        else:
            if char in both_up:
                if last_char == both_down:
                    if direction == "right":
                        temporary_characters.append([(x,y), both_up, "h"])
                        temporary_characters.append([(x,y-1), both_down, "i"])
                        x += 1
                    else:
                        temporary_characters.append([(x,y), both_up, "k"])
                        temporary_characters.append([(x,y-1), both_down, "j"])
                        x -= 1
                else:
                    y -= 1
            elif char in both_down:
                if last_char == both_up:
                    if direction == "right":
                        temporary_characters.append([(x,y), both_down, "j"])
                        temporary_characters.append([(x,y+1), both_up, "k"])
                        
                        x += 1
                    else:
                        temporary_characters.append([(x,y), both_down, "i"])
                        temporary_characters.append([(x,y+1), both_up, "h"])
                        x -= 1
                else:
                    y += 1

            elif char == "{":
                if last_char == "}":
                    if last_last_char in right_up:
                        temporary_characters.append([(x,y), "{", "k"])
                        temporary_characters.append([(x-1,y), "}", "j"])
                        y -= 1
                    elif last_last_char in right_down:
                        temporary_characters.append([(x,y), "{", "i"])
                        temporary_characters.append([(x-1,y), "}", "h"])
                        y += 1
                else:
                    x -= 1
            elif char == "}":
                if last_char == "{":
                    if last_last_char in left_up:
                        temporary_characters.append([(x+1,y), "{", "i"])
                        temporary_characters.append([(x,y), "}", "h"])
                        y -= 1
                    elif last_last_char in left_down:
                        temporary_characters.append([(x+1,y), "{", "k"])
                        temporary_characters.append([(x,y), "}", "j"])
                        y += 1
                else:
                    x += 1

            elif char != " ":
                if direction == 'right':
                    x += 1
                elif direction == 'left':
                    x -= 1
            else:
                return -1,-1,None,None,None, None, []

        last_last_char = last_char
        last_char = char
        
        return x, y, direction, last_char, direction_change, last_last_char, temporary_characters
    
    def skip_parts(self, character, direction, x, y, lines):
        passed = False
        trash = False
        direction_to_x_y_addition = {"right": (1, 0), "left": (-1, 0), "up": (0, -1), "down": (0, 1)}
        right_up = 'ko'
        right_down = "im"
        left_up = "hl"
        left_down = 'jn'
        char = lines[y][x]
        if char:
            if (char in right_down and direction == "right") or (char in left_down and direction == "left"):
                direction = "down"
            elif (char in right_up and direction == "right") or (char in left_up and direction == "left"):
                direction = "up"
        while passed == False:
            x_addition, y_addition = direction_to_x_y_addition[direction]
            x += x_addition
            y += y_addition
            print("skip parts x, y is ", x, y)
            char = lines[y][x]
            if char == character:
                if not trash:
                    trash = True
                else:
                    passed = True
                    break
        return x, y
    
    def get_next_char_from_direction(self, direction, x, y, char, lines):
        direction_to_x_y_addition = {"right": (1, 0), "left": (-1, 0), "up": (0, -1), "down": (0, 1)}
        right_up = 'ko'
        right_down = "im"
        left_up = "hl"
        left_down = 'jn'
        if char:
            if (char in right_down and direction == "right") or (char in left_down and direction == "left"):
                direction = "down"
            elif (char in right_up and direction == "right") or (char in left_up and direction == "left"):
                direction = "up"
        x_addition, y_addition = direction_to_x_y_addition[direction]
        print("next char coord", x + x_addition, y + y_addition, "direction ", direction)
        return lines[y + y_addition][x + x_addition]
    
    def update_signals(self):
        for signal in self.signals:
            signal.update_color(self.trains)
        self.display_class.display_signal_color(self.signals, self)

    def run(self):
        running = True
        clock = pygame.time.Clock()
        for signal in self.signals:
            signal.deactivate_TRTS(self, self.display_class)
        # try:
        for i in range(10):
            self.update_signals()
        self.setup_approach_and_last_sent()
        while running:
            try:
                total_seconds = int(self.game_seconds)
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60
                time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d} *{self.time_speed}"
                running = self.display_class.update_and_draw(self, self.signals, self.autos, self.lines, time_str)
                # Draw signal colors using self.signals
                self.update_signals()
                self.display_class.update_entry_signal_flash(self, self.lines)
                self.display_class.display_auto_button_color(self.autos, self)
                self.check_approach()
                # Draw and handle events
                self.color_entry_signal()
                if self.entry_signal and self.exit_signal:
                    self.set_route()
                # if hasattr(self, "ars_manager"):
                #     self.ars_manager.update(self)
                for train in self.trains:
                    if not self.paused:
                        train.move(self.lines, self, self.signals, self.display_class)
                    # if train in self.trains:
                        # train.color_route_coords(self.display_class, self.lines, self)
                        # train.display_on(self.display_class, self.lines, self)
                if self.paused:
                    continue
                self.check_backlog_train()
                
                now = time.time()
                delta_real = now - self._last_real_time
                self._last_real_time = now
                if self.timetable_obj:
                    self.timetable_obj.window.update()
                if not self.paused:
                    self.game_seconds += delta_real * self.time_speed
                # Move all trains
                total_seconds = int(self.game_seconds)
                current_interval = total_seconds // (5*60)
                if total_seconds % (5*60) == 0 and current_interval != self.last_snapshot_interval:
                    self.save_game(f"snapshot_{hours:02d}{minutes:02d}{seconds:02d}.pkl")
                    self.last_snapshot_interval = current_interval
                self.update_spawn()
                clock.tick(120)
            except Exception as e:
                print("error in main loop:", e)
                traceback.print_exc()
            

# Python's best practice, only run the code if it is the main script

def choose_scenario():
    base_dir = Path(__file__).parent
    map_files = list(base_dir.glob("*_map.txt"))
    scenarios = [os.path.basename(f).replace("_map.txt", "") for f in map_files]

    selected = {"name": None}

    def choose(event=None):
        """Set the selected scenario and close the window"""
        selection = listbox.curselection()
        if selection:
            selected["name"] = listbox.get(selection[0])
            root.destroy()

    def update_filter(*args):
        """Update the listbox based on the search entry"""
        search_term = search_var.get().lower()
        listbox.delete(0, tk.END)
        for scenario in scenarios:
            if search_term in scenario.lower():
                listbox.insert(tk.END, scenario)

    root = tk.Tk()
    root.title("Select Scenario")
    root.geometry("400x400")  # Starting size

    tk.Label(root, text="Choose a scenario:", font=("Arial", 12)).pack(pady=10)

    # Search entry
    search_var = tk.StringVar()
    search_var.trace_add("write", update_filter)  # Update list as user types
    tk.Entry(root, textvariable=search_var, width=30).pack(pady=5)

    # Scrollable listbox
    frame = tk.Frame(root)
    frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    scrollbar = tk.Scrollbar(frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    listbox = tk.Listbox(frame, yscrollcommand=scrollbar.set, font=("Arial", 11))
    listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.config(command=listbox.yview)

    # Populate the listbox
    for scenario in scenarios:
        listbox.insert(tk.END, scenario)

    # Bind double click or Enter key to choose
    listbox.bind("<Double-Button-1>", choose)
    listbox.bind("<Return>", choose)

    root.mainloop()

    scenario = selected["name"]
    return scenario

def main():
    scenario = choose_scenario()

    if scenario:
        # global LAYOUT_FILE, TIMETABLE_FILE, ANNOTATED_SEGMENTS_FILE
        layout_file = f"{scenario}_map.txt"
        timetable_file = f"{scenario}_timetable.json"
        annotated_segments_file = f"{scenario}_annotated_segments.json"

        print("LAYOUT_FILE =", layout_file)
        print("TIMETABLE_FILE =", timetable_file)
        print("ANNOTATED_SEGMENTS =", annotated_segments_file)
    else:
        print("No scenario selected")
    # --- Setup code ---
    target_chars = {'à', 'ø', 'û','ã','â',"ù", "á", "©", "¨", "ú"}
    signal_type_map = {'à': 'manual','ã':"manual",'â':"manual", "á":"manual", 'ø': 'automatic', 'û': 'automatic', 'ù': 'automatic', 'ú':"automatic",'©': 'automatic','¨': 'automatic'}
    direction_map = {'à': 'right', 'ø': 'right', 'â': 'right', 'û': 'left', 'ã': 'left', 'ù': 'left', "ú": 'right', 'á': 'left', '©': 'right', '¨': 'left'}
    mount_map = {'à': 'up', 'ø': 'up',"á":"up",'ù': 'up', 'û': 'down', 'ã': 'down', 'â': 'down',"ú":"down",'©':'2-right', '¨':'2-left'}
    buffer_map = {'à': False, 'ø': False, 'û': False, 'ã': False, 'â': False, 'ù': False, 'á': False, 'ú': False, '©': True, '¨': True}
    #! TODO Rework this to be less tweaking moment
    with open(layout_file, "r", encoding="utf-8") as f:
        text = f.read()
    game = Game(text, Display_Class(), layout_file, scenario)
    signals = game.create_signals_from_file(target_chars, signal_type_map, direction_map, mount_map,buffer_map)

    # game.display_class = 
    game.load_timetable_and_annotated_segments(os.path.join(CWD, JSON_PATH, timetable_file), annotated_segments_file)
    game.find_next_signals(signals)
    game.define_switches()
    game.define_auto_and_TRTS_buttons()
    # game.spawn_train(6, (1, 10))
    game.run()

# cProfile.run("main()")
if __name__ == "__main__":
    main()
