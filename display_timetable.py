import tkinter as tk
from tkinter import ttk
class Timetable:
    def __init__(self, train):
        self.window = tk.Tk()
        self.train = train
        self.window.title(f"Timetable - {train.headcode}")
        self.window.geometry("500x400")
        self.tree = ttk.Treeview(self.window, columns=("Station", "Platform", "Arrival", "Departure"), show="headings")
        self.tree_items = []
        self.stops = train.timetable
        self.current_index = getattr(train, "current_stop_index", 0)
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)
        style = ttk.Style(self.window)
        style.configure("Treeview", font=("JetBrain Mono", 10))
        style.configure("Treeview.Heading", font=("JetBrain Mono", 10, "bold"))
        # self.window.resizable(False, False)

    def on_close(self):
        """ Handle window close event """
        print("Window is being closed...")
        self.window.destroy()  # Close the Tkinter window gracefull

    def format_seconds_to_time(self, seconds):
        mins = seconds // 60
        hrs = mins // 60
        mins = mins % 60
        seconds = seconds % 60
        return f"{int(hrs):02}:{int(mins):02}:{int(seconds):02}"

    def show_timetable_window(self):
        self.tree.heading("Station", text="Station")
        self.tree.heading("Platform", text="Platform")
        self.tree.heading("Arrival", text="Arrival")
        self.tree.heading("Departure", text="Departure")

        self.tree.column("Station", width=150)
        self.tree.column("Platform", width=100)
        self.tree.column("Arrival", width=100)
        self.tree.column("Departure", width=100)

        self.tree.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.populate_table()
        self.update_table()
        self.window.update()

    def populate_table(self):
        
        self.tree_items.clear()
        self.tree.delete(*self.tree.get_children())
        for stop in self.stops[self.current_index:]:
            self.tree_items.append(self.tree.insert("", "end", values=("", "", "", "")))
        # self.window.after(1000, self.populate_table)

    def update_table(self):
        start_time = getattr(self.train, "game_seconds_at_spawn", 0)
        print(start_time)
        current_index = getattr(self.train, "current_stop_index", 0)
        for i, stop in enumerate(self.stops[current_index:]):
            arr_time = start_time + stop["arrival_offset"]
            dep_time = start_time + stop["departure_offset"]

            arr_str = self.format_seconds_to_time(arr_time)
            dep_str = self.format_seconds_to_time(dep_time)

            self.tree.item(self.tree_items[i], values=(stop["station"], stop["platform"], arr_str, dep_str))
        self.window.update()

        # self.window.after(1000, self.update_table)
        

    # window.after(1000, update_table)
    # try:
    #     populate_table()
    #     update_table()
    #     window.mainloop()
    # except tk.TclError:
    #     print("Window closed error")