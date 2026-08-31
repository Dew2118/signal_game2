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

MAX_SPAWNS_PER_DAY = 60
MIN_GAP_SECONDS = 86400 // MAX_SPAWNS_PER_DAY  # ~900 seconds (15 minutes)
SAFETY_PADDING = 30 # Seconds to pad before and after a train occupies a tile
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
    chained_targets = set()
    for tt in tt_data:
        for stop in tt.get("stops", []):
            if "change_timetable" in stop:
                chained_targets.add(stop["change_timetable"])

    for tt in tt_data:
        idx = tt.get("index")
        route = next((r for r in ars_routes if r.get("timetable_index") == idx), None)
        if not route or not route.get("paths"):
            continue
            
        sched_stops = route["paths"][0].get("stops", [])
        tt_stops = tt.get("stops", [])
        
        if len(sched_stops) == len(tt_stops):
            for t_stop, s_stop in zip(tt_stops, sched_stops):
                t_stop["arrival_offset"] = s_stop["arrive"]
                t_stop["departure_offset"] = s_stop["depart"]
            print(f" -> Timetable {idx} synced with ARS physical timings.")

    def get_footprint(tt_idx, base_sec, visited=None):
        if visited is None: 
            visited = set()
        if tt_idx in visited: 
            return []
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
                        footprint.append(((cx, cy), base_sec + rel_t - SAFETY_PADDING, base_sec + rel_t + SAFETY_PADDING))
                    except (ValueError, TypeError): 
                        pass
                    
        if tt_entry and tt_entry.get("stops"):
            last_stop = tt_entry["stops"][-1]
            if "change_timetable" in last_stop:
                next_idx = last_stop["change_timetable"]
                dep = last_stop.get("departure_offset", 0)
                footprint.extend(get_footprint(next_idx, base_sec + dep, visited))
                
        return footprint

    # Filter candidate timetables that spawn trains at entrance/exits
    active_candidates = []
    for tt in tt_data:
        idx = tt.get("index")
        if idx in chained_targets:
            tt["spawn_times"] = []
            continue
        start_type = tt.get("start_location", {}).get("type", "")
        if start_type != "entrance_exit":
            print(f" -> Timetable {idx} (Station Spawn): Removing spawn times as requested.")
            tt["spawn_times"] = []
            continue

        footprint = get_footprint(idx, 0)
        active_candidates.append({
            "tt": tt,
            "index": idx,
            "footprint": footprint,
            "pass1_spawns_count": 0
        })

    # =========================================================================
    # PASS 1: Trial schedule generation to measure spawn counts per timetable
    # =========================================================================
    print("\n=== STAGE 2: PASS 1 - MEASURING INITIAL SPAWNS ADDED PER TIMETABLE ===")
    pass1_occupancy = {}

    def is_safe_pass1(spawn_time, footprint):
        for (cx, cy), rel_start, rel_end in footprint:
            my_start = spawn_time + rel_start
            my_end = spawn_time + rel_end
            for occ_start, occ_end in pass1_occupancy.get((cx, cy), []):
                if my_start <= occ_end and my_end >= occ_start:
                    return False
        return True

    def add_to_pass1_occupancy(footprint, abs_spawn_time):
        for (cx, cy), rel_start, rel_end in footprint:
            pass1_occupancy.setdefault((cx, cy), []).append(
                (abs_spawn_time + rel_start, abs_spawn_time + rel_end)
            )

    for item in active_candidates:
        footprint = item["footprint"]
        safe_times = [t for t in range(MIN_SPAWN_SECONDS, 86400, 30) if is_safe_pass1(t, footprint)]
        
        picked = []
        last_s = -99999
        for t in safe_times:
            if t - last_s >= MIN_GAP_SECONDS:
                picked.append(t)
                last_s = t
                if len(picked) >= MAX_SPAWNS_PER_DAY:
                    break

        item["pass1_spawns_count"] = len(picked)
        for sp in picked:
            add_to_pass1_occupancy(footprint, sp)
        print(f" -> Pass 1: Timetable {item['index']} could fit {len(picked)} spawns.")

    # Sort strictly by least number able to be added to the most
    active_candidates.sort(key=lambda item: (item["pass1_spawns_count"], item["index"]))
    print(f"\n -> Pass 2 Ordering (Least to Most): {[item['index'] for item in active_candidates]} with counts {[item['pass1_spawns_count'] for item in active_candidates]}")

    # =========================================================================
    # PASS 2: Re-thread master occupancy starting with the least spawns first
    # =========================================================================
    print("\n=== STAGE 3: PASS 2 - FINAL THREADING IN LEAST-TO-MOST ORDER ===")
    master_occupancy = {}

    def is_safe(spawn_time, footprint):
        for (cx, cy), rel_start, rel_end in footprint:
            my_start = spawn_time + rel_start
            my_end = spawn_time + rel_end
            for occ_start, occ_end in master_occupancy.get((cx, cy), []):
                if my_start <= occ_end and my_end >= occ_start:
                    return False
        return True

    def add_to_occupancy(footprint, abs_spawn_time):
        for (cx, cy), rel_start, rel_end in footprint:
            master_occupancy.setdefault((cx, cy), []).append(
                (abs_spawn_time + rel_start, abs_spawn_time + rel_end)
            )

    total_spawns_added = 0
    spawns_summary = {}

    for item in active_candidates:
        tt = item["tt"]
        idx = item["index"]
        footprint = item["footprint"]
        
        safe_times = [t for t in range(MIN_SPAWN_SECONDS, 86400, 30) if is_safe(t, footprint)]
        
        if not safe_times:
            print(f"    [!] NO SAFE SPAWN TIMES FOUND for Timetable {idx}. Network is congested.")
            tt["spawn_times"] = []
            spawns_summary[idx] = 0
            continue
            
        picked_spawns = []
        last_spawn = -99999
        
        for t in safe_times:
            if t - last_spawn >= MIN_GAP_SECONDS:
                picked_spawns.append(t)
                last_spawn = t
                if len(picked_spawns) >= MAX_SPAWNS_PER_DAY:
                    break
                    
        print(f"    [+] Timetable {idx}: Successfully threaded {len(picked_spawns)} spawn times.")
        
        tt["spawn_times"] = [sec_to_time(s) for s in picked_spawns]
        total_spawns_added += len(picked_spawns)
        spawns_summary[idx] = len(picked_spawns)
        
        for sp in picked_spawns:
            add_to_occupancy(footprint, sp)

    # Save to disk
    output_path.write_text(json.dumps(tt_data, indent=4), encoding="utf-8")
    
    print(f"\n=== SUCCESS! ===")
    print("Final Spawn Summary per Route:")
    for r_idx, count in sorted(spawns_summary.items()):
        print(f"  - Timetable {r_idx}: {count} spawns added")
    print(f"\nTotal spawn times added across all timetables: {total_spawns_added}")
    print(f"Optimized schedule saved to {output_path.name}")

if __name__ == "__main__":
    scenario_name = choose_scenario()
    if scenario_name:
        run_auto_scheduler(scenario_name)
