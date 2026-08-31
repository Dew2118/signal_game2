import pygame
import sys
import json
import os
import tkinter as tk
from pathlib import Path

# --- Configuration & Pathing ---
PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

FONT_PATH = PROJECT_ROOT / "src" / "assets" / "fonts" / "S-box.ttf"
JSON_PATH = PROJECT_ROOT / "src" / "json"

# Colors
COL_BG = (17, 17, 17)
COL_SIDEBAR_BG = (29, 29, 29)
COL_TEXT = (240, 240, 240)
COL_GRID = (43, 43, 43)

COL_SIGNAL = (111, 201, 255)
COL_PLATFORM = (107, 211, 139)
COL_ENTRANCE = (200, 100, 255)
COL_SELECTED = (255, 255, 0)
COL_PREV_SELECTED = (180, 180, 100)
COL_REPLACE = (255, 50, 50)
COL_INSERT = (50, 255, 50)
COL_DRAGGING = (80, 160, 255)

# Sequential Path Colors
COL_LINE_SIG_EDIT = (255, 255, 0) 
COL_LINE_STA_EDIT = (255, 150, 0) 
COL_LINE_SIG = (0, 255, 0)        
COL_LINE_STA = (0, 150, 255)      
COL_LINE_SIG_ALT = (50, 120, 50)  
COL_LINE_STA_ALT = (50, 80, 150)  

CELL_SIZE = 16
SIDEBAR_WIDTH = 420

ALL_SIGNALS = {"à", "ã", "â", "á", "ø", "û", "ù", "ú", "©", "¨"}

def load_font(size, bold=False, custom=False):
    if custom and FONT_PATH.exists():
        font = pygame.font.Font(str(FONT_PATH), size)
    else:
        font = pygame.font.Font(None, size)
    font.set_bold(bold)
    return font

def choose_scenario():
    map_files = list(PROJECT_ROOT.glob("*_map.txt"))
    scenarios = [os.path.basename(f).replace("_map.txt", "") for f in map_files]
    selected = {"name": None}

    def choose(event=None):
        selection = listbox.curselection()
        if selection:
            selected["name"] = listbox.get(selection[0])
            root.destroy()

    def update_filter(*args):
        search_term = search_var.get().lower()
        listbox.delete(0, tk.END)
        for scenario in scenarios:
            if search_term in scenario.lower():
                listbox.insert(tk.END, scenario)

    root = tk.Tk()
    root.title("Select Scenario")
    root.geometry("400x400")
    tk.Label(root, text="Choose a scenario:", font=("Arial", 12)).pack(pady=10)
    search_var = tk.StringVar()
    search_var.trace_add("write", update_filter) 
    tk.Entry(root, textvariable=search_var, width=30).pack(pady=5)
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

class TextInput:
    def __init__(self, x, y, w, h, label, default=""):
        self.rect = pygame.Rect(x, y, w, h)
        self.label = label
        self.text = default
        self.active = False
        self.font = pygame.font.Font(None, 24)

    def draw(self, screen):
        color = (100, 100, 150) if self.active else (50, 50, 50)
        pygame.draw.rect(screen, color, self.rect, border_radius=4)
        pygame.draw.rect(screen, (200, 200, 200), self.rect, 2, border_radius=4)
        screen.blit(self.font.render(self.label, True, COL_TEXT), (self.rect.x, self.rect.y - 18))
        display_text = self.text + ("|" if self.active and pygame.time.get_ticks() % 1000 < 500 else "")
        txt_surf = self.font.render(display_text, True, COL_TEXT)
        offset_x = max(0, txt_surf.get_width() - (self.rect.width - 10))
        old_clip = screen.get_clip()
        screen.set_clip(self.rect)
        screen.blit(txt_surf, (self.rect.x + 5 - offset_x, self.rect.y + 5))
        screen.set_clip(old_clip)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.active = self.rect.collidepoint(event.pos)
        elif event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE: self.text = self.text[:-1]
            elif event.unicode and event.unicode.isprintable(): self.text += event.unicode


class UnifiedBuilder:
    def __init__(self, scenario):
        pygame.init()
        pygame.key.set_repeat(200, 50) 
        
        # Made the default starting size smaller. 
        # pygame.RESIZABLE automatically adds the OS maximize button and drag-to-resize.
        self.width, self.height = 1200, 720
        self.screen = pygame.display.set_mode((self.width, self.height), pygame.RESIZABLE)
        pygame.display.set_caption(f"Timetable & ARS Builder - {scenario}")
        self.clock = pygame.time.Clock()
        
        self.scenario = scenario
        self.map_lines = (PROJECT_ROOT / f"{scenario}_map.txt").read_text(encoding="utf-8").splitlines()
        
        self.font_map = load_font(13, bold=True, custom=True)
        self.font_ui = load_font(20)
        self.font_small = load_font(16)
        
        self.camera_x, self.camera_y = 0, 0
        self.panning = False
        self.pan_start = (0, 0)
        self.pan_start_camera = (0, 0)
        self.node_list_scroll_y = 0 
        
        # --- UI Notifications ---
        self.notification_text = ""
        self.notification_timer = 0
        
        # --- UI Elements Layout ---
        self.btn_prev_tt = pygame.Rect(10, 25, 30, 30)
        self.input_load_tt = TextInput(50, 25, 80, 30, "Load TT #", "")
        self.btn_load_tt = pygame.Rect(140, 25, 60, 30)
        self.btn_next_tt = pygame.Rect(210, 25, 30, 30)
        
        self.input_headcode = TextInput(10, 80, 100, 30, "Headcode Prefix", "1A")
        self.direction_val = "right"
        self.btn_direction = pygame.Rect(125, 80, 95, 30)
        self.despawn = False
        self.btn_despawn = pygame.Rect(230, 80, 95, 30)
        
        self.input_change_tt = TextInput(10, 135, 120, 30, "Change TT Index", "")
        self.input_spawns = TextInput(140, 135, 270, 30, "Spawn Times (HH:MM:SS, ...)", "")
        
        self.btn_save_update = pygame.Rect(10, 180, 195, 35)
        self.btn_save_new = pygame.Rect(215, 180, 195, 35)
        self.btn_calculate = pygame.Rect(10, 225, 400, 35)
        
        self.btn_new_path = pygame.Rect(10, 275, 120, 30)
        self.btn_clone_path = pygame.Rect(140, 275, 130, 30)
        self.btn_del_path = pygame.Rect(280, 275, 130, 30)
        
        self.btn_clone_route = pygame.Rect(10, 315, 130, 30)
        self.btn_undo = pygame.Rect(150, 315, 120, 30)
        
        self.btn_insert_node = pygame.Rect(10, 355, 130, 30)
        self.btn_del_node = pygame.Rect(150, 355, 120, 30)
        
        self.undo_stack = []
        self.nodes = {} 
        self._load_map_nodes()
        
        # --- CLEAN DATA STRUCTURE ---
        self.station_path: list = []             
        self.signal_paths: list[list] = [[]]     
        self.active_signal_path_idx: int = 0
        
        self.active_mode = "timetable" # "timetable" or "signal"
        self.prev_path_idx = -1 
        self.replace_idx = -1 
        self.insert_idx = -1 
        self.dragging_tab_idx = -1 

        # --- Drag-and-Drop Node List State ---
        self.dragging_node_idx = -1

        # --- Platform Selection Menu State ---
        self.platform_menu = {"active": False, "options": [], "rects": [], "station_name": ""}
        
        self.available_tt_indices = []
        self._refresh_available_tts()

    def show_notification(self, text, duration_frames=180):
        self.notification_text = str(text)
        self.notification_timer = duration_frames
        print(f"[UI NOTIFY]: {text}")

    def _get_display_path(self):
        """Returns ONLY the list corresponding to the currently active tab."""
        if self.active_mode == "timetable":
            return self.station_path
        else:
            if self.active_signal_path_idx < len(self.signal_paths):
                return self.signal_paths[self.active_signal_path_idx]
            return []

    def _find_node_by_station(self, station_name, platform_name):
        for coord, data in self.nodes.items():
            if data.get("station") == station_name and data.get("platform") == platform_name: return dict(data)
        if platform_name == "" or platform_name is None:
            for coord, data in self.nodes.items():
                if data.get("station") == station_name: return dict(data)
        return None

    def _activate_platform_menu(self, station_name, position, is_start_location=False):
        platforms = sorted({n['platform'] for n in self.nodes.values() if n.get('station') == station_name and n.get('platform')})
        if len(platforms) > 0:
            # For start location (index 0), 'Any Platform' is strictly NOT allowed.
            options = []
            if not is_start_location:
                options.append(("Any Platform", ""))
            options.extend([(f"Platform {p}" if p else "Unnamed", p) for p in platforms])

            self.platform_menu.update({
                'active': True,
                'station_name': station_name,
                'options': options,
                'rects': []
            })
            x, y = position
            for i, (text, _) in enumerate(self.platform_menu['options']):
                self.platform_menu['rects'].append(pygame.Rect(x + 10, y + 10 + i * 25, 150, 25))
            return True
        return False

    def save_state(self):
        self.undo_stack.append({
            "station_path": [dict(node) for node in self.station_path],
            "signal_paths": [[dict(node) for node in path] for path in self.signal_paths],
            "active_signal_path_idx": getattr(self, "active_signal_path_idx", 0)
        })
        if len(self.undo_stack) > 50: self.undo_stack.pop(0)

    def undo(self):
        if self.undo_stack:
            last_state = self.undo_stack.pop()
            self.station_path = last_state.get("station_path", [])
            self.signal_paths = last_state.get("signal_paths", [[]])
            self.active_signal_path_idx = last_state.get("active_signal_path_idx", 0)
            self.replace_idx, self.insert_idx = -1, -1
            self.dragging_node_idx = -1
            self.show_notification("Undo successful.", 90)

    def load_new_timetable_workspace(self):
        self.save_state()
        self.station_path, self.signal_paths = [], [[]]
        self.active_signal_path_idx, self.active_mode = 0, "timetable"
        self.prev_path_idx, self.replace_idx, self.insert_idx = -1, -1, -1
        self.dragging_node_idx = -1
        self.input_headcode.text, self.direction_val, self.input_spawns.text, self.input_change_tt.text = "", "right", "", ""
        self.despawn = False
        self.show_notification("Loaded a NEW blank workspace.", 120)

    def _load_map_nodes(self):
        for y, line in enumerate(self.map_lines):
            for x, char in enumerate(line):
                if char in ALL_SIGNALS: 
                    self.nodes[(x, y)] = {"type": "signal", "coord": (x, y), "char": char}
                elif char == "q":
                    # Check via criteria
                    left_is_space = (x > 0 and line[x-1] == " ") or (x == 0)
                    right_is_space = (x + 1 < len(line) and line[x+1] == " ") or (x + 1 >= len(line))
                    below_is_track = (y + 1 < len(self.map_lines) and x < len(self.map_lines[y+1]) and self.map_lines[y+1][x] == "a")
                    if left_is_space and right_is_space and below_is_track:
                        self.nodes[(x, y)] = {
                            "type": "via", 
                            "coord": (x, y), 
                            "track_coord": (x, y + 1),
                            "char": "q"
                        }

        anno_path = JSON_PATH / f"{self.scenario}_annotated_segments.json"
        if anno_path.exists():
            data = json.loads(anno_path.read_text(encoding="utf-8"))
            for seg in data.get("segments", []):
                seg_type = "entrance_exit" if seg.get("left") == seg.get("right") else "platform"
                for key in ["left", "right", "start", "end"]:
                    if key in seg:
                        cx, cy = seg[key][0], seg[key][1]
                        self.nodes[(cx, cy)] = {"type": seg_type, "station": seg.get("station", "Unknown"), "platform": seg.get("platform", ""), "coord": (cx, cy)}

    def _refresh_available_tts(self):
        timetable_path = JSON_PATH / f"{self.scenario}_timetable.json"
        self.available_tt_indices = []
        if timetable_path.exists():
            try: self.available_tt_indices = sorted([t.get("index", 0) for t in json.loads(timetable_path.read_text(encoding="utf-8")) if "index" in t])
            except Exception: pass

    def _navigate_tt(self, direction):
        self._refresh_available_tts()
        seq = self.available_tt_indices + ["NEW"]
        curr_val = int(self.input_load_tt.text.strip()) if self.input_load_tt.text.strip().isdigit() else "NEW"
        new_val = seq[(seq.index(curr_val) + direction) % len(seq)] if curr_val in seq else (seq[0] if direction > 0 else seq[-1])
        self.input_load_tt.text = str(new_val)
        self.load_new_timetable_workspace() if new_val == "NEW" else self.load_existing_timetable()

    def _screen_to_grid(self, pos):
        return (pos[0] - SIDEBAR_WIDTH + self.camera_x) // CELL_SIZE, (pos[1] + self.camera_y) // CELL_SIZE

    def _clamp_camera(self):
        map_w, map_h = max((len(line) for line in self.map_lines), default=0) * CELL_SIZE, len(self.map_lines) * CELL_SIZE
        self.camera_x = min(max(0, self.camera_x), max(0, map_w - (self.width - SIDEBAR_WIDTH)))
        self.camera_y = min(max(0, self.camera_y), max(0, map_h - self.height))

    def load_existing_timetable(self):
        idx_str = self.input_load_tt.text.strip()
        if idx_str == "NEW": return self.load_new_timetable_workspace()
        if not idx_str.isdigit(): 
            self.show_notification("Error: Invalid Timetable Index to load.")
            return
        
        tt_idx = int(idx_str)
        timetable_path, ars_path = JSON_PATH / f"{self.scenario}_timetable.json", JSON_PATH / f"{self.scenario}_ars_routes.json"
        if not timetable_path.exists(): 
            self.show_notification("Error: Timetable file not found.")
            return
        
        try:
            tt_data = json.loads(timetable_path.read_text(encoding="utf-8"))
            ars_data = json.loads(ars_path.read_text(encoding="utf-8")) if ars_path.exists() else {}
            ars_data = ars_data.get("routes", []) if isinstance(ars_data, dict) else ars_data
        except json.JSONDecodeError: return
            
        tt_entry = next((t for t in tt_data if t.get("index") == tt_idx), None)
        if not tt_entry: 
            self.show_notification(f"Error: Timetable {tt_idx} not found.")
            return
        ars_entry = next((r for r in ars_data if r.get("timetable_index") == tt_idx), None)

        self.save_state()
        self.station_path = []
        start_loc = tt_entry.get("start_location", {})
        if start_node := self._find_node_by_station(start_loc.get("station"), start_loc.get("platform")):
            start_copy = dict(start_node)
            start_copy["platform"] = start_loc.get("platform", "")
            self.station_path.append(start_copy)

        for stop_entry in tt_entry.get("stops", []):
            if stop_entry.get("type") == "signal": continue
            if node := self._find_node_by_station(stop_entry.get("station"), stop_entry.get("platform")):
                node_copy = dict(node)
                node_copy["platform"] = stop_entry.get("platform", "")
                if stop_entry.get("reverse_direction"): node_copy["change_dir"] = True
                
                if not (len(self.station_path) == 1 and self.station_path[0]["coord"] == node_copy["coord"]):
                    self.station_path.append(node_copy)

        self.signal_paths = [[]]
        if ars_entry and ars_entry.get("signal_paths"):
            self.signal_paths = [[dict(self.nodes[tuple(s)]) for s in p if tuple(s) in self.nodes] for p in ars_entry["signal_paths"]]

        self.input_headcode.text, self.direction_val = tt_entry.get("headcode_prefix", ""), tt_entry.get("direction", "right")
        self.input_spawns.text = ", ".join(tt_entry.get("spawn_times", []))
        self.despawn, self.input_change_tt.text = False, ""
        if stops := tt_entry.get("stops", []):
            if "despawn" in stops[-1]: self.despawn = True
            elif "change_timetable" in stops[-1]: self.input_change_tt.text = str(stops[-1]["change_timetable"])

        self.active_signal_path_idx, self.active_mode = 0, "timetable"
        self.prev_path_idx, self.replace_idx, self.insert_idx, self.node_list_scroll_y = -1, -1, -1, 0
        self.dragging_node_idx = -1
        self.show_notification(f"Successfully loaded Timetable {tt_idx}.")

    def save_unified_data(self, is_new=False):
        if len(self.station_path) < 1 and len(self.signal_paths[0]) < 1: 
            self.show_notification("Error: Timetable must have a start location.")
            return

        start_node = self.station_path[0] if self.station_path else self.signal_paths[0][0]
        
        # --- 1. VALIDATE START LOCATION ---
        start_station = start_node.get("station", "")
        start_platform = str(start_node.get("platform", "")).strip()
        start_type = "entrance_exit" if start_node["type"] == "entrance_exit" else "platform"

        if start_type == "platform" and not start_platform:
            self.show_notification("Error: Start Location MUST have a specific platform (Any Platform is invalid)!")
            return

        anno_path = JSON_PATH / f"{self.scenario}_annotated_segments.json"
        valid_start = False
        all_segments = []
        if anno_path.exists():
            data = json.loads(anno_path.read_text(encoding="utf-8"))
            all_segments = data.get("segments", [])
            for seg in all_segments:
                if seg.get("type") == start_type and seg.get("station") == start_station:
                    if start_type == "entrance_exit":
                        valid_start = True
                        break
                    elif str(seg.get("platform", "")).strip() == start_platform:
                        valid_start = True
                        break

        if not valid_start:
            self.show_notification(f"Error: Start Location '{start_station} P{start_platform}' not found in annotated segments!")
            return

        change_tt_text = self.input_change_tt.text.strip()
        if not self.despawn and not change_tt_text: 
            self.show_notification("Error: Final stop must Despawn or Change TT!")
            return

        start_location = {
            "type": start_type, 
            "station": start_station, 
            "platform": start_platform
        }
        
        # --- 2. BUILD RAW STOPS LIST (station_path[1:]) ---
        stops = []
        for i in range(1, len(self.station_path)):
            node = self.station_path[i]
            stop_entry = {
                "station": node.get("station", ""), 
                "platform": node.get("platform", ""), 
                "arrival_offset": 0,
                "departure_offset": 30
            }
            if node.get("change_dir"): 
                stop_entry["change_direction"] = True
            if node.get("type") == "signal": 
                stop_entry.update({"type": "signal", "coord": node["coord"]})
            stops.append(stop_entry)

        if stops:
            if self.despawn: 
                stops[-1]["despawn"] = True
            elif change_tt_text.isdigit(): 
                stops[-1]["change_timetable"] = int(change_tt_text)
            
        # Determine Timetable Index
        timetable_path = JSON_PATH / f"{self.scenario}_timetable.json"
        tt_data = []
        if timetable_path.exists():
            try: 
                tt_data = json.loads(timetable_path.read_text(encoding="utf-8"))
            except Exception: 
                pass
            
        loaded_idx = self.input_load_tt.text.strip()
        new_index = max([t.get("index", 0) for t in tt_data], default=0) + 1 if is_new or not loaded_idx.isdigit() else int(loaded_idx)

        # --- 3. SAVE ARS ROUTES JSON ---
        ars_path = JSON_PATH / f"{self.scenario}_ars_routes.json"
        ars_data = []
        if ars_path.exists():
            try:
                raw = json.loads(ars_path.read_text(encoding="utf-8"))
                ars_data = raw.get("routes", []) if isinstance(raw, dict) else raw
            except Exception: 
                pass

        if not is_new and loaded_idx.isdigit(): 
            ars_data = [r for r in ars_data if r.get("timetable_index") != new_index]
        
        valid_signal_paths = [[[n['coord'][0], n['coord'][1]] for n in p] for p in self.signal_paths if p]
        new_ars = {
            "name": str(new_index), 
            "timetable_index": new_index, 
            "signal_paths": valid_signal_paths
        }
        if valid_signal_paths and valid_signal_paths[0]: 
            new_ars["signals"] = valid_signal_paths[0]
        ars_data.append(new_ars)
        ars_data.sort(key=lambda x: x.get("timetable_index", 999))

        try: 
            ars_path.write_text(json.dumps({"routes": ars_data}, indent=4), encoding="utf-8")
        except Exception as e: 
            self.show_notification(f"CRITICAL ERROR saving ARS routes: {e}")
            return

        # --- 4. COMPUTE EXACT FORWARD TIMINGS (START LOCATION -> STOPS) ---
        # Resolve start location physical spawn coordinate
        start_coord = None
        for seg in all_segments:
            if seg.get("type") == start_type and seg.get("station") == start_station:
                if start_type == "entrance_exit":
                    start_coord = tuple(seg.get("right", seg.get("left", (0, 0)))) if self.direction_val == "right" else tuple(seg.get("left", seg.get("right", (0, 0))))
                    break
                elif str(seg.get("platform", "")).strip() == start_platform:
                    start_coord = tuple(seg.get("right", seg.get("left", (0, 0)))) if self.direction_val == "right" else tuple(seg.get("left", seg.get("right", (0, 0))))
                    break

        if start_coord is None and self.station_path:
            start_coord = tuple(self.station_path[0]["coord"])

        # Physical simulation forward from start_location
        # If multiple signal paths are present, evaluate forward timings across each path and take max
        paths_to_evaluate = self.signal_paths if (self.signal_paths and any(p for p in self.signal_paths)) else [[{"coord": n["coord"]} for n in self.station_path]]
        
        for stop_idx, stop_entry in enumerate(stops):
            target_station_node = self.station_path[stop_idx + 1] # Corresponding stop node
            target_coord = tuple(target_station_node["coord"])
            
            max_arr_for_stop = 0
            max_dep_for_stop = 0

            for sig_path in paths_to_evaluate:
                curr_t = 0
                curr_pos = start_coord
                
                # Walk through any intermediate signals/vias in this path that precede or lead to this stop
                # and through previous stops
                for prev_s_idx in range(1, stop_idx + 1):
                    prev_node = self.station_path[prev_s_idx]
                    prev_coord = tuple(prev_node["coord"])
                    curr_t += abs(prev_coord[0] - curr_pos[0]) + abs(prev_coord[1] - curr_pos[1])
                    curr_t += 30 # Dwell at intermediate stop
                    curr_pos = prev_coord
                
                # Travel from last stop/signal position to this target stop
                curr_t += abs(target_coord[0] - curr_pos[0]) + abs(target_coord[1] - curr_pos[1])
                arr_time = curr_t
                dep_time = curr_t + 30

                max_arr_for_stop = max(max_arr_for_stop, arr_time)
                max_dep_for_stop = max(max_dep_for_stop, dep_time)

            stop_entry["arrival_offset"] = max_arr_for_stop
            stop_entry["departure_offset"] = max_dep_for_stop

        # --- 5. WRITE TIMETABLE JSON ---
        tt_data = [t for t in tt_data if t.get("index") != new_index]
        tt_data.append({
            "index": new_index, 
            "headcode_prefix": self.input_headcode.text.strip().upper(), 
            "start_location": start_location, 
            "direction": self.direction_val, 
            "stops": stops, 
            "spawn_times": [t.strip() for t in self.input_spawns.text.split(",") if t.strip()]
        })
        tt_data.sort(key=lambda x: x.get("index", 999))

        try: 
            timetable_path.write_text(json.dumps(tt_data, indent=4), encoding="utf-8")
        except Exception as e: 
            self.show_notification(f"CRITICAL ERROR saving Timetable: {e}")
            return
            
        self.input_load_tt.text = str(new_index)
        self._refresh_available_tts()
        self.show_notification(f"SUCCESS! Timetable and ARS {new_index} saved (forward timings synced).")

    def run_needle_threader(self):
        self.show_notification("Needle Threader Logic not currently implemented.")

    def draw(self):
        self.screen.fill(COL_BG)
        map_rect = pygame.Rect(SIDEBAR_WIDTH, 0, self.width - SIDEBAR_WIDTH, self.height)
        self.screen.set_clip(map_rect)

        active_display_path = self._get_display_path()
        insert_node = active_display_path[self.insert_idx] if 0 <= self.insert_idx < len(active_display_path) else None
        replace_node = active_display_path[self.replace_idx] if 0 <= self.replace_idx < len(active_display_path) else None

        for y, line in enumerate(self.map_lines):
            for x, char in enumerate(line):
                if char == " ": continue
                
                screen_x = SIDEBAR_WIDTH + x * CELL_SIZE - self.camera_x
                screen_y = y * CELL_SIZE - self.camera_y
                if not (map_rect.left - CELL_SIZE < screen_x < map_rect.right and -CELL_SIZE < screen_y < map_rect.bottom):
                    continue
                
                rect = pygame.Rect(screen_x, screen_y, CELL_SIZE, CELL_SIZE)
                bg_color = COL_GRID

                if (x, y) in self.nodes:
                    node = self.nodes[(x, y)]
                    if node.get("type") == "signal": 
                        bg_color = COL_SIGNAL
                    elif node.get("type") == "platform": 
                        bg_color = COL_PLATFORM
                    elif node.get("type") == "entrance_exit": 
                        bg_color = COL_ENTRANCE
                    elif node.get("type") == "via":
                        bg_color = (255, 180, 50)

                    # Highlight stations open in platform menu
                    if self.platform_menu['active'] and self.platform_menu['station_name'] == node.get("station"):
                        bg_color = COL_SELECTED
                    
                    # Highlight nodes in active tab's path
                    if self.active_mode == "timetable" and any(n["coord"] == (x, y) for n in self.station_path):
                        bg_color = COL_SELECTED
                    elif self.active_mode == "signal" and self.active_signal_path_idx < len(self.signal_paths) and any(n["coord"] == (x, y) for n in self.signal_paths[self.active_signal_path_idx]):
                        bg_color = COL_SELECTED

                # Highlight Insert / Replace targets
                if insert_node and insert_node["coord"] == (x, y): 
                    bg_color = COL_INSERT
                elif replace_node and replace_node["coord"] == (x, y): 
                    bg_color = COL_REPLACE
                    
                pygame.draw.rect(self.screen, bg_color, rect)
                pygame.draw.rect(self.screen, (20, 20, 20), rect, 1)

                glyph_color = (0,0,0) if bg_color != COL_GRID else COL_TEXT
                glyph = self.font_map.render(char, True, glyph_color)
                self.screen.blit(glyph, glyph.get_rect(center=rect.center))

        def draw_path_lines(nodes, col, width):
            if len(nodes) < 2: return
            points = [(SIDEBAR_WIDTH + n["coord"][0]*CELL_SIZE - self.camera_x + CELL_SIZE//2, n["coord"][1]*CELL_SIZE - self.camera_y + CELL_SIZE//2) for n in nodes]
            pygame.draw.lines(self.screen, col, False, points, width)

        draw_path_lines(self.station_path, COL_LINE_STA, 3)
        for i, s_path in enumerate(self.signal_paths): 
            draw_path_lines(s_path, COL_LINE_SIG_EDIT if i == self.active_signal_path_idx else COL_LINE_SIG_ALT, 4 if i == self.active_signal_path_idx else 2)

        self.screen.set_clip(None)
        
        # --- Draw Popup Menu (if active) ---
        if self.platform_menu['active']:
            for i, (text, _) in enumerate(self.platform_menu['options']):
                rect = self.platform_menu['rects'][i]
                pygame.draw.rect(self.screen, (50, 50, 70), rect)
                pygame.draw.rect(self.screen, (150, 150, 200), rect, 1)
                self.screen.blit(self.font_small.render(text, True, COL_TEXT), (rect.x + 5, rect.y + 5))
        
        # --- Sidebar Base ---
        pygame.draw.rect(self.screen, COL_SIDEBAR_BG, (0, 0, SIDEBAR_WIDTH, self.height))
        
        pygame.draw.rect(self.screen, (100, 100, 100), self.btn_prev_tt, border_radius=4)
        self.screen.blit(self.font_ui.render("<", True, COL_TEXT), (self.btn_prev_tt.x+8, self.btn_prev_tt.y+5))
        self.input_load_tt.draw(self.screen)
        pygame.draw.rect(self.screen, (100, 150, 100), self.btn_load_tt, border_radius=4)
        self.screen.blit(self.font_small.render("LOAD", True, (0,0,0)), (self.btn_load_tt.x + 10, self.btn_load_tt.y + 8))
        pygame.draw.rect(self.screen, (100, 100, 100), self.btn_next_tt, border_radius=4)
        self.screen.blit(self.font_ui.render(">", True, COL_TEXT), (self.btn_next_tt.x+8, self.btn_next_tt.y+5))

        self.input_headcode.draw(self.screen)
        dir_color = (80, 150, 80) if self.direction_val == "right" else (200, 100, 100)
        pygame.draw.rect(self.screen, dir_color, self.btn_direction, border_radius=4)
        pygame.draw.rect(self.screen, (200, 200, 200), self.btn_direction, 2, border_radius=4)
        self.screen.blit(self.font_ui.render("Direction", True, COL_TEXT), (self.btn_direction.x, self.btn_direction.y - 20))
        self.screen.blit(self.font_ui.render(f"{self.direction_val.title()}", True, (255,255,255)), (self.btn_direction.x + 20, self.btn_direction.y + 5))

        d_color = COL_PLATFORM if self.despawn else (60,60,60)
        pygame.draw.rect(self.screen, d_color, self.btn_despawn, border_radius=4)
        self.screen.blit(self.font_ui.render("Despawn", True, (0,0,0) if self.despawn else COL_TEXT), (self.btn_despawn.x + 10, self.btn_despawn.y + 5))
        
        self.input_change_tt.draw(self.screen)
        self.input_spawns.draw(self.screen)
        
        pygame.draw.rect(self.screen, (255, 165, 0), self.btn_save_update, border_radius=4)
        self.screen.blit(self.font_ui.render("UPDATE Existing TT", True, (0,0,0)), (self.btn_save_update.x + 8, self.btn_save_update.y + 8))
        pygame.draw.rect(self.screen, COL_PLATFORM, self.btn_save_new, border_radius=4)
        self.screen.blit(self.font_ui.render("SAVE AS NEW TT", True, (0,0,0)), (self.btn_save_new.x + 15, self.btn_save_new.y + 8))
        
        pygame.draw.rect(self.screen, (100, 200, 100), self.btn_new_path, border_radius=4)
        self.screen.blit(self.font_small.render("+ New Path", True, (0,0,0)), (self.btn_new_path.x + 15, self.btn_new_path.y + 8))
        pygame.draw.rect(self.screen, (100, 150, 255), self.btn_clone_path, border_radius=4)
        self.screen.blit(self.font_small.render("++ Clone Path (C)", True, (0,0,0)), (self.btn_clone_path.x + 10, self.btn_clone_path.y + 8))
        pygame.draw.rect(self.screen, (200, 100, 100), self.btn_del_path, border_radius=4)
        self.screen.blit(self.font_small.render("- Delete Path", True, (0,0,0)), (self.btn_del_path.x + 15, self.btn_del_path.y + 8))
        pygame.draw.rect(self.screen, (100, 150, 255), self.btn_clone_route, border_radius=4)
        self.screen.blit(self.font_small.render("Clone to New TT", True, (0,0,0)), (self.btn_clone_route.x + 10, self.btn_clone_route.y + 8))
        pygame.draw.rect(self.screen, (200, 200, 100), self.btn_undo, border_radius=4)
        self.screen.blit(self.font_small.render("Undo (Ctrl+Z)", True, (0,0,0)), (self.btn_undo.x + 15, self.btn_undo.y + 8))
        pygame.draw.rect(self.screen, COL_INSERT, self.btn_insert_node, border_radius=4)
        self.screen.blit(self.font_small.render("+ Insert Node", True, (0,0,0)), (self.btn_insert_node.x + 15, self.btn_insert_node.y + 8))
        pygame.draw.rect(self.screen, (255, 100, 100), self.btn_del_node, border_radius=4)
        self.screen.blit(self.font_small.render("- Del Node", True, (0,0,0)), (self.btn_del_node.x + 20, self.btn_del_node.y + 8))

        # --- Tabs ---
        y_off, tab_x, self.tab_rects = 395, 10, []
        
        tt_color = (100, 100, 100)
        if self.active_mode == "timetable": 
            tt_color = COL_SELECTED 
        elif self.prev_path_idx == "timetable": 
            tt_color = COL_PREV_SELECTED
        
        tt_rect = pygame.Rect(tab_x, y_off, 90, 25)
        pygame.draw.rect(self.screen, tt_color, tt_rect, border_radius=4)
        self.screen.blit(self.font_small.render("Timetable", True, (0,0,0)), (tt_rect.x + 5, tt_rect.y + 5))
        self.tab_rects.append((tt_rect, "timetable"))
        tab_x += 95

        for i in range(len(self.signal_paths)):
            color = (100, 100, 100)
            if self.active_mode == "signal" and i == self.active_signal_path_idx: 
                color = COL_SELECTED
            elif self.prev_path_idx == i: 
                color = COL_PREV_SELECTED
            
            rect = pygame.Rect(tab_x, y_off, 90, 25)
            pygame.draw.rect(self.screen, color, rect, border_radius=4)
            self.screen.blit(self.font_small.render(f"Path {i}" + ("(Prim)" if i == 0 else ""), True, (0,0,0)), (rect.x + 5, rect.y + 5))
            self.tab_rects.append((rect, i))
            tab_x += 95
            if tab_x > 320: 
                tab_x, y_off = 10, y_off + 30

        y_off += 35
        self.screen.blit(self.font_small.render("Select Node on Map/List to Replace. Map: Ctrl = Delete", True, (150,150,150)), (10, y_off))
        self.screen.blit(self.font_small.render("Right-Click List Node = Toggle Reverse Direction [REV]", True, (150,150,150)), (10, y_off + 20))
        
        # --- Node List Section ---
        y_off += 40
        self.node_list_rects = [] 
        list_label = "Timetable Sequence:" if self.active_mode == "timetable" else f"Signal Path {self.active_signal_path_idx} Sequence:"
        self.screen.blit(self.font_ui.render(list_label, True, COL_TEXT), (10, y_off))
        y_off += 25
        
        list_clip_rect = pygame.Rect(0, y_off, SIDEBAR_WIDTH, self.height - y_off)
        self.screen.set_clip(list_clip_rect)
        current_y = y_off - self.node_list_scroll_y
        
        for i, node in enumerate(active_display_path):
            rect = pygame.Rect(10, current_y, 390, 24)
            if i == self.dragging_node_idx:
                pygame.draw.rect(self.screen, (40, 60, 90), rect, border_radius=3)
                pygame.draw.rect(self.screen, (80, 160, 255), rect, 1, border_radius=3)

            is_start_location = (self.active_mode == "timetable" and i == 0)

            if node["type"] == "signal": 
                txt = f"{i+1}. Signal: {node['coord']}"
            elif node["type"] == "via":
                txt = f"{i+1}. Via Button: {node['coord']}"
            else:
                plat_str = str(node.get('platform', ''))
                display_plat = f"P{plat_str}" if len(plat_str) == 1 and plat_str.isdigit() else ("[Any Platform]" if plat_str == "" else plat_str.title())
                
                if is_start_location:
                    txt = f"★ [START] {node['type'].title().replace('_', ' ')}: {node['station']} {display_plat}"
                else:
                    txt = f"{i}. Stop: {node['station']} {display_plat}"

            if node.get("change_dir"): 
                txt += " [REV]"
            
            # Text is white by default; turns RED only when actively selected for replacement
            if i == self.replace_idx:
                color = COL_REPLACE  # Red (255, 50, 50)
            elif i == self.insert_idx:
                color = COL_INSERT   # Green (50, 255, 50)
            elif i == self.dragging_node_idx:
                color = (80, 160, 255)
            else:
                color = COL_TEXT     # White (240, 240, 240)

            lbl = self.font_ui.render(txt, True, color)
            self.screen.blit(lbl, (10, current_y))
            self.node_list_rects.append((rect, i))
            current_y += 26

            if is_start_location:
                pygame.draw.line(self.screen, (70, 70, 90), (10, current_y - 2), (380, current_y - 2), 1)
                current_y += 4
            
        self.screen.set_clip(None)
        
        # --- UI Notification Banner ---
        if getattr(self, "notification_timer", 0) > 0:
            notif_surf = self.font_ui.render(self.notification_text, True, (255, 255, 255))
            center_x = SIDEBAR_WIDTH + (self.width - SIDEBAR_WIDTH) // 2
            notif_rect = notif_surf.get_rect(center=(center_x, 40))
            
            bg_box = notif_rect.inflate(40, 16)
            is_success = "SUCCESS" in self.notification_text.upper()
            bg_col = (25, 130, 45) if is_success else (160, 35, 35)
            border_col = (100, 255, 120) if is_success else (255, 100, 100)
            
            shadow_rect = bg_box.copy()
            shadow_rect.y += 3
            pygame.draw.rect(self.screen, (20, 20, 20), shadow_rect, border_radius=6)
            pygame.draw.rect(self.screen, bg_col, bg_box, border_radius=6)
            pygame.draw.rect(self.screen, border_col, bg_box, 2, border_radius=6)
            self.screen.blit(notif_surf, notif_rect)
            self.notification_timer -= 1
            
        pygame.display.flip()

    def run(self):
        running = True
        while running:
            active_display_path = self._get_display_path()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                
                elif event.type == pygame.VIDEORESIZE:
                    self.width, self.height = event.w, event.h
                    self.screen = pygame.display.set_mode((self.width, self.height), pygame.RESIZABLE)
                    self._clamp_camera()
                    
                elif event.type == pygame.KEYDOWN:
                    inputs_active = any([self.input_load_tt.active, self.input_headcode.active, self.input_change_tt.active, self.input_spawns.active])
                    if event.key == pygame.K_z and (pygame.key.get_mods() & pygame.KMOD_CTRL) and not inputs_active:
                        self.undo()
                    elif not inputs_active:
                        if event.key == pygame.K_i:
                            if self.replace_idx != -1:
                                self.insert_idx = self.replace_idx
                                self.replace_idx = -1
                        elif event.key == pygame.K_c:  # HOTKEY: Clone Path
                            self.save_state() 
                            self.prev_path_idx = self.active_signal_path_idx if self.active_mode == "signal" else "timetable"
                            self.signal_paths.append([dict(n) for n in self.signal_paths[self.active_signal_path_idx]])
                            self.active_mode = "signal"
                            self.active_signal_path_idx = len(self.signal_paths) - 1
                            self.replace_idx, self.insert_idx, self.node_list_scroll_y = -1, -1, 0
                            self.show_notification(f"Cloned to Path {self.active_signal_path_idx}", 90)
                        elif event.key == pygame.K_DELETE:
                            self.save_state()
                            idx_to_del = self.replace_idx if self.replace_idx != -1 else self.insert_idx if self.insert_idx != -1 else -1
                            if idx_to_del != -1 and 0 <= idx_to_del < len(active_display_path):
                                node_to_delete = active_display_path[idx_to_del]
                                if node_to_delete['type'] in ('signal', 'via'):
                                    self.signal_paths[self.active_signal_path_idx] = [n for n in self.signal_paths[self.active_signal_path_idx] if n['coord'] != node_to_delete['coord']]
                                else:
                                    self.station_path = [n for n in self.station_path if n['coord'] != node_to_delete['coord']]
                                self.replace_idx, self.insert_idx = -1, -1
                
                for inp in [self.input_load_tt, self.input_headcode, self.input_change_tt, self.input_spawns]:
                    inp.handle_event(event)
                
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button in (4, 5): 
                        scroll_val = -30 if event.button == 4 else 30
                        if event.pos[0] <= SIDEBAR_WIDTH: 
                            self.node_list_scroll_y = max(0, min(max(0, len(active_display_path) * 25), self.node_list_scroll_y + scroll_val))
                        else:
                            scroll_cam = -60 if event.button == 4 else 60
                            if pygame.key.get_mods() & pygame.KMOD_SHIFT: self.camera_y += scroll_cam
                            else: self.camera_x += scroll_cam
                            self._clamp_camera()
                    
                    elif event.pos[0] > SIDEBAR_WIDTH: 
                        if event.button == 3:
                            self.panning, self.pan_start, self.pan_start_camera = True, event.pos, (self.camera_x, self.camera_y)
                        elif event.button == 1:
                            # --- PLATFORM POPUP SELECTION HANDLING ---
                            if self.platform_menu['active']:
                                menu_clicked = False
                                for i, rect in enumerate(self.platform_menu['rects']):
                                    if rect.collidepoint(event.pos):
                                        _, platform = self.platform_menu['options'][i]
                                        if node_to_add := self._find_node_by_station(self.platform_menu['station_name'], platform):
                                            self.save_state()
                                            node_copy = dict(node_to_add)
                                            node_copy["platform"] = platform
                                            
                                            # Apply Replace / Insert Logic
                                            if self.replace_idx != -1 and 0 <= self.replace_idx < len(self.station_path):
                                                self.station_path[self.replace_idx] = node_copy
                                                self.replace_idx = -1
                                            elif self.insert_idx != -1 and 0 <= self.insert_idx < len(self.station_path):
                                                self.station_path.insert(self.insert_idx + 1, node_copy)
                                                self.insert_idx += 1
                                            else:
                                                self.station_path.append(node_copy)
                                        menu_clicked = True
                                        self.platform_menu['active'] = False
                                        break
                                if not menu_clicked: 
                                    self.platform_menu['active'] = False
                                continue

                            gx, gy = self._screen_to_grid(event.pos)
                            if (gx, gy) in self.nodes:
                                node_clicked, mods = self.nodes[(gx, gy)], pygame.key.get_mods()
                                
                                # Strict Tab Rules
                                if self.active_mode == "timetable":
                                    if node_clicked["type"] in ("signal", "via"): 
                                        continue
                                    if node_clicked["type"] == "platform":
                                        is_start = (len(self.station_path) == 0) or (self.replace_idx == 0)
                                        if self._activate_platform_menu(node_clicked.get("station"), event.pos, is_start_location=is_start): 
                                            continue
                                elif self.active_mode == "signal":
                                    if node_clicked["type"] not in ("signal", "via"): 
                                        continue

                                target_list = self.station_path if self.active_mode == "timetable" else self.signal_paths[self.active_signal_path_idx]
                                
                                # If replacement is active, replace the target item directly
                                if self.replace_idx != -1 and 0 <= self.replace_idx < len(target_list):
                                    self.save_state()
                                    target_list[self.replace_idx] = dict(node_clicked)
                                    self.replace_idx = -1
                                # If insert is active, insert right after
                                elif self.insert_idx != -1 and 0 <= self.insert_idx < len(target_list):
                                    self.save_state()
                                    target_list.insert(self.insert_idx + 1, dict(node_clicked))
                                    self.insert_idx += 1
                                # If clicking an already existing node on the map, select it for replace or delete
                                elif any(n["coord"] == node_clicked["coord"] for n in target_list):
                                    if mods & pygame.KMOD_CTRL:
                                        self.save_state()
                                        if self.active_mode == "timetable": 
                                            self.station_path[:] = [n for n in target_list if n['coord'] != node_clicked['coord']]
                                        else: 
                                            self.signal_paths[self.active_signal_path_idx][:] = [n for n in target_list if n['coord'] != node_clicked['coord']]
                                        self.replace_idx, self.insert_idx = -1, -1
                                    else:
                                        disp_indices = [i for i, n in enumerate(active_display_path) if n["coord"] == node_clicked["coord"]]
                                        if disp_indices: 
                                            self.replace_idx, self.insert_idx = disp_indices[0], -1
                                # Standard append
                                elif not (mods & pygame.KMOD_CTRL):
                                    self.save_state()
                                    target_list.append(dict(node_clicked))

                    else: # Sidebar Clicks
                        if event.button == 1:
                            if self.btn_prev_tt.collidepoint(event.pos): self._navigate_tt(-1)
                            elif self.btn_next_tt.collidepoint(event.pos): self._navigate_tt(1)
                            elif self.btn_load_tt.collidepoint(event.pos): self.load_existing_timetable()
                            elif self.btn_direction.collidepoint(event.pos): self.direction_val = "left" if self.direction_val == "right" else "right"
                            elif self.btn_despawn.collidepoint(event.pos): self.despawn = not self.despawn
                            elif self.btn_new_path.collidepoint(event.pos):
                                self.save_state() 
                                self.prev_path_idx = self.active_signal_path_idx if self.active_mode == "signal" else "timetable"
                                self.signal_paths.append([])
                                self.active_mode = "signal"
                                self.active_signal_path_idx = len(self.signal_paths) - 1
                                self.replace_idx, self.insert_idx, self.node_list_scroll_y = -1, -1, 0
                            elif self.btn_clone_path.collidepoint(event.pos):
                                self.save_state() 
                                self.prev_path_idx = self.active_signal_path_idx if self.active_mode == "signal" else "timetable"
                                self.signal_paths.append([dict(n) for n in self.signal_paths[self.active_signal_path_idx]])
                                self.active_mode = "signal"
                                self.active_signal_path_idx = len(self.signal_paths) - 1
                                self.replace_idx, self.insert_idx, self.node_list_scroll_y = -1, -1, 0
                                self.show_notification(f"Cloned Path {self.active_signal_path_idx - 1} to new Path {self.active_signal_path_idx}", 90)
                            elif self.btn_del_path.collidepoint(event.pos):
                                if len(self.signal_paths) > 1:
                                    self.save_state() 
                                    self.signal_paths.pop(self.active_signal_path_idx)
                                    self.active_mode = "signal"
                                    self.active_signal_path_idx = max(0, self.active_signal_path_idx - 1)
                                    self.prev_path_idx = "timetable"
                                    self.replace_idx, self.insert_idx, self.node_list_scroll_y = -1, -1, 0
                            elif self.btn_clone_route.collidepoint(event.pos):
                                self.save_state()
                                self.input_load_tt.text = "NEW"
                                self.show_notification("Cloned current route to NEW workspace.", 120)
                            elif self.btn_undo.collidepoint(event.pos): self.undo()
                            elif self.btn_save_update.collidepoint(event.pos): self.save_unified_data(is_new=False)
                            elif self.btn_save_new.collidepoint(event.pos): self.save_unified_data(is_new=True)
                            else:
                                for rect, i in getattr(self, "tab_rects", []):
                                    if rect.collidepoint(event.pos):
                                        self.prev_path_idx = self.active_signal_path_idx if self.active_mode == "signal" else "timetable"
                                        self.active_mode = "timetable" if i == "timetable" else "signal"
                                        if i != "timetable": self.active_signal_path_idx = i
                                        self.replace_idx, self.insert_idx = -1, -1
                                        break
                                if event.pos[1] > 400:
                                    for rect, i in getattr(self, "node_list_rects", []):
                                        if rect.collidepoint(event.pos):
                                            self.replace_idx, self.insert_idx = (i, -1) if not (pygame.key.get_mods() & pygame.KMOD_SHIFT) else (-1, i)
                                            break

                        elif event.button == 3:
                            if event.pos[1] > 400:
                                for rect, i in getattr(self, "node_list_rects", []):
                                    if rect.collidepoint(event.pos):
                                        node_to_toggle = active_display_path[i]
                                        if node_to_toggle["type"] in ("platform", "entrance_exit"):
                                            self.save_state()
                                            idx = next((j for j, n in enumerate(self.station_path) if n['coord'] == node_to_toggle['coord']), -1)
                                            if idx != -1: self.station_path[idx]["change_dir"] = not self.station_path[idx].get("change_dir", False)
                                        break

                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 3: self.panning = False
                    elif event.button == 1:
                        if getattr(self, "dragging_tab_idx", -1) != -1:
                            for rect, i in getattr(self, "tab_rects", []):
                                if rect.collidepoint(event.pos) and i != "timetable" and self.dragging_tab_idx != "timetable" and i != self.dragging_tab_idx:
                                    self.save_state()
                                    self.signal_paths[self.dragging_tab_idx], self.signal_paths[i] = self.signal_paths[i], self.signal_paths[self.dragging_tab_idx]
                                    self.active_signal_path_idx = i
                                    self.prev_path_idx = -1
                                    self.replace_idx, self.insert_idx = -1, -1
                                    break
                        self.dragging_tab_idx = -1

                elif event.type == pygame.MOUSEMOTION and self.panning:
                    dx, dy = event.pos[0] - self.pan_start[0], event.pos[1] - self.pan_start[1]
                    self.camera_x, self.camera_y = self.pan_start_camera[0] - dx, self.pan_start_camera[1] - dy
                    self._clamp_camera()

            self.draw()
            self.clock.tick(60)
        pygame.quit()


if __name__ == "__main__":
    scenario = choose_scenario()
    if scenario:
        app = UnifiedBuilder(scenario)
        app.run()
