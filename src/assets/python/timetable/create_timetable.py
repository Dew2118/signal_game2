import json
import os
import datetime

CWD = os.path.dirname(__file__)
JSON_PATH = os.path.join("..", "..","..", "json")

class TimetableCreator:
    def __init__(self, segments_file=os.path.join(CWD, JSON_PATH, "zone_A_annotated_segments.json")):
        with open(segments_file, "r") as f:
            data = json.load(f)

        self.segments = data.get("segments", [])
        self.portals = data.get("portals", [])

        self.timetable = {
            "headcode_prefix": "",
            "start_location": None,
            "direction": "",
            "stops": [],
            "spawn_times": []
        }

        for seg in self.segments:
            if 'type' not in seg:
                if seg.get('left') == seg.get('right'):
                    seg['type'] = 'entrance_exit'
                else:
                    seg['type'] = 'platform'

        self.entrances = sorted(
            [s for s in self.segments if s['type'] == 'entrance_exit'],
            key=lambda x: (x.get('station', '').lower(), x.get('platform', '').lower())
        )
        self.platforms = sorted(
            [s for s in self.segments if s['type'] == 'platform'],
            key=lambda x: (x.get('station', '').lower(), x.get('platform', '').lower())
        )

    def input_spawn_times(self):
        choice = input("Do you want to define spawn times? (y/n): ").strip().lower()
        if choice != 'y':
            self.timetable["spawn_times"] = []
            return

        while True:
            try:
                h = int(input("Enter spawn start hour (0-23): ").strip())
                m = int(input("Enter spawn start minute (0-59): ").strip())
                s = int(input("Enter spawn start second (0-59): ").strip())
                start_time = datetime.timedelta(hours=h, minutes=m, seconds=s)
                break
            except ValueError:
                print("Invalid time input. Try again.")

        while True:
            try:
                interval = int(input("Enter interval between spawns (in seconds): ").strip())
                if interval <= 0:
                    raise ValueError
                break
            except ValueError:
                print("Invalid interval. Enter a positive number.")

        while True:
            try:
                count = int(input("How many spawns?: ").strip())
                if count <= 0:
                    raise ValueError
                break
            except ValueError:
                print("Invalid count. Enter a positive number.")

        self.timetable["spawn_times"] = []
        for i in range(count):
            spawn_time = start_time + datetime.timedelta(seconds=i * interval)
            spawn_str = str(spawn_time)
            if spawn_time.days > 0:
                spawn_str = str(datetime.timedelta(seconds=spawn_time.total_seconds() % 86400))
            self.timetable["spawn_times"].append(spawn_str)

    def input_headcode(self):
        while True:
            code = input("Enter first 2 digits of headcode (e.g., 2H): ").strip().upper()
            if len(code) == 2:
                self.timetable['headcode_prefix'] = code
                break
            print("Invalid input. Please enter exactly 2 characters.")

    def input_start_location(self):
        print("Available starting locations:")
        print("Entrances/Exits:")
        for i, e in enumerate(self.entrances):
            print(f"  {i}: Station: {e.get('station', 'N/A')}, Platform: {e.get('platform', 'N/A')}")
        print("Platforms:")
        for i, p in enumerate(self.platforms):
            print(f"  {i + len(self.entrances)}: Station: {p.get('station', 'N/A')}, Platform: {p.get('platform', 'N/A')}")

        while True:
            idx = input(f"Choose start location by index (0 to {len(self.entrances)+len(self.platforms)-1}): ")
            if idx.isdigit():
                idx = int(idx)
                if 0 <= idx < len(self.entrances) + len(self.platforms):
                    if idx < len(self.entrances):
                        self.timetable['start_location'] = self.entrances[idx]
                    else:
                        self.timetable['start_location'] = self.platforms[idx - len(self.entrances)]
                    break
            print("Invalid index. Try again.")

    def input_direction(self):
        while True:
            d = input("Enter direction of travel (left/right): ").strip().lower()
            if d in ("left", "right"):
                self.timetable['direction'] = d
                break
            print("Invalid direction. Please enter 'left' or 'right'.")

    def input_stops(self, filename):
        print("Enter stops (station and platform names). When done, type 'done'.")
        last_stop_coord = self.timetable['start_location'][self.timetable['direction']]
        last_value = 0

        while True:
            station = input("Station name (or 'done' to finish): ").strip()
            if station.lower() == "done":
                break

            platform = input("Platform name: ").strip()
            second_last_stop_coord = None
            matched_seg = None

            for seg in self.segments:
                if seg['station'] == station and (seg['platform'] == platform or platform == ''):
                    second_last_stop_coord = (seg[self.timetable['direction']][0], seg[self.timetable['direction']][1])
                    matched_seg = seg
                    break

            if second_last_stop_coord is None:
                print("location invalid please retry")
                continue

            # ✅ Distance
            distance = abs(last_stop_coord[0] - second_last_stop_coord[0]) + \
                       abs(last_stop_coord[1] - second_last_stop_coord[1])

            # ✅ Wait time from JSON
            wait_time = matched_seg.get("wait_time", 1)
            if wait_time <= 0:
                wait_time = 1

            # ✅ Adjusted travel time
            adjusted_time = round(distance / wait_time)

            travel_time = int(input(
                f"Arrival time addition (sec) travel time is ({adjusted_time}): "
            ).strip())

            stop_time = int(input("Stop time (sec): ").strip())

            last_value += travel_time
            arr = last_value
            last_value += stop_time
            dep = last_value

            reverse = input("Reverse direction here? (y/n): ").strip().lower() == "y"

            last_stop_coord = second_last_stop_coord

            self.timetable['stops'].append({
                "station": station,
                "platform": platform,
                "arrival_offset": arr,
                "departure_offset": dep,
                "reverse_direction": reverse,
                "despawn": False
            })

        if self.timetable['stops']:
            last_stop = self.timetable['stops'][-1]

            if input("Change timetable at last stop? (y/n): ").strip().lower() == "y":
                all_timetables = []

                if os.path.exists(filename):
                    with open(filename, "r") as f:
                        try:
                            all_timetables = json.load(f)
                        except json.JSONDecodeError:
                            print("Warning: timetable file was corrupted or empty. Starting fresh.")
                            all_timetables = []

                next_index = len(all_timetables) + 1
                new_tt_code = input(f"Enter new timetable index (e.g., {next_index}): ").strip().upper()
                last_stop['change_timetable'] = int(new_tt_code)

            last_stop['despawn'] = input("Despawn at last stop? (y/n): ").strip().lower() == "y"

    def save_timetable(self, filename):
        all_timetables = []

        if os.path.exists(filename):
            with open(filename, "r") as f:
                try:
                    all_timetables = json.load(f)
                except json.JSONDecodeError:
                    print("Warning: timetable file was corrupted or empty. Starting fresh.")
                    all_timetables = []

        self.timetable["index"] = len(all_timetables)
        all_timetables.append(self.timetable)

        with open(filename, "w") as f:
            json.dump(all_timetables, f, indent=4)

        print(f"Timetable added and saved to {filename}")

    def run(self):
        self.input_headcode()
        self.input_spawn_times()
        self.input_start_location()
        self.input_direction()
        self.input_stops(os.path.join(CWD, JSON_PATH, "zone_A_timetable.json"))
        self.save_timetable(os.path.join(CWD, JSON_PATH, "zone_A_timetable.json"))


if __name__ == "__main__":
    t = TimetableCreator()
    t.run()