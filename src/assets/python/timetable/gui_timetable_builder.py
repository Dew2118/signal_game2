import pygame
import sys
import json
import os
import itertools
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

# Separated Path Colors
COL_LINE_SIG = (0, 255, 0)        # Green for Signals
COL_LINE_SIG_ALT = (150, 220, 90)
COL_LINE_STA = (0, 150, 255)      # Blue for Stations
COL_LINE_STA_ALT = (100, 200, 255)

CELL_SIZE = 16
SIDEBAR_WIDTH = 380

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
        
        lbl_surf = self.font.render(self.label, True, COL_TEXT)
        screen.blit(lbl_surf, (self.rect.x, self.rect.y - 20))
        
        display_text = self.text
        if self.active and pygame.time.get_ticks() % 1000 < 500:
            display_text += "|"
            
        txt_surf = self.font.render(display_text, True, COL_TEXT)
        screen.blit(txt_surf, (self.rect.x + 5, self.rect.y + 5))

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.active = self.rect.collidepoint(event.pos)
        elif event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.unicode and event.unicode.isprintable():
                self.text += event.unicode

class UnifiedBuilder:
    def __init__(self, scenario):
        pygame.init()
        pygame.key.set_repeat(200, 50) 
        
        self.width, self.height = 1400, 850
        self.screen = pygame.display.set_mode((self.width, self.height))
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
        
        # UI Elements
        self.input_headcode = TextInput(10, 30, 100, 30, "Headcode Prefix", "1A")
        self.input_change_tt = TextInput(10, 90, 150, 30, "Change TT Index", "")
        self.despawn = False
        
        # --- NEW: Direction Toggle Button ---
        self.direction_val = "right"
        self.btn_direction = pygame.Rect(120, 30, 100, 30)
        # ------------------------------------
        
        self.btn_despawn = pygame.Rect(180, 90, 100, 30)
        self.btn_calculate = pygame.Rect(10, 150, 220, 40)
        
        # Inputs & Buttons for saving
        self.input_spawns = TextInput(10, 230, 350, 30, "Spawn Times (e.g. 08:35:00, 09:12:00)", "")
        self.btn_save = pygame.Rect(10, 290, 260, 40)
        self.btn_undo = pygame.Rect(280, 290, 80, 40)
        
        # Load Segments
        self.nodes = {} 
        self._load_map_nodes()
        
        self.route_steps = []

    def _load_map_nodes(self):
        for y, line in enumerate(self.map_lines):
            for x, char in enumerate(line):
                if char in ALL_SIGNALS:
                    self.nodes[(x, y)] = {"type": "signal", "coord": (x, y), "char": char}
        
        anno_path = JSON_PATH / f"{self.scenario}_annotated_segments.json"
        if anno_path.exists():
            data = json.loads(anno_path.read_text(encoding="utf-8"))
            for seg in data.get("segments", []):
                seg_type = "entrance_exit" if seg.get("left") == seg.get("right") else "platform"
                station = seg.get("station", "Unknown")
                plat = seg.get("platform", "")
                
                for key in ["left", "right", "start", "end"]:
                    if key in seg:
                        cx, cy = seg[key][0], seg[key][1]
                        self.nodes[(cx, cy)] = {
                            "type": seg_type, 
                            "station": station, 
                            "platform": plat, 
                            "coord": (cx, cy)
                        }

    def _screen_to_grid(self, pos):
        mx, my = pos
        gx = (mx - SIDEBAR_WIDTH + self.camera_x) // CELL_SIZE
        gy = (my + self.camera_y) // CELL_SIZE
        return gx, gy

    def _clamp_camera(self):
        map_pixel_w = max((len(line) for line in self.map_lines), default=0) * CELL_SIZE
        map_pixel_h = len(self.map_lines) * CELL_SIZE
        max_cam_x = max(0, map_pixel_w - (self.width - SIDEBAR_WIDTH))
        max_cam_y = max(0, map_pixel_h - self.height)
        self.camera_x = min(max(0, self.camera_x), max_cam_x)
        self.camera_y = min(max(0, self.camera_y), max_cam_y)

    def draw(self):
        self.screen.fill(COL_BG)
        
        map_rect = pygame.Rect(SIDEBAR_WIDTH, 0, self.width-SIDEBAR_WIDTH, self.height)
        self.screen.set_clip(map_rect)
        
        flat_selected_nodes = [node for step in self.route_steps for node in step]

        for y, line in enumerate(self.map_lines):
            for x, char in enumerate(line):
                if char == " ": continue
                
                screen_x = SIDEBAR_WIDTH + x * CELL_SIZE - self.camera_x
                screen_y = y * CELL_SIZE - self.camera_y
                
                if screen_x < SIDEBAR_WIDTH - CELL_SIZE or screen_x > self.width or screen_y < -CELL_SIZE or screen_y > self.height:
                    continue
                
                rect = pygame.Rect(screen_x, screen_y, CELL_SIZE, CELL_SIZE)
                
                bg_color = COL_GRID
                if (x, y) in self.nodes:
                    ntype = self.nodes[(x, y)]["type"]
                    if ntype == "signal": bg_color = COL_SIGNAL
                    elif ntype == "platform": bg_color = COL_PLATFORM
                    elif ntype == "entrance_exit": bg_color = COL_ENTRANCE
                    
                if any(n["coord"] == (x, y) for n in flat_selected_nodes):
                    bg_color = COL_SELECTED
                    
                pygame.draw.rect(self.screen, bg_color, rect)
                pygame.draw.rect(self.screen, (20,20,20), rect, 1)
                
                glyph = self.font_map.render(char, True, COL_TEXT if bg_color == COL_GRID else (0,0,0))
                self.screen.blit(glyph, glyph.get_rect(center=rect.center))
                
        # Draw Separated Path Lines
        signal_steps = [[n for n in step if n["type"] == "signal"] for step in self.route_steps]
        signal_steps = [s for s in signal_steps if s]
        
        station_steps = [[n for n in step if n["type"] in ("entrance_exit", "platform")] for step in self.route_steps]
        station_steps = [s for s in station_steps if s]

        def draw_lines(steps, col_pri, col_alt):
            for i in range(len(steps) - 1):
                current_step = steps[i]
                next_step = steps[i + 1]

                for c_idx, current_node in enumerate(current_step):
                    for n_idx, next_node in enumerate(next_step):
                        is_primary = (c_idx == 0 and n_idx == 0)
                        color = col_pri if is_primary else col_alt
                        width = 3 if is_primary else 2
                        
                        c1 = current_node["coord"]
                        c2 = next_node["coord"]
                        p1 = (SIDEBAR_WIDTH + c1[0]*CELL_SIZE - self.camera_x + CELL_SIZE//2, c1[1]*CELL_SIZE - self.camera_y + CELL_SIZE//2)
                        p2 = (SIDEBAR_WIDTH + c2[0]*CELL_SIZE - self.camera_x + CELL_SIZE//2, c2[1]*CELL_SIZE - self.camera_y + CELL_SIZE//2)
                        pygame.draw.line(self.screen, color, p1, p2, width)

        draw_lines(signal_steps, COL_LINE_SIG, COL_LINE_SIG_ALT)
        draw_lines(station_steps, COL_LINE_STA, COL_LINE_STA_ALT)

        self.screen.set_clip(None)
        
        # Draw Sidebar
        pygame.draw.rect(self.screen, COL_SIDEBAR_BG, (0, 0, SIDEBAR_WIDTH, self.height))
        self.input_headcode.draw(self.screen)
        self.input_change_tt.draw(self.screen)
        self.input_spawns.draw(self.screen)
        
        # --- NEW: Draw Direction Toggle ---
        dir_color = (80, 150, 80) if self.direction_val == "right" else (200, 100, 100)
        pygame.draw.rect(self.screen, dir_color, self.btn_direction, border_radius=4)
        pygame.draw.rect(self.screen, (200, 200, 200), self.btn_direction, 2, border_radius=4)
        lbl_surf = self.font_ui.render("Direction", True, COL_TEXT)
        self.screen.blit(lbl_surf, (self.btn_direction.x, self.btn_direction.y - 20))
        lbl = self.font_ui.render(f"{self.direction_val.title()}", True, (255,255,255))
        self.screen.blit(lbl, (self.btn_direction.x + 15, self.btn_direction.y + 6))
        # ----------------------------------

        # Despawn Button
        d_color = COL_PLATFORM if self.despawn else (60,60,60)
        pygame.draw.rect(self.screen, d_color, self.btn_despawn, border_radius=4)
        lbl = self.font_ui.render("Despawn", True, (0,0,0) if self.despawn else COL_TEXT)
        self.screen.blit(lbl, (self.btn_despawn.x + 15, self.btn_despawn.y + 5))
        
        # Calculate Button
        pygame.draw.rect(self.screen, (100, 150, 255), self.btn_calculate, border_radius=4)
        lbl = self.font_ui.render("Calculate Safe Spawns", True, (0,0,0))
        self.screen.blit(lbl, (self.btn_calculate.x + 15, self.btn_calculate.y + 10))
        
        # Save & Undo Buttons
        pygame.draw.rect(self.screen, COL_PLATFORM, self.btn_save, border_radius=4)
        lbl = self.font_ui.render("SAVE ROUTE & TIMETABLE", True, (0,0,0))
        self.screen.blit(lbl, (self.btn_save.x + 15, self.btn_save.y + 10))
        
        pygame.draw.rect(self.screen, (200, 100, 100), self.btn_undo, border_radius=4)
        lbl = self.font_ui.render("Undo", True, (0,0,0))
        self.screen.blit(lbl, (self.btn_undo.x + 15, self.btn_undo.y + 10))

        inst_txt = "Click: Add Step | Shift+Click: Add Alternate"
        inst_lbl = self.font_small.render(inst_txt, True, (150,150,150))
        self.screen.blit(inst_lbl, (10, 350))
        
        # List Nodes
        y_off = 370
        for i, step in enumerate(self.route_steps):
            primary = step[0]
            alts = len(step) - 1
            if primary["type"] == "signal":
                txt = f"{i+1}. Signal at {primary['coord']}"
            else:
                plat_str = str(primary['platform'])
                if plat_str.lower() in ["up", "down", "fast", "slow", "main", "relief"]:
                    display_plat = plat_str.title()
                else:
                    display_plat = f"P{plat_str}" if plat_str else ""
                txt = f"{i+1}. {primary['type'].title().replace('_', ' ')}: {primary['station']} {display_plat}".strip()
            
            if alts > 0: txt += f" (+{alts} alts)"
                
            lbl = self.font_ui.render(txt, True, COL_TEXT)
            self.screen.blit(lbl, (10, y_off))
            y_off += 25

        pygame.display.flip()

    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    
                self.input_headcode.handle_event(event)
                self.input_change_tt.handle_event(event)
                self.input_spawns.handle_event(event)
                
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        if event.pos[0] > SIDEBAR_WIDTH:
                            gx, gy = self._screen_to_grid(event.pos)
                            if (gx, gy) in self.nodes:
                                node = self.nodes[(gx, gy)]
                                mods = pygame.key.get_mods()
                                shift = bool(mods & pygame.KMOD_SHIFT)
                                ctrl = bool(mods & pygame.KMOD_CTRL)
                                
                                if ctrl:
                                    for step in self.route_steps:
                                        if node in step: step.remove(node)
                                    self.route_steps = [s for s in self.route_steps if s]
                                elif shift and self.route_steps:
                                    if node not in self.route_steps[-1]:
                                        self.route_steps[-1].append(node)
                                else:
                                    self.route_steps.append([node])
                        else:
                            # --- NEW: Direction Toggle Click Handler ---
                            if self.btn_direction.collidepoint(event.pos):
                                self.direction_val = "left" if self.direction_val == "right" else "right"
                            # -------------------------------------------
                            elif self.btn_despawn.collidepoint(event.pos):
                                self.despawn = not self.despawn
                            elif self.btn_undo.collidepoint(event.pos):
                                if self.route_steps:
                                    self.route_steps.pop()
                            elif self.btn_calculate.collidepoint(event.pos):
                                self.run_needle_threader()
                            elif self.btn_save.collidepoint(event.pos):
                                self.save_unified_data()
                                
                    elif event.button == 3: # Right click pan
                        self.panning = True
                        self.pan_start = event.pos
                        self.pan_start_camera = (self.camera_x, self.camera_y)
                        
                    elif event.button == 4: # Mouse Wheel UP (Swapped to L/R)
                        if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                            self.camera_y -= 60
                        else:
                            self.camera_x -= 60
                        self._clamp_camera()
                        
                    elif event.button == 5: # Mouse Wheel DOWN (Swapped to L/R)
                        if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                            self.camera_y += 60
                        else:
                            self.camera_x += 60
                        self._clamp_camera()
                        
                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 3: self.panning = False
                        
                elif event.type == pygame.MOUSEMOTION and self.panning:
                    dx = event.pos[0] - self.pan_start[0]
                    dy = event.pos[1] - self.pan_start[1]
                    self.camera_x = self.pan_start_camera[0] - dx
                    self.camera_y = self.pan_start_camera[1] - dy
                    self._clamp_camera()

            self.draw()
            self.clock.tick(60)
        pygame.quit()

    def run_needle_threader(self):
        print("\n--- RUNNING NEEDLE THREADER (RECURSIVE ARS SCHEDULE) ---")
        if not self.route_steps:
            print("Error: No route selected!")
            return
            
        print(f"Train Prefix: {self.input_headcode.text} | Direction: {self.direction_val}")
        
        schedule_path = JSON_PATH / f"{self.scenario}_ars_schedule.json"
        if not schedule_path.exists():
            print(f"Error: Precalculated schedule not found at {schedule_path.name}!")
            return
            
        timetable_path = JSON_PATH / f"{self.scenario}_timetable.json"
        if not timetable_path.exists():
            print("Error: timetable.json not found!")
            return
            
        schedule_data = json.loads(schedule_path.read_text(encoding="utf-8"))
        existing_tt = json.loads(timetable_path.read_text(encoding="utf-8"))
        schedule_routes = schedule_data.get("routes", [])
        segments = schedule_data.get("segments", {})

        def get_continued_footprint(tt_index, base_relative_sec, visited=None):
            if visited is None: visited = set()
            if tt_index in visited: return [] 
            visited.add(tt_index)
            
            extension = []
            tt_entry = next((t for t in existing_tt if t.get("index") == tt_index), None)
            route = next((r for r in schedule_routes if r.get("timetable_index") == tt_index), None)
            
            if route and route.get("paths"):
                primary_coords = route["paths"][0].get("coords", [])
                for item in primary_coords:
                    if not isinstance(item, (list, tuple)) or len(item) < 3: continue
                    try:
                        cx, cy = int(item[0]), int(item[1])
                        rel_t = float(item[2])
                    except (TypeError, ValueError): continue
                    
                    extension.append({"coord": (cx, cy), "arrival": base_relative_sec + rel_t})
                    
            if tt_entry:
                stops = tt_entry.get("stops", [])
                if stops and "change_timetable" in stops[-1]:
                    next_tt = stops[-1]["change_timetable"]
                    next_offset = base_relative_sec + stops[-1].get("departure_offset", 0)
                    extension.extend(get_continued_footprint(next_tt, next_offset, visited))
            return extension

        import itertools
        combinations = list(itertools.product(*self.route_steps))
        ghost_footprints = []
        
        for combo in combinations:
            relative_second = 0
            footprint = []
            
            for i in range(len(combo) - 1):
                curr_node = combo[i]
                next_node = combo[i+1]
                seg_key = f"{curr_node['coord'][0]},{curr_node['coord'][1]}->{next_node['coord'][0]},{next_node['coord'][1]}"
                
                if seg_key in segments:
                    for coord in segments[seg_key]["coords"]:
                        footprint.append({"coord": (coord[0], coord[1]), "arrival": relative_second})
                        relative_second += 1 
                else:
                    c1, c2 = curr_node['coord'], next_node['coord']
                    dist = abs(c2[0] - c1[0]) + abs(c2[1] - c1[1])
                    for step in range(dist):
                        lerp_x = int(c1[0] + (c2[0] - c1[0]) * (step / max(1, dist)))
                        lerp_y = int(c1[1] + (c2[1] - c1[1]) * (step / max(1, dist)))
                        footprint.append({"coord": (lerp_x, lerp_y), "arrival": relative_second})
                        relative_second += 1

                if next_node["type"] == "platform":
                    relative_second += 30 
                    
            change_tt_str = self.input_change_tt.text.strip()
            if change_tt_str.isdigit():
                print(f"Chaining Ghost Train to Timetable {change_tt_str}...")
                continued_path = get_continued_footprint(int(change_tt_str), relative_second)
                footprint.extend(continued_path)
                
            ghost_footprints.append(footprint)

        print(f"Simulating {len(ghost_footprints)} Ghost Train permutations (Total length ~{len(ghost_footprints[0])} tiles)...")

        master_occupancy = {}
        
        def trace_existing_occupancy(tt_index, abs_spawn_seconds, visited=None):
            if visited is None: visited = set()
            visit_key = (tt_index, abs_spawn_seconds)
            if visit_key in visited: return
            visited.add(visit_key)
            
            tt_entry = next((t for t in existing_tt if t.get("index") == tt_index), None)
            if not tt_entry: return
            
            route = next((r for r in schedule_routes if r.get("timetable_index") == tt_index), None)
            if route and route.get("paths"):
                primary_coords = route["paths"][0].get("coords", [])
                for item in primary_coords:
                    if not isinstance(item, (list, tuple)) or len(item) < 3: continue
                    try:
                        cx, cy = int(item[0]), int(item[1])
                        rel_t = float(item[2])
                    except (TypeError, ValueError): continue
                    
                    abs_occupied_start = abs_spawn_seconds + rel_t - 15  
                    abs_occupied_end = abs_spawn_seconds + rel_t + 15    
                    master_occupancy.setdefault((cx, cy), []).append((abs_occupied_start, abs_occupied_end))
                    
            stops = tt_entry.get("stops", [])
            if stops and "change_timetable" in stops[-1]:
                next_tt = stops[-1]["change_timetable"]
                next_spawn = abs_spawn_seconds + stops[-1].get("departure_offset", 0)
                trace_existing_occupancy(next_tt, next_spawn, visited)

        for entry in existing_tt:
            for spawn_str in entry.get("spawn_times", []):
                try: h, m, s = map(int, spawn_str.split(":"))
                except ValueError: continue
                spawn_seconds = h * 3600 + m * 60 + s
                trace_existing_occupancy(entry.get("index"), spawn_seconds)

        print(f"Master Occupancy Map fully loaded with {len(master_occupancy)} conflicting points (including continuations).")

        safe_windows = []
        window_start = None
        
        for spawn_attempt in range(0, 86400, 30):
            any_path_safe = False
            
            for footprint in ghost_footprints:
                conflict_found = False
                for step in footprint:
                    coord = step["coord"]
                    if coord in master_occupancy:
                        my_arr = spawn_attempt + step["arrival"]
                        my_dep = my_arr + 2 
                        
                        for (occ_start, occ_end) in master_occupancy[coord]:
                            if my_arr <= occ_end and my_dep >= occ_start:
                                conflict_found = True
                                break
                    if conflict_found: break
                        
                if not conflict_found:
                    any_path_safe = True
                    break 
                    
            if any_path_safe:
                if window_start is None: window_start = spawn_attempt
            else:
                if window_start is not None:
                    safe_windows.append((window_start, spawn_attempt - 30))
                    window_start = None
                    
        if window_start is not None:
            safe_windows.append((window_start, 86400))

        print("\n--- SAFE SPAWN WINDOWS ---")
        if not safe_windows:
            print("CRITICAL TRACK CONGESTION: No safe windows found!")
        else:
            valid_gaps = 0
            for start, end in safe_windows:
                if end - start < 120: continue
                valid_gaps += 1
                st_h, st_m, st_s = start // 3600, (start % 3600) // 60, start % 60
                en_h, en_m, en_s = end // 3600, (end % 3600) // 60, end % 60
                
                en_h_display = 23 if en_h >= 24 else en_h
                en_m_display = 59 if en_h >= 24 else en_m
                en_s_display = 59 if en_h >= 24 else en_s
                print(f"Safe spawn: {st_h:02d}:{st_m:02d}:{st_s:02d}  to  {en_h_display:02d}:{en_m_display:02d}:{en_s_display:02d}")
                
            if valid_gaps == 1 and safe_windows[0][0] == 0 and safe_windows[0][1] == 86400:
                 print("WARNING: Track is completely clear. Verify that at least one train exists in timetable.json.")
        print("--------------------------\n")

    def save_unified_data(self):
        print("\n=== SAVING TIMETABLE AND ARS DATA ===")
        if len(self.route_steps) < 2:
            print("Error: Need at least a start point and one stop/signal.")
            return
            
        change_tt_text = self.input_change_tt.text.strip()
        if not self.despawn and not change_tt_text:
            print("Error: You must select 'Despawn' or input a 'Change TT Index' before saving!")
            return
            
        spawns_raw = [t.strip() for t in self.input_spawns.text.split(",") if t.strip()]
        if not spawns_raw:
            print("Warning: Saving without any spawn times.")
            
        timetable_path = JSON_PATH / f"{self.scenario}_timetable.json"
        ars_path = JSON_PATH / f"{self.scenario}_ars_routes.json"
        
        tt_data = []
        if timetable_path.exists():
            try: tt_data = json.loads(timetable_path.read_text(encoding="utf-8"))
            except Exception: pass
            
        new_index = max([t.get("index", 0) for t in tt_data], default=0) + 1
        
        primary_path = [step[0] for step in self.route_steps]
        start_node = primary_path[0]
        
        start_type = "entrance_exit" if start_node["type"] == "entrance_exit" else "platform"
        start_location = {
            "type": start_type,
            "station": start_node.get("station", ""),
            "platform": start_node.get("platform", "")
        }
        
        stops = []
        current_time = 0
        
        for i in range(1, len(primary_path)):
            node = primary_path[i]
            prev = primary_path[i-1]["coord"]
            curr = node["coord"]
            
            dist = abs(curr[0] - prev[0]) + abs(curr[1] - prev[1])
            current_time += dist
            
            if node["type"] in ("platform", "entrance_exit"):
                arr = current_time
                if node["type"] == "platform":
                    current_time += 30 
                dep = current_time
                
                stop_entry = {
                    "station": node.get("station", ""),
                    "platform": node.get("platform", ""),
                    "arrival_offset": arr,
                    "departure_offset": dep
                }
                stops.append(stop_entry)
                
        if stops:
            if self.despawn:
                stops[-1]["despawn"] = True
            elif self.input_change_tt.text.strip():
                try: 
                    stops[-1]["change_timetable"] = int(self.input_change_tt.text.strip())
                except ValueError: 
                    print("Warning: Change TT index invalid.")

        new_tt_entry = {
            "index": new_index,
            "headcode_prefix": self.input_headcode.text.strip().upper(),
            "start_location": start_location,
            "direction": self.direction_val, # Uses the new direction toggle
            "stops": stops,
            "spawn_times": spawns_raw
        }
        
        tt_data.append(new_tt_entry)
        
        ars_data = []
        if ars_path.exists():
            try: ars_data = json.loads(ars_path.read_text(encoding="utf-8"))
            except Exception: pass
            if isinstance(ars_data, dict): ars_data = ars_data.get("routes", [])
            
        signal_steps = []
        for step in self.route_steps:
            sigs = [list(n["coord"]) for n in step if n["type"] == "signal"]
            if sigs:
                signal_steps.append(sigs)
                
        if not signal_steps:
            print("Error: No signals selected. Cannot build ARS route.")
            return
            
        combinations = list(itertools.product(*signal_steps))
        signal_paths = [[list(c) for c in combo] for combo in combinations]
        
        new_ars_entry = {
            "name": str(new_index),
            "timetable_index": new_index,
            "signals": signal_paths[0],
            "signal_paths": signal_paths
        }
        
        ars_data.append(new_ars_entry)
        
        timetable_path.write_text(json.dumps(tt_data, indent=4), encoding="utf-8")
        if isinstance(ars_data, list):
            ars_wrapper = {"routes": ars_data}
        else:
            ars_wrapper = ars_data
        ars_path.write_text(json.dumps(ars_wrapper, indent=4), encoding="utf-8")
        
        print(f"SUCCESS! Timetable Index {new_index} saved to both JSONs.")
        print(f"Added {len(stops)} stops and {len(signal_paths)} ARS path variation(s).")
        
        self.route_steps = []

if __name__ == "__main__":
    scenario = choose_scenario()
    if scenario:
        app = UnifiedBuilder(scenario)
        app.run()
