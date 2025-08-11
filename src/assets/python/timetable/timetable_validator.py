import json
import os
CWD = os.path.dirname(__file__)
JSON_PATH = os.path.join("..", "..","..", "json")
# Load both JSON files
with open(os.path.join(CWD, JSON_PATH, "timetable.json"), 'r') as f:
    timetable_data = json.load(f)

with open(os.path.join(CWD, JSON_PATH, "annotated_segments.json"), 'r') as f:
    annotated_segments = json.load(f)

# Convert annotated_segments into a set of (station, platform) tuples for easy lookup
annotated_stations = set()
annotated_set = set()
for segment in annotated_segments:
    station = segment.get('station')
    platform = segment.get('platform')
    annotated_stations.add(station)
    annotated_set.add((station, platform))

# Check timetable data against the annotated_segments
missing_entries = []

for entry in timetable_data:
    # For the start location
    start_station = entry['start_location']['station']
    start_platform = entry['start_location']['platform']
    
    # If the platform is empty, only check the station
    # print(start_station, start_platform)
    if start_platform == "" and (start_station, "") not in annotated_set:
        missing_entries.append(f"Missing entry: {start_station} (Platform unspecified)")
    if (start_station, start_platform) not in annotated_set:
        # Check for both station and platform
        if (start_station, "") not in annotated_set:
            missing_entries.append(f"Missing entry: {start_station} (Platform {start_platform})")

    # For the stops
    for stop in entry['stops']:
        stop_station = stop['station']
        stop_platform = stop['platform']
        
        # If the platform is empty, only check the station
        if stop_platform == "":
            if stop_station not in annotated_stations:
                missing_entries.append(f"Missing entry: {stop_station} (Platform unspecified)")
        elif (stop_station, stop_platform) not in annotated_set:
            # Check for both station and platform
            if (stop_station, "") not in annotated_set:
                missing_entries.append(f"Missing entry: {stop_station} (Platform {stop_platform})")

# Print the missing entries
if missing_entries:
    for missing in missing_entries:
        print(missing)
else:
    print("All platforms and stations are accounted for.")