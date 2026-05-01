import json
import os
import datetime

# Assuming your JSON file is stored at this path
CWD = os.path.dirname(__file__)
JSON_PATH = os.path.join(CWD, "../../../json", "zone_E_timetable.json")

class TimetableProcessor:
    def __init__(self, timetable_file=JSON_PATH):
        # Load the timetables from the provided JSON file
        with open(timetable_file, "r") as f:
            self.timetables = json.load(f)

    def process_timetables(self):
        # Iterate over each timetable entry
        for timetable in self.timetables:
            self.process_single_timetable(timetable)

    def process_single_timetable(self, timetable):
        print(f"Processing timetable for headcode: {timetable['headcode_prefix']}")

        # Loop through every consecutive pair of stops (departure of one and arrival of next)
        for i in range(1, len(timetable['stops'])):
            self.process_stop_pair(timetable, i)

    def process_stop_pair(self, timetable, stop_index):
        # Get the first stop (departure) and second stop (arrival)
        first_stop = timetable['stops'][stop_index - 1]
        second_stop = timetable['stops'][stop_index]

        # Extract times for first and second stop
        departure_time_first = first_stop['departure_offset']
        arrival_time_second = second_stop['arrival_offset']

        # Calculate time difference between departure of first stop and arrival of second stop
        time_difference = arrival_time_second - departure_time_first

        # Calculate time based on distance (for now, using a placeholder function)
        time_based_on_distance = self.calculate_time_based_on_distance(first_stop, second_stop)

        print(f"    - Time Difference: {time_difference} sec")
        print(f"    - Time Based on Distance: {time_based_on_distance} sec")

        # If time based on distance is greater, adjust the times
        if time_based_on_distance > time_difference:
            # Calculate the amount to add
            time_to_add = time_based_on_distance - time_difference
            print(f"    - Adjusting arrival times by {time_to_add} sec")

            # Adjust the arrival time of the second station
            second_stop['arrival_offset'] += time_to_add
            second_stop['departure_offset'] += time_to_add

            # Propagate the adjustment to all subsequent stops
            self.adjust_subsequent_stops(timetable, stop_index, time_to_add)

    def adjust_subsequent_stops(self, timetable, stop_index, time_to_add):
        # Adjust all subsequent stops by adding the time_to_add
        for i in range(stop_index + 1, len(timetable['stops'])):
            stop = timetable['stops'][i]
            stop['arrival_offset'] += time_to_add
            stop['departure_offset'] += time_to_add

    def calculate_time_based_on_distance(self, first_stop, second_stop):
        # Placeholder for your logic to calculate time based on distance
        # For simplicity, let's assume a fixed time of 200 seconds as an example
        # You would replace this with your own calculation logic based on coordinates, speed, etc.
        return 200  # Example fixed time based on distance (replace with actual logic)

    def print_final_timetable(self):
        # Just to see the final processed timetable in a human-readable format
        for timetable in self.timetables:
            print(f"\nHeadcode: {timetable['headcode_prefix']}")
            for stop in timetable['stops']:
                print(f"  - {stop['station']} (Platform: {stop['platform']}) "
                      f"Arrival: {stop['arrival_offset']} sec, Departure: {stop['departure_offset']} sec")

    def save_timetables(self, output_file):
        # Save the modified timetables back to a JSON file, maintaining the structure
        with open(output_file, "w") as f:
            json.dump(self.timetables, f, indent=4)
        print(f"Modified timetables saved to {output_file}")

if __name__ == "__main__":
    # Initialize the TimetableProcessor and run
    processor = TimetableProcessor()
    processor.process_timetables()

    # Optionally print the final processed timetables
    processor.print_final_timetable()

    # Save the modified timetables to a new file
    processor.save_timetables(os.path.join(CWD, "../../../json", "zone_E_timetable_modified.json"))