import tkinter as tk
from tkinter import ttk

# Dummy data for simulation
class DummyTrain:
    def __init__(self):
        self.headcode = "2H01"
        self.game_seconds_at_spawn = 0
        self.timetable = [
            {"station": "Alpha", "platform": "1", "arrival_offset": 1, "departure_offset": 2},
            {"station": "Bravo", "platform": "2", "arrival_offset": 5, "departure_offset": 6},
            {"station": "Charlie", "platform": "3", "arrival_offset": 10, "departure_offset": 12}
        ]

train = DummyTrain()
current_game_seconds = 0  # Simulate current game time

def format_seconds_to_time(seconds):
    mins = seconds // 60
    hrs = mins // 60
    mins = mins % 60
    return f"{int(hrs):02}:{int(mins):02}"

def show_timetable_window(train, current_game_seconds):
    def launch_window():
        window = tk.Tk()
        window.title(f"Timetable - {train.headcode}")
        window.geometry("500x400")

        tree = ttk.Treeview(window, columns=("Station", "Platform", "Arrival", "Departure"), show="headings")
        tree.heading("Station", text="Station")
        tree.heading("Platform", text="Platform")
        tree.heading("Arrival", text="Arrival")
        tree.heading("Departure", text="Departure")

        tree.column("Station", width=150)
        tree.column("Platform", width=100)
        tree.column("Arrival", width=100)
        tree.column("Departure", width=100)

        tree.pack(fill="both", expand=True, padx=10, pady=10)

        stops = train.timetable
        start_time = train.game_seconds_at_spawn

        for stop in stops:
            arr_time = start_time + stop["arrival_offset"] * 60
            dep_time = start_time + stop["departure_offset"] * 60

            if current_game_seconds > dep_time:
                continue  # Skip past stops

            arr_str = format_seconds_to_time(arr_time)
            dep_str = format_seconds_to_time(dep_time)

            tree.insert("", "end", values=(stop["station"], stop["platform"], arr_str, dep_str))

        window.mainloop()

    launch_window()

# Run the window
show_timetable_window(train, current_game_seconds)
