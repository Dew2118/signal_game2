import json
import os
import sys
import tkinter as tk
from pathlib import Path

# --- Configuration & Pathing ---
PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

JSON_PATH = PROJECT_ROOT / "src" / "json"

MAX_SPAWNS_PER_DAY = 96
MIN_GAP_SECONDS = 86400 // MAX_SPAWNS_PER_DAY  # ~900 seconds (15 minutes)
SAFETY_PADDING = 15 # Seconds to pad before and after a train occupies a tile
MIN_SPAWN_SECONDS = 3 # Train spawn times must be >= 00:00:03 to avoid loading race conditions

def choose_scenario():
    map_files = list(PROJECT_ROOT.glob("*_map.txt"))
    scenarios = [os.path.basename(f).replace("_map.txt", "") for f in map_files]

    selected = {"name": None}

    def choose(event=None):
        selection = listbox.curselection()
        if selection:
            selected["name"] = listbox.get(selection[0])
            root.destroy()

    root = tk.Tk()
    root.title("Select Scenario for Auto-Scheduler")
    root.geometry("400x300") 

    tk.Label(root, text="Choose a scenario:", font=("Arial", 12)).pack(pady=10)

    frame = tk.Frame(root)
    frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
    scrollbar = tk.Scrollbar(frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    listbox = tk.Listbox(frame, yscrollcommand=scrollbar.set, font=("Arial", 11))
    listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.config(command=listbox.yview)

    for scenario in scenarios:
        listbox.insert(tk.END, scenario)

    listbox.bind("<Double-Button-1>", choose)
    listbox.bind("<Return>", choose)
    root.mainloop()

    return selected["name"]

def sec_to_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def time_to_sec(time_str):
    try:
        h, m, s = map(int, time_str.split(":"))
        return h * 3600 + m * 60 + s
    except Exception:
        return 0

def run_auto_scheduler(scenario):
    template_path = JSON_PATH / f"{scenario}_timetable.json"
    output_path = JSON_PATH / f"{scenario}_timetable.json"
    ars_path = JSON_PATH / f"{scenario}_ars_schedule.json"

    if not template_path.exists():
        print(f"Error: Template file {template_path.name} not found!")
        print(f"Please rename your working timetable to {scenario}_timetable1.json first.")
        return

    if not ars_path.exists():
        print(f"Error: ARS Schedule {ars_path.name} not found!")
        return

    tt_data = json.loads(template_path.read_text(encoding="utf-8"))
    ars_data = json.loads(ars_path.read_text(encoding="utf-8"))
    ars_routes = ars_data.get("routes", [])

    print("\n=== STAGE 1: SYNCHRONIZING TIMETABLE OFFSETS ===")
    # Find all timetables that act as chained continuations
    chained_targets = set()
    for tt in tt_data:
        for stop in tt.get("stops", []):
            if "change_timetable" in stop:
                chained_targets.add(stop["change_timetable"])

    # Synchronize the stops in timetable1 with the physical reality of ARS Schedule
    for tt in tt_data:
        idx = tt.get("index")
        route = next((r for r in ars_routes if r.get("timetable_index") == idx), None)
        if not route or not route.get("paths"):
            continue
            
        sched_stops = route["paths"][0].get("stops", [])
        tt_stops = tt.get("stops", [])
        
        # If lengths match, sync the precise physical times
        if len(sched_stops) == len(tt_stops):
            for t_stop, s_stop in zip(tt_stops, sched_stops):
                t_stop["arrival_offset"] = s_stop["arrive"]
                t_stop["departure_offset"] = s_stop["depart"]
            print(f" -> Timetable {idx} synced with ARS physical timings.")

    print("\n=== STAGE 2: BUILDING OCCUPANCY AND THREADING NEEDLE ===")
    master_occupancy = {} # (x,y) -> list of (abs_start, abs_end)

    def get_footprint(tt_idx, base_sec, visited=None):
        if visited is None: visited = set()
        if tt_idx in visited: return []
        visited.add(tt_idx)
        
        footprint = []
        route = next((r for r in ars_routes if r.get("timetable_index") == tt_idx), None)
        tt_entry = next((t for t in tt_data if t.get("index") == tt_idx), None)
        
        if route and route.get("paths"):
            for item in route["paths"][0].get("coords", []):
                if len(item) >= 3:
                    try:
                        cx, cy = int(item[0]), int(item[1])
                        rel_t = float(item[2])
                        # Pad the footprint with the safety window
                        footprint.append( ((cx, cy), base_sec + rel_t - SAFETY_PADDING, base_sec + rel_t + SAFETY_PADDING) )
                    except (ValueError, TypeError): pass
                    
        # Trace chained timetables
        if tt_entry and tt_entry.get("stops"):
            last_stop = tt_entry["stops"][-1]
            if "change_timetable" in last_stop:
                next_idx = last_stop["change_timetable"]
                dep = last_stop.get("departure_offset", 0)
                footprint.extend(get_footprint(next_idx, base_sec + dep, visited))
                
        return footprint

    def add_to_occupancy(footprint, abs_spawn_time):
        for (cx, cy), rel_start, rel_end in footprint:
            master_occupancy.setdefault((cx, cy), []).append(
                (abs_spawn_time + rel_start, abs_spawn_time + rel_end)
            )

    def is_safe(spawn_time, footprint):
        for (cx, cy), rel_start, rel_end in footprint:
            my_start = spawn_time + rel_start
            my_end = spawn_time + rel_end
            for occ_start, occ_end in master_occupancy.get((cx, cy), []):
                if my_start <= occ_end and my_end >= occ_start:
                    return False
        return True

    # Process all timetables
    for tt in tt_data:
        idx = tt.get("index")
        
        # Skip chained routes (they don't spawn independently)
        if idx in chained_targets:
            tt["spawn_times"] = [] # Clear spawns just to be safe
            continue
            
        start_type = tt.get("start_location", {}).get("type", "")
        
        # If the start location is not an entrance/exit, empty the spawns and skip
        if start_type != "entrance_exit":
            print(f" -> Timetable {idx} (Station Spawn): Removing all spawn times as requested.")
            tt["spawn_times"] = []
            continue

        footprint = get_footprint(idx, 0)
        
        print(f" -> Timetable {idx} (Entrance/Exit): Scanning 24h clock to thread {MAX_SPAWNS_PER_DAY} spawns...")
        
        safe_times = []
        
        # Scan every 30 seconds
        for t in range(MIN_SPAWN_SECONDS, 86400, 30):
            if is_safe(t, footprint):
                safe_times.append(t)
                
        if not safe_times:
            print(f"    [!] NO SAFE SPAWN TIMES FOUND for Timetable {idx}. Network is congested.")
            tt["spawn_times"] = []
            continue
            
        # Filter the safe times to spread them out evenly
        picked_spawns = []
        last_spawn = -99999
        
        for t in safe_times:
            # Only pick a time if it respects our MIN_GAP (e.g., 15 mins) from the last train
            if t - last_spawn >= MIN_GAP_SECONDS:
                picked_spawns.append(t)
                last_spawn = t
                if len(picked_spawns) >= MAX_SPAWNS_PER_DAY:
                    break
                    
        print(f"    [+] Successfully threaded {len(picked_spawns)} spawn times (Target: {MAX_SPAWNS_PER_DAY}).")
        
        # Format and apply back to the timetable dictionary
        tt["spawn_times"] = [sec_to_time(s) for s in picked_spawns]
        
        # Claim this footprint on the master map so the next timetable weaves around it!
        for sp in picked_spawns:
            add_to_occupancy(footprint, sp)

    # Save to the final live game file
    output_path.write_text(json.dumps(tt_data, indent=4), encoding="utf-8")
    print(f"\n=== SUCCESS! ===")
    print(f"Optimized schedule saved to {output_path.name}")
    print(f"Your game is now ready to play.")


if __name__ == "__main__":
    scenario_name = choose_scenario()
    if scenario_name:
        run_auto_scheduler(scenario_name)
