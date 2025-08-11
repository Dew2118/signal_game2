import json
import os
import datetime
CWD = os.path.dirname(__file__)
JSON_PATH = os.path.join("..", "..","..", "json")
class TimetableCreator:
    def __init__(self, segments_file=os.path.join(CWD, JSON_PATH, "annotated_segments.json")):
        with open(segments_file, "r") as f:
            self.segments = json.load(f)
        self.timetable = {
            "headcode_prefix": "",
            "start_location": None,
            "direction": "",
            "stops": [],
            "spawn_times": []
        }
        # Add type detection here if not already present
        for seg in self.segments:
            if 'type' not in seg:
                # If left == right, treat as entrance/exit
                if seg.get('left') == seg.get('right'):
                    seg['type'] = 'entrance_exit'
                else:
                    seg['type'] = 'platform'

        # Separate entrances and platforms, sort alphabetically by station name then platform
        self.entrances = sorted(
            [s for s in self.segments if s['type'] == 'entrance_exit'],
            key=lambda x: (x.get('station', '').lower(), x.get('platform', '').lower())
        )
        self.platforms = sorted(
            [s for s in self.segments if s['type'] == 'platform'],
            key=lambda x: (x.get('station', '').lower(), x.get('platform', '').lower())
        )

    import datetime

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

        # Generate the times
        self.timetable["spawn_times"] = []
        for i in range(count):
            spawn_time = start_time + datetime.timedelta(seconds=i * interval)
            # Format to HH:MM:SS
            spawn_str = str(spawn_time)
            if spawn_time.days > 0:
                # Remove days if over 24 hours
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
                        break
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

    def input_stops(self):
        print("Enter stops (station and platform names). When done, type 'done'.")
        while True:
            station = input("Station name (or 'done' to finish): ").strip()
            if station.lower() == "done":
                break
            platform = input("Platform name: ").strip()
            arr = input("Arrival time addition (sec): ").strip()
            dep = input("Departure time addition (sec): ").strip()
            reverse = input("Reverse direction here? (y/n): ").strip().lower() == "y"
            change_tt = False
            despawn = False

            # Will handle these only at last stop after finishing input

            try:
                arr = int(arr)
                dep = int(dep)
            except:
                print("Invalid times. Please enter numbers.")
                continue

            self.timetable['stops'].append({
                "station": station,
                "platform": platform,
                "arrival_offset": arr,
                "departure_offset": dep,
                "reverse_direction": reverse,
                # "change_timetable": False,
                "despawn": False
            })

        if self.timetable['stops']:
            # Ask for last stop special flags
            last_stop = self.timetable['stops'][-1]

            if input("Change timetable at last stop? (y/n): ").strip().lower() == "y":
                # while True:
                new_tt_code = input("Enter new timetable index (e.g., 1): ").strip().upper()
                last_stop['change_timetable'] = int(new_tt_code)
            # else:
            #     # Only add key if actually relevant
            #     last_stop['change_timetable'] = None

            last_stop['despawn'] = input("Despawn at last stop? (y/n): ").strip().lower() == "y"



    def save_timetable(self, filename=os.path.join(CWD, JSON_PATH, "timetable.json")):
        all_timetables = []

        # Step 1: Load existing data if the file exists
        if os.path.exists(filename):
            with open(filename, "r") as f:
                try:
                    all_timetables = json.load(f)
                except json.JSONDecodeError:
                    print("Warning: timetable file was corrupted or empty. Starting fresh.")
                    all_timetables = []

        # Step 2: Append the current timetable
        self.timetable["index"] = len(all_timetables)
        all_timetables.append(self.timetable)
        
        # Step 3: Write back the updated list
        with open(filename, "w") as f:
            json.dump(all_timetables, f, indent=4)

        print(f"Timetable added and saved to {filename}")

    def run(self):
        self.input_headcode()
        self.input_spawn_times()  # NEW LINE HERE
        self.input_start_location()
        self.input_direction()
        self.input_stops()
        self.save_timetable()



if __name__ == "__main__":
    t = TimetableCreator()
    t.run()
