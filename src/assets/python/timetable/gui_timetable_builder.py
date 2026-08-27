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
        self.width, self.height = 1500, 900
        self.screen = pygame.display.set_mode((self.width, self.height), pygame.RESIZABLE)
        pygame.display.set_caption(f"Timetable & ARS Builder - {scenario}")
        self.clock = pygame.time.Clock()
        self.scenario = scenario
        self.map_lines = (PROJECT_ROOT / f"{scenario}_map.txt").read_text(encoding="utf-8").splitlines()
        self.font_map = load_font(13, bold=True, custom=True)
        self.font_ui, self.font_small = load_font(20), load_font(16)
        
        self.camera_x, self.camera_y = 0, 0
        self.panning, self.pan_start, self.pan_start_camera = False, (0, 0), (0, 0)
        self.node_list_scroll_y = 0 
        
        # --- UI Elements Layout ---
        self.btn_prev_tt = pygame.Rect(10, 25, 30, 30)
        self.input_load_tt = TextInput(50, 25, 80, 30, "Load TT #", "")
        self.btn_load_tt = pygame.Rect(140, 25, 60, 30)
        self.btn_next_tt = pygame.Rect(210, 25, 30, 30)
        self.input_headcode = TextInput(10, 80, 100, 30, "Headcode Prefix", "1A")
        self.direction_val = "right"
        self.btn_direction = pygame.Rect(125, 80, 95, 30)
        self.despawn, self.btn_despawn = False, pygame.Rect(230, 80, 95, 30)
        self.input_change_tt = TextInput(10, 135, 120, 30, "Change TT Index", "")
        self.input_spawns = TextInput(140, 135, 270, 30, "Spawn Times (HH:MM:SS, ...)", "")
        self.btn_save_update, self.btn_save_new = pygame.Rect(10, 180, 195, 35), pygame.Rect(215, 180, 195, 35)
        self.btn_calculate = pygame.Rect(10, 225, 400, 35)
        self.btn_new_path, self.btn_clone_path = pygame.Rect(10, 275, 120, 30), pygame.Rect(140, 275, 130, 30)
        self.btn_del_path, self.btn_clone_route = pygame.Rect(280, 275, 130, 30), pygame.Rect(10, 315, 130, 30)
        self.btn_undo = pygame.Rect(150, 315, 120, 30)
        self.btn_insert_node, self.btn_del_node = pygame.Rect(10, 355, 130, 30), pygame.Rect(150, 355, 120, 30)
        
        self.undo_stack, self.nodes = [], {} 
        self._load_map_nodes()
        
        # --- CLEAN DATA STRUCTURE ---
        self.station_path: list = []             
        self.signal_paths: list[list] = [[]]     
        self.active_signal_path_idx: int = 0
        self.active_mode = "timetable" # "timetable" or "signal"
        self.prev_path_idx, self.replace_idx, self.insert_idx, self.dragging_tab_idx = -1, -1, -1, -1

        # --- Platform Selection Menu State ---
        self.platform_menu = {"active": False, "options": [], "rects": [], "station_name": ""}
        
        self.available_tt_indices = []
        self._refresh_available_tts()

    def _get_display_path(self):
        """Returns ONLY the list corresponding to the currently active tab."""
        if self.active_mode == "timetable":
            return self.station_path
        else:
            if self.active_signal_path_idx < len(self.signal_paths):
                return self.signal_paths[self.active_signal_path_idx]
            return []

    def _find_node_by_station(self, station_name, platform_name):
        """Helper to find a node, falling back safely if platform is empty."""
        for coord, data in self.nodes.items():
            if data.get("station") == station_name and data.get("platform") == platform_name: return dict(data)
        if platform_name == "" or platform_name is None:
            for coord, data in self.nodes.items():
                if data.get("station") == station_name: return dict(data)
        return None

    def _activate_platform_menu(self, station_name, position):
        """Prepares and opens the popup menu for platform selection."""
        platforms = sorted({n['platform'] for n in self.nodes.values() if n.get('station') == station_name})
        if len(platforms) > 0:
            self.platform_menu.update({'active': True, 'station_name': station_name, 'options': [("Any Platform", "")] + [(f"Platform {p}" if p else "Unnamed", p) for p in platforms], 'rects': []})
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

    def load_new_timetable_workspace(self):
        self.save_state()
        self.station_path, self.signal_paths = [], [[]]
        self.active_signal_path_idx, self.active_mode = 0, "timetable"
        self.prev_path_idx, self.replace_idx, self.insert_idx = -1, -1, -1
        self.input_headcode.text, self.direction_val, self.input_spawns.text, self.input_change_tt.text = "", "right", "", ""
        self.despawn = False

    def _load_map_nodes(self):
        for y, line in enumerate(self.map_lines):
            for x, char in enumerate(line):
                if char in ALL_SIGNALS: self.nodes[(x, y)] = {"type": "signal", "coord": (x, y), "char": char}

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
        if not idx_str.isdigit(): return
        tt_idx = int(idx_str)
        timetable_path, ars_path = JSON_PATH / f"{self.scenario}_timetable.json", JSON_PATH / f"{self.scenario}_ars_routes.json"
        if not timetable_path.exists(): return
        
        try:
            tt_data = json.loads(timetable_path.read_text(encoding="utf-8"))
            ars_data = json.loads(ars_path.read_text(encoding="utf-8")) if ars_path.exists() else {}
            ars_data = ars_data.get("routes", []) if isinstance(ars_data, dict) else ars_data
        except json.JSONDecodeError: return
            
        tt_entry = next((t for t in tt_data if t.get("index") == tt_idx), None)
        if not tt_entry: return
        ars_entry = next((r for r in ars_data if r.get("timetable_index") == tt_idx), None)

        self.save_state()
        self.station_path = []
        start_loc = tt_entry.get("start_location", {})
        if start_node := self._find_node_by_station(start_loc.get("station"), start_loc.get("platform")):
            self.station_path.append(start_node)

        for stop_entry in tt_entry.get("stops", []):
            if stop_entry.get("type") == "signal": continue # Strict separation: Ignore legacy signals in timetable

            if node := self._find_node_by_station(stop_entry.get("station"), stop_entry.get("platform")):
                node_copy = dict(node)
                node_copy["platform"] = stop_entry.get("platform", "")
                if stop_entry.get("change_direction"): node_copy["change_dir"] = True
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

    def save_unified_data(self, is_new=False):
        print("\n=== SAVING TIMETABLE AND ARS DATA ===")
        
        # 1. Validation Checks
        if len(self.station_path) < 1 and len(self.signal_paths[0]) < 1:
            print("Error: No nodes in path. Add a start location and at least one stop or signal.")
            return
        if len(self.station_path) == 1 and len(self.signal_paths[0]) == 0:
            print("Error: Path is too short. Must include at least one stop or signal after the start.")
            return

        change_tt_text = self.input_change_tt.text.strip()
        if not self.despawn and not change_tt_text:
            print("Error: You must select 'Despawn' or input a 'Change TT Index' for the final stop before saving!")
            return

        # --- 2. PREPARE TIMETABLE DATA ---
        start_node = self.station_path[0] if self.station_path else self.signal_paths[0][0]
        
        start_location = {
            "type": "entrance_exit" if start_node["type"] == "entrance_exit" else "platform",
            "station": start_node.get("station", ""),
            "platform": start_node.get("platform", "")
        }

        stops = []
        temp_display_path = self._get_display_path()
        
        start_node_index = next((i for i, n in enumerate(temp_display_path) if n['coord'] == start_node['coord']), 0)
        
        current_time = 0
        for i in range(start_node_index + 1, len(temp_display_path)):
            node = temp_display_path[i]
            prev_node = temp_display_path[i-1]
            
            # Use Manhattan distance (dx + dy) for accurate physical track timing
            dx = abs(node["coord"][0] - prev_node["coord"][0])
            dy = abs(node["coord"][1] - prev_node["coord"][1])
            current_time += (dx + dy)

            # We only write nodes to timetable.json if they exist in station_path
            is_manual_stop = any(n['coord'] == node['coord'] for n in self.station_path)
            
            if is_manual_stop and node['coord'] != start_node['coord']:
                arrival_time = current_time
                departure_time = arrival_time
                if node["type"] == "platform":
                    departure_time += 30 # Standard dwell time
                
                # Find the matching original node from station_path to get the correct 'platform' string (e.g. "")
                original_node = next(n for n in self.station_path if n['coord'] == node['coord'])
                
                stop_entry = {
                    "station": original_node.get("station", ""), 
                    "platform": original_node.get("platform", ""), 
                    "arrival_offset": arrival_time, 
                    "departure_offset": departure_time
                }
                
                if original_node.get("change_dir"): 
                    stop_entry["change_direction"] = True
                
                # Prevent duplicates
                if not any(s.get('station') == stop_entry.get('station') and s.get('platform') == stop_entry.get('platform') for s in stops): 
                    stops.append(stop_entry)

        if stops:
            if self.despawn:
                stops[-1]["despawn"] = True
            elif change_tt_text.isdigit():
                stops[-1]["change_timetable"] = int(change_tt_text)
            
        timetable_path = JSON_PATH / f"{self.scenario}_timetable.json"
        tt_data = []
        if timetable_path.exists():
            try: 
                tt_data = json.loads(timetable_path.read_text(encoding="utf-8"))
            except Exception: 
                pass
            
        loaded_idx_str = self.input_load_tt.text.strip()
        if is_new or not loaded_idx_str.isdigit():
            new_index = max([t.get("index", 0) for t in tt_data], default=0) + 1
        else:
            new_index = int(loaded_idx_str)
            tt_data = [t for t in tt_data if t.get("index") != new_index]

        new_tt_entry = {
            "index": new_index,
            "headcode_prefix": self.input_headcode.text.strip().upper(),
            "start_location": start_location,
            "direction": self.direction_val,
            "stops": stops,
            "spawn_times": [t.strip() for t in self.input_spawns.text.split(",") if t.strip()]
        }
        tt_data.append(new_tt_entry)
        tt_data.sort(key=lambda x: x.get("index", 999))
        
        # --- 3. PREPARE ARS DATA ---
        ars_path = JSON_PATH / f"{self.scenario}_ars_routes.json"
        ars_data = []
        if ars_path.exists():
            try:
                raw_payload = json.loads(ars_path.read_text(encoding="utf-8"))
                ars_data = raw_payload.get("routes", []) if isinstance(raw_payload, dict) else raw_payload
            except Exception: 
                pass

        if not is_new and loaded_idx_str.isdigit():
            ars_data = [r for r in ars_data if r.get("timetable_index") != new_index]

        new_ars_entry = {
            "name": str(new_index),
            "timetable_index": new_index,
            "signal_paths": [[[n['coord'][0], n['coord'][1]] for n in path] for path in self.signal_paths]
        }
        if new_ars_entry["signal_paths"] and new_ars_entry["signal_paths"][0]:
            new_ars_entry["signals"] = new_ars_entry["signal_paths"][0]
        
        ars_data.append(new_ars_entry)
        ars_data.sort(key=lambda x: x.get("timetable_index", 999))

        # --- 4. WRITE TO FILES ---
        try:
            timetable_path.write_text(json.dumps(tt_data, indent=4), encoding="utf-8")
            print(f"SUCCESS! Timetable Index {new_index} saved to timetable file.")
        except Exception as e:
            print(f"CRITICAL ERROR saving Timetable: {e}")

        try:
            ars_path.write_text(json.dumps({"routes": ars_data}, indent=4), encoding="utf-8")
            print(f"SUCCESS! ARS Index {new_index} saved to ARS file.")
        except Exception as e:
            print(f"CRITICAL ERROR saving ARS: {e}")

        self.input_load_tt.text = str(new_index)
        self._refresh_available_tts()

    def run_needle_threader(self):
        pass # Placeholder for future logic

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
                screen_x, screen_y = SIDEBAR_WIDTH + x * CELL_SIZE - self.camera_x, y * CELL_SIZE - self.camera_y
                if not (map_rect.left - CELL_SIZE < screen_x < map_rect.right and -CELL_SIZE < screen_y < map_rect.bottom): continue
                
                rect = pygame.Rect(screen_x, screen_y, CELL_SIZE, CELL_SIZE)
                bg_color, node_in_path = COL_GRID, False

                if (x, y) in self.nodes:
                    node = self.nodes[(x, y)]
                    if node.get("type") == "signal": bg_color = COL_SIGNAL
                    elif node.get("type") == "platform": bg_color = COL_PLATFORM
                    elif node.get("type") == "entrance_exit": bg_color = COL_ENTRANCE
                    
                    if self.active_mode == "timetable" and any(n["coord"] == (x, y) for n in self.station_path): bg_color, node_in_path = COL_SELECTED, True
                    elif self.active_mode == "signal" and self.active_signal_path_idx < len(self.signal_paths) and any(n["coord"] == (x, y) for n in self.signal_paths[self.active_signal_path_idx]): bg_color, node_in_path = COL_SELECTED, True

                if insert_node and insert_node["coord"] == (x, y): bg_color = COL_INSERT
                elif replace_node and replace_node["coord"] == (x, y): bg_color = COL_REPLACE
                    
                pygame.draw.rect(self.screen, bg_color, rect)
                pygame.draw.rect(self.screen, (20, 20, 20), rect, 1)
                self.screen.blit(self.font_map.render(char, True, (0,0,0) if bg_color != COL_GRID else COL_TEXT), self.font_map.render(char, True, (0,0,0)).get_rect(center=rect.center))

        def draw_path_lines(nodes, col, width):
            if len(nodes) < 2: return
            pygame.draw.lines(self.screen, col, False, [(SIDEBAR_WIDTH + n["coord"][0]*CELL_SIZE - self.camera_x + CELL_SIZE//2, n["coord"][1]*CELL_SIZE - self.camera_y + CELL_SIZE//2) for n in nodes], width)

        draw_path_lines(self.station_path, COL_LINE_STA, 3)
        for i, s_path in enumerate(self.signal_paths): draw_path_lines(s_path, COL_LINE_SIG_EDIT if i == self.active_signal_path_idx else COL_LINE_SIG_ALT, 4 if i == self.active_signal_path_idx else 2)

        self.screen.set_clip(None)
        if self.platform_menu['active']:
            for i, (text, _) in enumerate(self.platform_menu['options']):
                rect = self.platform_menu['rects'][i]
                pygame.draw.rect(self.screen, (50, 50, 70), rect)
                pygame.draw.rect(self.screen, (150, 150, 200), rect, 1)
                self.screen.blit(self.font_small.render(text, True, COL_TEXT), (rect.x + 5, rect.y + 5))
        
        pygame.draw.rect(self.screen, COL_SIDEBAR_BG, (0, 0, SIDEBAR_WIDTH, self.height))
        pygame.draw.rect(self.screen, (100, 100, 100), self.btn_prev_tt, border_radius=4)
        self.screen.blit(self.font_ui.render("<", True, COL_TEXT), (self.btn_prev_tt.x+8, self.btn_prev_tt.y+5))
        self.input_load_tt.draw(self.screen)
        pygame.draw.rect(self.screen, (100, 150, 100), self.btn_load_tt, border_radius=4)
        self.screen.blit(self.font_small.render("LOAD", True, (0,0,0)), (self.btn_load_tt.x + 10, self.btn_load_tt.y + 8))
        pygame.draw.rect(self.screen, (100, 100, 100), self.btn_next_tt, border_radius=4)
        self.screen.blit(self.font_ui.render(">", True, COL_TEXT), (self.btn_next_tt.x+8, self.btn_next_tt.y+5))

        self.input_headcode.draw(self.screen)
        pygame.draw.rect(self.screen, (80, 150, 80) if self.direction_val == "right" else (200, 100, 100), self.btn_direction, border_radius=4)
        pygame.draw.rect(self.screen, (200, 200, 200), self.btn_direction, 2, border_radius=4)
        self.screen.blit(self.font_ui.render("Direction", True, COL_TEXT), (self.btn_direction.x, self.btn_direction.y - 20))
        self.screen.blit(self.font_ui.render(f"{self.direction_val.title()}", True, (255,255,255)), (self.btn_direction.x + 20, self.btn_direction.y + 5))
        pygame.draw.rect(self.screen, COL_PLATFORM if self.despawn else (60,60,60), self.btn_despawn, border_radius=4)
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
        self.screen.blit(self.font_small.render("++ Clone Path", True, (0,0,0)), (self.btn_clone_path.x + 15, self.btn_clone_path.y + 8))
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

        y_off, tab_x, self.tab_rects = 395, 10, []
        tt_rect = pygame.Rect(tab_x, y_off, 90, 25)
        pygame.draw.rect(self.screen, COL_SELECTED if self.active_mode == "timetable" else (100, 100, 100), tt_rect, border_radius=4)
        self.screen.blit(self.font_small.render("Timetable", True, (0,0,0)), (tt_rect.x + 5, tt_rect.y + 5))
        self.tab_rects.append((tt_rect, "timetable")); tab_x += 95

        for i in range(len(self.signal_paths)):
            rect = pygame.Rect(tab_x, y_off, 90, 25)
            pygame.draw.rect(self.screen, COL_SELECTED if self.active_mode == "signal" and i == self.active_signal_path_idx else (100, 100, 100), rect, border_radius=4)
            self.screen.blit(self.font_small.render(f"Path {i}" + ("(Prim)" if i == 0 else ""), True, (0,0,0)), (rect.x + 5, rect.y + 5))
            self.tab_rects.append((rect, i))
            tab_x += 95
            if tab_x > 320: tab_x, y_off = 10, y_off + 30

        y_off += 35
        self.screen.blit(self.font_small.render("Select Node on Map/List to Replace. Map: Ctrl = Delete", True, (150,150,150)), (10, y_off))
        self.screen.blit(self.font_small.render("Right-Click List Node = Toggle Reverse Direction [REV]", True, (150,150,150)), (10, y_off + 20))
        
        y_off += 40
        self.node_list_rects = [] 
        list_label = "Timetable Stops:" if self.active_mode == "timetable" else f"Signal Path {self.active_signal_path_idx}:"
        self.screen.blit(self.font_ui.render(list_label, True, COL_TEXT), (10, y_off))
        y_off += 25
        
        self.screen.set_clip(pygame.Rect(0, y_off, SIDEBAR_WIDTH, self.height - y_off))
        current_y = y_off - self.node_list_scroll_y
        
        for i, node in enumerate(active_display_path):
            if node["type"] == "signal": txt = f"{i+1}. Signal at {node['coord']}"
            else:
                plat_str = str(node.get('platform', ''))
                display_plat = f"P{plat_str}" if len(plat_str) == 1 and plat_str.isdigit() else ("[Any Platform]" if plat_str == "" else plat_str.title())
                txt = f"{i+1}. {node['type'].title().replace('_', ' ')}: {node['station']} {display_plat}".strip()
            if node.get("change_dir"): txt += " [REV]"
            
            lbl = self.font_ui.render(txt, True, COL_REPLACE if i == self.replace_idx else COL_INSERT if i == self.insert_idx else COL_TEXT)
            rect = pygame.Rect(10, current_y, 360, 22)
            self.screen.blit(lbl, (10, current_y))
            self.node_list_rects.append((rect, i))
            current_y += 25
            
        self.screen.set_clip(None)
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
                        elif event.key == pygame.K_DELETE:
                            self.save_state()
                            idx_to_del = self.replace_idx if self.replace_idx != -1 else self.insert_idx if self.insert_idx != -1 else -1
                            if idx_to_del != -1 and 0 <= idx_to_del < len(active_display_path):
                                node_to_delete = active_display_path[idx_to_del]
                                if node_to_delete['type'] == 'signal':
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
                            if self.platform_menu['active']:
                                menu_clicked = False
                                for i, rect in enumerate(self.platform_menu['rects']):
                                    if rect.collidepoint(event.pos):
                                        _, platform = self.platform_menu['options'][i]
                                        if node_to_add := self._find_node_by_station(self.platform_menu['station_name'], platform):
                                            self.save_state()
                                            node_copy = dict(node_to_add)
                                            node_copy["platform"] = platform
                                            
                                            # Apply Insert/Replace Logic to station_path
                                            if self.replace_idx != -1 and 0 <= self.replace_idx < len(active_display_path):
                                                self.station_path[self.replace_idx] = node_copy
                                                self.replace_idx = -1
                                            elif self.insert_idx != -1 and 0 <= self.insert_idx < len(active_display_path):
                                                self.station_path.insert(self.insert_idx + 1, node_copy)
                                                self.insert_idx += 1
                                            else:
                                                self.station_path.append(node_copy)
                                        menu_clicked = True
                                        self.platform_menu['active'] = False
                                        break
                                if not menu_clicked: self.platform_menu['active'] = False
                                continue

                            gx, gy = self._screen_to_grid(event.pos)
                            if (gx, gy) in self.nodes:
                                node_clicked, mods = self.nodes[(gx, gy)], pygame.key.get_mods()
                                
                                # Strict Tab Rules
                                if self.active_mode == "timetable":
                                    if node_clicked["type"] == "signal": continue
                                    if node_clicked["type"] == "platform":
                                        if self._activate_platform_menu(node_clicked.get("station"), event.pos): continue
                                elif self.active_mode == "signal":
                                    if node_clicked["type"] != "signal": continue

                                target_list = self.station_path if self.active_mode == "timetable" else self.signal_paths[self.active_signal_path_idx]
                                
                                if any(n["coord"] == node_clicked["coord"] for n in target_list):
                                    if mods & pygame.KMOD_CTRL:
                                        self.save_state()
                                        if self.active_mode == "timetable": self.station_path[:] = [n for n in target_list if n['coord'] != node_clicked['coord']]
                                        else: self.signal_paths[self.active_signal_path_idx][:] = [n for n in target_list if n['coord'] != node_clicked['coord']]
                                        self.replace_idx, self.insert_idx = -1, -1
                                    else:
                                        disp_indices = [i for i, n in enumerate(active_display_path) if n["coord"] == node_clicked["coord"]]
                                        if disp_indices: self.replace_idx, self.insert_idx = disp_indices[0], -1
                                elif not (mods & pygame.KMOD_CTRL):
                                    self.save_state()
                                    node_copy = dict(node_clicked)
                                    if self.replace_idx != -1 and 0 <= self.replace_idx < len(active_display_path):
                                        target_list[self.replace_idx] = node_copy
                                    elif self.insert_idx != -1 and 0 <= self.insert_idx < len(active_display_path):
                                        target_list.insert(self.insert_idx + 1, node_copy)
                                        self.insert_idx += 1
                                    else:
                                        target_list.append(node_copy)

                    else: # Sidebar Clicks
                        if event.button == 1:
                            if self.btn_prev_tt.collidepoint(event.pos): self._navigate_tt(-1)
                            elif self.btn_next_tt.collidepoint(event.pos): self._navigate_tt(1)
                            elif self.btn_load_tt.collidepoint(event.pos): self.load_existing_timetable()
                            elif self.btn_direction.collidepoint(event.pos): self.direction_val = "left" if self.direction_val == "right" else "right"
                            elif self.btn_despawn.collidepoint(event.pos): self.despawn = not self.despawn
                            elif self.btn_new_path.collidepoint(event.pos):
                                self.save_state() 
                                self.signal_paths.append([])
                                self.active_signal_path_idx = len(self.signal_paths) - 1
                                self.replace_idx, self.insert_idx, self.node_list_scroll_y = -1, -1, 0
                            elif self.btn_clone_path.collidepoint(event.pos):
                                self.save_state() 
                                self.signal_paths.append([dict(n) for n in self.signal_paths[self.active_signal_path_idx]])
                                self.active_signal_path_idx = len(self.signal_paths) - 1
                                self.replace_idx, self.insert_idx, self.node_list_scroll_y = -1, -1, 0
                            elif self.btn_del_path.collidepoint(event.pos):
                                if len(self.signal_paths) > 1:
                                    self.save_state() 
                                    self.signal_paths.pop(self.active_signal_path_idx)
                                    self.active_signal_path_idx = max(0, self.active_signal_path_idx - 1)
                                    self.replace_idx, self.insert_idx, self.node_list_scroll_y = -1, -1, 0
                            elif self.btn_clone_route.collidepoint(event.pos):
                                self.save_state()
                                self.input_load_tt.text = "NEW"
                            elif self.btn_undo.collidepoint(event.pos): self.undo()
                            elif self.btn_insert_node.collidepoint(event.pos):
                                if self.replace_idx != -1: self.insert_idx, self.replace_idx = self.replace_idx, -1
                            elif self.btn_del_node.collidepoint(event.pos): self.run(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DELETE))
                            elif self.btn_calculate.collidepoint(event.pos): self.run_needle_threader()
                            elif self.btn_save_update.collidepoint(event.pos): self.save_unified_data(is_new=False)
                            elif self.btn_save_new.collidepoint(event.pos): self.save_unified_data(is_new=True)
                            else:
                                for rect, i in getattr(self, "tab_rects", []):
                                    if rect.collidepoint(event.pos):
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
                                            self.station_path[i]["change_dir"] = not self.station_path[i].get("change_dir", False)
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
