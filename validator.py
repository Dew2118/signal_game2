import json
from collections import defaultdict

def validate_stations(json_data):
    # Step 1: Check if there is only one unique station
    station_names = set()
    for segment in json_data:
        station_names.add(segment.get("station"))

    if len(station_names) == 1:
        print(f"Warning: Only one station found: {list(station_names)[0]}. It could be a typo.")
    
    # Step 2: Check for loner station names (stations mentioned only once)
    station_count = defaultdict(int)
    for segment in json_data:
        station = segment.get("station")
        station_count[station] += 1
    
    for station, count in station_count.items():
        if count == 1:
            print(f"Warning: Loner station found: {station}. It may be a typo or a station not connected to others.")
    
    # Step 3: Check for duplicated platform within the same station
    platform_set = set()
    for segment in json_data:
        station = segment.get("station")
        platform = segment.get("platform")
        
        # Combine station and platform as a unique pair (tuple)
        station_platform_pair = (station, platform)
        
        # Check if the pair already exists
        if station_platform_pair in platform_set:
            print(f"Warning: Duplicated platform {platform} found at station {station}.")
        else:
            # print(platform_set)
            platform_set.add(station_platform_pair)
    
    if len(station_names) > 1:
        # Step 4: Check for consistency in left and right x values for the same station
        station_platforms = defaultdict(lambda: {'left_x': set(), 'right_x': set()})
        
        for segment in json_data:
            station = segment.get('station')
            platform = segment.get('platform')
            left_x, _ = segment.get('left', [None, None])
            right_x, _ = segment.get('right', [None, None])
            
            # Collect all left_x and right_x for the given station
            station_platforms[station]['left_x'].add(left_x)
            station_platforms[station]['right_x'].add(right_x)
        
        for station, coordinates in station_platforms.items():
            # If there is more than one unique left_x or right_x for the same station, flag it
            if len(coordinates['left_x']) > 1:
                print(f"Warning: Inconsistent left x-values for station {station}.")
            if len(coordinates['right_x']) > 1:
                print(f"Warning: Inconsistent right x-values for station {station}.")

if __name__ == "__main__":
    # Read the JSON data from the file
    try:
        with open('annotated_segments.json', 'r') as f:
            data = json.load(f)
        
        validate_stations(data)

    except FileNotFoundError:
        print("Error: annotated_segments.json file not found.")
    except json.JSONDecodeError:
        print("Error: Failed to decode JSON. Please check the file format.")
