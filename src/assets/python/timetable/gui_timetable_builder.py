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
COL_PREV_SELECTED = (180, 180, 100) # Dimmer yellow for the previously selected tab
COL_REPLACE = (255, 50, 50)    # Red for replace mode
COL_INSERT = (50, 255, 50)     # Green for insert mode

# Sequential Path Colors
COL_LINE_SIG_EDIT = (255, 255, 0) # Active Path Signals (Yellow)
COL_LINE_STA_EDIT = (255, 150, 0) # Active Path Stations (Orange)

COL_LINE_SIG = (0, 255, 0)        # Stored Primary Signals (Green)
COL_LINE_STA = (0, 150, 255)      # Stored Primary Stations (Blue)

COL_LINE_SIG_ALT = (50, 120, 50)  # Stored Alt Signals (Dim Green)
COL_LINE_STA_ALT = (50, 80, 150)  # Stored Alt Stations (Dim Blue)

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
        lbl_surf = self.font.render(self.label, True, COL_TEXT)
        screen.blit(lbl_surf, (self.rect.x, self.rect.y - 18))

        display_text = self.text
        if self.active and pygame.time.get_ticks() % 1000 < 500:
            display_text += "|"

        txt_surf = self.font.render(display_text, True, COL_TEXT)

        text_w = txt_surf.get_width()
        max_w = self.rect.width - 10
        offset_x = 0
        if text_w > max_w:
            offset_x = max_w - text_w

        old_clip = screen.get_clip()
        screen.set_clip(self.rect)
        screen.blit(txt_surf, (self.rect.x + 5 + offset_x, self.rect.y + 5))
        screen.set_clip(old_clip)

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
        
        self.width, self.height = 1500, 900
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
        
        # Save Buttons
        self.btn_save_update = pygame.Rect(10, 180, 195, 35)
        self.btn_save_new = pygame.Rect(215, 180, 195, 35)
        
        self.btn_calculate = pygame.Rect(10, 225, 400, 35)
        
        # Path Management Buttons
        self.btn_new_path = pygame.Rect(10, 275, 120, 30)
        self.btn_clone_path = pygame.Rect(140, 275, 130, 30)
        self.btn_del_path = pygame.Rect(280, 275, 130, 30)
        
        # Clone Route & Undo
        self.btn_clone_route = pygame.Rect(10, 315, 130, 30)
        self.btn_undo = pygame.Rect(150, 315, 120, 30)
        
        # Node Operations
        self.btn_insert_node = pygame.Rect(10, 355, 130, 30)
        self.btn_del_node = pygame.Rect(150, 355, 120, 30)
        
        self.undo_stack = []
        
        self.nodes = {} 
        self._load_map_nodes()
        
        # --- UNIFIED PATH MULTIVERSE STATE ---
        self.paths = [[]] 
        self.active_path_idx = 0
        self.prev_path_idx = -1 
        
        # Mid-Path Editing States
        self.replace_idx = -1 
        self.insert_idx = -1 
        self.dragging_tab_idx = -1 # NEW: Tracks tab drag-and-drop state
        
        self.available_tt_indices = []
        self._refresh_available_tts()



    def save_state(self):
        paths_copy = [[dict(node) for node in path] for path in self.paths]
        self.undo_stack.append({
            "paths": paths_copy,
            "active_path_idx": self.active_path_idx
        })
        if len(self.undo_stack) > 50:
            self.undo_stack.pop(0)

    def undo(self):
        if self.undo_stack:
            last_state = self.undo_stack.pop()
            self.paths = last_state["paths"]
            self.active_path_idx = last_state["active_path_idx"]
            self.replace_idx = -1
            self.insert_idx = -1
            print("Undo successful.")

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
                        # Shift the platform/entrance clickable left by 1 (x - 1)
                        cx, cy = seg[key][0] - 1, seg[key][1]
                        self.nodes[(cx, cy)] = {
                            "type": seg_type,
                            "station": station,
                            "platform": plat,
                            "coord": (cx, cy)
                        }


    def _refresh_available_tts(self):
        timetable_path = JSON_PATH / f"{self.scenario}_timetable.json"
        self.available_tt_indices = []
        if timetable_path.exists():
            try:
                tt_data = json.loads(timetable_path.read_text(encoding="utf-8"))
                self.available_tt_indices = sorted([t.get("index", 0) for t in tt_data if "index" in t])
            except Exception: pass

    def load_new_timetable_workspace(self):
        self.save_state()
        self.paths = [[]]
        self.active_path_idx = 0
        self.prev_path_idx = -1
        self.replace_idx = -1
        self.insert_idx = -1

        self.input_headcode.text = ""
        self.direction_val = "right"
        self.input_spawns.text = ""
        self.input_change_tt.text = ""
        self.despawn = False
        print("Loaded a NEW blank timetable workspace.")

    def _navigate_tt(self, direction):
        self._refresh_available_tts()

        sequence = self.available_tt_indices + ["NEW"]

        current_str = self.input_load_tt.text.strip()
        current_val = int(current_str) if current_str.isdigit() else "NEW"

        if current_val in sequence:
            list_idx = sequence.index(current_val)
            new_list_idx = (list_idx + direction) % len(sequence)
            new_val = sequence[new_list_idx]
        else:
            new_val = sequence[0] if direction > 0 else sequence[-1]

        if new_val == "NEW":
            self.input_load_tt.text = "NEW"
            self.load_new_timetable_workspace()
        else:
            self.input_load_tt.text = str(new_val)
            self.load_existing_timetable()

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

    def get_active_path(self):
        return self.paths[self.active_path_idx]

    def load_existing_timetable(self):
        idx_str = self.input_load_tt.text.strip()
        if idx_str == "NEW":
            self.load_new_timetable_workspace()
            return

        if not idx_str.isdigit():
            print("Error: Invalid Timetable Index to load.")
            return

        tt_idx = int(idx_str)
        timetable_path = JSON_PATH / f"{self.scenario}_timetable.json"
        ars_path = JSON_PATH / f"{self.scenario}_ars_routes.json"

        if not timetable_path.exists() or not ars_path.exists():
            print("Error: JSON files not found.")
            return

        tt_data = json.loads(timetable_path.read_text(encoding="utf-8"))
        ars_data = json.loads(ars_path.read_text(encoding="utf-8"))
        if isinstance(ars_data, dict): ars_data = ars_data.get("routes", [])

        tt_entry = next((t for t in tt_data if t.get("index") == tt_idx), None)
        ars_entry = next((r for r in ars_data if r.get("timetable_index") == tt_idx), None)

        if not tt_entry or not ars_entry:
            print(f"Error: Could not find Timetable {tt_idx} in both files.")
            return

        self.save_state()
        self.input_headcode.text = tt_entry.get("headcode_prefix", "")
        self.direction_val = tt_entry.get("direction", "right")
        self.input_spawns.text = ", ".join(tt_entry.get("spawn_times", []))

        stops = tt_entry.get("stops", [])
        self.despawn = False
        self.input_change_tt.text = ""
        if stops:
            if "despawn" in stops[-1]:
                self.despawn = True
            elif "change_timetable" in stops[-1]:
                self.input_change_tt.text = str(stops[-1]["change_timetable"])

        editor_paths = ars_entry.get("editor_paths", [])
        if editor_paths:
            self.paths = []
            for ep in editor_paths:
                reconstructed = []
                for coord_list in ep:
                    c_tup = (coord_list[0], coord_list[1])
                    if c_tup in self.nodes:
                        node_copy = dict(self.nodes[c_tup])
                        # Restore change_dir flag if it exists in saved editor path
                        if len(coord_list) > 2 and isinstance(coord_list[2], dict):
                            if coord_list[2].get("change_dir"):
                                node_copy["change_dir"] = True
                        reconstructed.append(node_copy)
                self.paths.append(reconstructed)
            self.active_path_idx = 0
            self.prev_path_idx = -1
            self.replace_idx = -1
            self.insert_idx = -1
            print(f"Successfully loaded Timetable {tt_idx} with {len(self.paths)} path(s).")
        else:
            print("Error: Old route lacks 'editor_paths' data. Cannot reconstruct GUI state perfectly.")

    def draw(self):
        self.screen.fill(COL_BG)
        
        map_rect = pygame.Rect(SIDEBAR_WIDTH, 0, self.width-SIDEBAR_WIDTH, self.height)
        self.screen.set_clip(map_rect)
        
        active_path = self.get_active_path()
        flat_inactive_nodes = [node for i, path in enumerate(self.paths) if i != self.active_path_idx for node in path]
        
        insert_node = active_path[self.insert_idx] if 0 <= self.insert_idx < len(active_path) else None
        replace_node = active_path[self.replace_idx] if 0 <= self.replace_idx < len(active_path) else None

        for y, line in enumerate(self.map_lines):
            for x, char in enumerate(line):
                if char == " ": continue
                
                screen_x = SIDEBAR_WIDTH + x * CELL_SIZE - self.camera_x
                screen_y = y * CELL_SIZE - self.camera_y
                if screen_x < SIDEBAR_WIDTH - CELL_SIZE or screen_x > self.width or screen_y < -CELL_SIZE or screen_y > self.height: continue
                
                rect = pygame.Rect(screen_x, screen_y, CELL_SIZE, CELL_SIZE)
                
                bg_color = COL_GRID
                if (x, y) in self.nodes:
                    ntype = self.nodes[(x, y)]["type"]
                    if ntype == "signal": bg_color = COL_SIGNAL
                    elif ntype == "platform": bg_color = COL_PLATFORM
                    elif ntype == "entrance_exit": bg_color = COL_ENTRANCE
                    
                if any(n["coord"] == (x, y) for n in flat_inactive_nodes):
                    bg_color = (180, 180, 150) 
                    
                if any(n["coord"] == (x, y) for n in active_path):
                    bg_color = COL_SELECTED
                    
                if insert_node and insert_node["coord"] == (x, y):
                    bg_color = COL_INSERT
                elif replace_node and replace_node["coord"] == (x, y):
                    bg_color = COL_REPLACE
                    
                pygame.draw.rect(self.screen, bg_color, rect)
                pygame.draw.rect(self.screen, (20,20,20), rect, 1)
                
                glyph = self.font_map.render(char, True, COL_TEXT if bg_color == COL_GRID else (0,0,0))
                self.screen.blit(glyph, glyph.get_rect(center=rect.center))
                
        def draw_path_lines(path_nodes, col_sig, col_sta, width):
            sig_nodes = [n for n in path_nodes if n["type"] == "signal"]
            sta_nodes = [n for n in path_nodes if n["type"] in ("platform", "entrance_exit")]
            
            for i in range(len(sig_nodes) - 1):
                c1, c2 = sig_nodes[i], sig_nodes[i+1]
                p1 = (SIDEBAR_WIDTH + c1["coord"][0]*CELL_SIZE - self.camera_x + CELL_SIZE//2, c1["coord"][1]*CELL_SIZE - self.camera_y + CELL_SIZE//2)
                p2 = (SIDEBAR_WIDTH + c2["coord"][0]*CELL_SIZE - self.camera_x + CELL_SIZE//2, c2["coord"][1]*CELL_SIZE - self.camera_y + CELL_SIZE//2)
                pygame.draw.line(self.screen, col_sig, p1, p2, width)
                
            for i in range(len(sta_nodes) - 1):
                c1, c2 = sta_nodes[i], sta_nodes[i+1]
                p1 = (SIDEBAR_WIDTH + c1["coord"][0]*CELL_SIZE - self.camera_x + CELL_SIZE//2, c1["coord"][1]*CELL_SIZE - self.camera_y + CELL_SIZE//2)
                p2 = (SIDEBAR_WIDTH + c2["coord"][0]*CELL_SIZE - self.camera_x + CELL_SIZE//2, c2["coord"][1]*CELL_SIZE - self.camera_y + CELL_SIZE//2)
                pygame.draw.line(self.screen, col_sta, p1, p2, width)

        for i, path in enumerate(self.paths):
            if i != self.active_path_idx:
                sig_col = COL_LINE_SIG if i == 0 else COL_LINE_SIG_ALT
                sta_col = COL_LINE_STA if i == 0 else COL_LINE_STA_ALT
                draw_path_lines(path, sig_col, sta_col, 2)

        if active_path:
            draw_path_lines(active_path, COL_LINE_SIG_EDIT, COL_LINE_STA_EDIT, 3)

        self.screen.set_clip(None)
        
        # --- Sidebar ---
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
        lbl_surf = self.font_ui.render("Direction", True, COL_TEXT)
        self.screen.blit(lbl_surf, (self.btn_direction.x, self.btn_direction.y - 20))
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
        
        pygame.draw.rect(self.screen, (100, 150, 255), self.btn_calculate, border_radius=4)
        self.screen.blit(self.font_ui.render("Needle Threader (Calculate Safe Spawns)", True, (0,0,0)), (self.btn_calculate.x + 20, self.btn_calculate.y + 10))
        
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

        # Node Operations
        pygame.draw.rect(self.screen, COL_INSERT, self.btn_insert_node, border_radius=4)
        self.screen.blit(self.font_small.render("+ Insert Node", True, (0,0,0)), (self.btn_insert_node.x + 15, self.btn_insert_node.y + 8))

        pygame.draw.rect(self.screen, (255, 100, 100), self.btn_del_node, border_radius=4)
        self.screen.blit(self.font_small.render("- Del Node", True, (0,0,0)), (self.btn_del_node.x + 20, self.btn_del_node.y + 8))

        # Path Tabs
        y_off = 395
        self.tab_rects = []
        tab_x = 10
        for i in range(len(self.paths)):
            if i == self.active_path_idx:
                color = COL_SELECTED 
            elif i == self.prev_path_idx:
                color = COL_PREV_SELECTED
            else:
                color = (100, 100, 100)
                
            txt = f"Path {i}" + ("(Prim)" if i == 0 else "")
            rect = pygame.Rect(tab_x, y_off, 90, 25)
            pygame.draw.rect(self.screen, color, rect, border_radius=4)
            self.screen.blit(self.font_small.render(txt, True, (0,0,0)), (rect.x + 5, rect.y + 5))
            self.tab_rects.append((rect, i))
            tab_x += 95
            if tab_x > 320:
                tab_x = 10
                y_off += 30

        y_off += 35
        inst_txt = "Select Node on Map/List to Replace. Map: Ctrl = Delete"
        self.screen.blit(self.font_small.render(inst_txt, True, (150,150,150)), (10, y_off))
        inst_txt2 = "Right-Click List Node = Toggle Reverse Direction [REV]"
        self.screen.blit(self.font_small.render(inst_txt2, True, (150,150,150)), (10, y_off + 20))
        
        y_off += 40
        self.node_list_rects = [] 
        
        lbl = self.font_ui.render(f"Nodes in Path {self.active_path_idx}:", True, COL_TEXT)
        self.screen.blit(lbl, (10, y_off))
        y_off += 25
        
        # --- NEW: List clipping area and scrolling application ---
        list_clip_rect = pygame.Rect(0, y_off, SIDEBAR_WIDTH, self.height - y_off)
        self.screen.set_clip(list_clip_rect)
        
        current_y = y_off - self.node_list_scroll_y
        
        for i, node in enumerate(active_path):
            if node["type"] == "signal":
                txt = f"{i+1}. Signal at {node['coord']}"
            else:
                plat_str = str(node['platform'])
                if plat_str.lower() in ["up", "down", "fast", "slow", "main", "relief"]:
                    display_plat = plat_str.title()
                else:
                    display_plat = f"P{plat_str}" if plat_str else ""
                txt = f"{i+1}. {node['type'].title().replace('_', ' ')}: {node['station']} {display_plat}".strip()
            
            if node.get("change_dir"):
                txt += " [REV]"
                
            color = COL_TEXT
            if i == self.replace_idx: color = COL_REPLACE
            elif i == self.insert_idx: color = COL_INSERT
            
            lbl = self.font_ui.render(txt, True, color)
            rect = pygame.Rect(10, current_y, 360, 22)
            self.screen.blit(lbl, (10, current_y))
            self.node_list_rects.append((rect, i))
            current_y += 25
            
        self.screen.set_clip(None) # Remove clip to not mess with subsequent draws

        pygame.display.flip()




    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    
                elif event.type == pygame.VIDEORESIZE:
                    self.width, self.height = event.w, event.h
                    self.screen = pygame.display.set_mode((self.width, self.height), pygame.RESIZABLE)
                    self._clamp_camera()
                    
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_z and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                        self.undo()
                        
                    # --- NEW: Hotkeys for Insert and Delete Node ---
                    inputs_active = any([self.input_load_tt.active, self.input_headcode.active, self.input_change_tt.active, self.input_spawns.active])
                    if not inputs_active:
                        if event.key == pygame.K_i: # Press 'I' for Insert Node
                            if self.replace_idx != -1:
                                self.insert_idx = self.replace_idx
                                self.replace_idx = -1
                        elif event.key == pygame.K_DELETE: # Press 'Delete' for Delete Node
                            active_path = self.get_active_path()
                            if active_path:
                                self.save_state()
                                if self.replace_idx != -1:
                                    active_path.pop(self.replace_idx)
                                    self.replace_idx = -1
                                elif self.insert_idx != -1:
                                    active_path.pop(self.insert_idx)
                                    self.insert_idx = -1
                                else:
                                    active_path.pop()
                        
                self.input_load_tt.handle_event(event)
                self.input_headcode.handle_event(event)
                self.input_change_tt.handle_event(event)
                self.input_spawns.handle_event(event)
                
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 4: # Mouse Wheel UP
                        if event.pos[0] <= SIDEBAR_WIDTH:
                            self.node_list_scroll_y = max(0, self.node_list_scroll_y - 30)
                        else:
                            if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                                self.camera_y -= 60
                            else:
                                self.camera_x -= 60
                            self._clamp_camera()
                    elif event.button == 5: # Mouse Wheel DOWN
                        if event.pos[0] <= SIDEBAR_WIDTH:
                            max_scroll = max(0, len(self.get_active_path()) * 25)
                            self.node_list_scroll_y = min(max_scroll, self.node_list_scroll_y + 30)
                        else:
                            if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                                self.camera_y += 60
                            else:
                                self.camera_x += 60
                            self._clamp_camera()
                        
                    elif event.pos[0] > SIDEBAR_WIDTH:
                        if event.button == 3: # Right click pan
                            self.panning = True
                            self.pan_start = event.pos
                            self.pan_start_camera = (self.camera_x, self.camera_y)
                        elif event.button == 1:
                            # 1. Map Clicks
                            gx, gy = self._screen_to_grid(event.pos)
                            if (gx, gy) in self.nodes:
                                node = self.nodes[(gx, gy)]
                                mods = pygame.key.get_mods()
                                ctrl = bool(mods & pygame.KMOD_CTRL)
                                active_path = self.get_active_path()
                                
                                node_coords = [n["coord"] for n in active_path]
                                
                                if node["coord"] in node_coords:
                                    existing_idx = node_coords.index(node["coord"])
                                    if ctrl:
                                        self.save_state()
                                        active_path.pop(existing_idx)
                                        self.replace_idx = -1
                                        self.insert_idx = -1
                                    else:
                                        self.replace_idx = existing_idx
                                        self.insert_idx = -1
                                else:
                                    if not ctrl:
                                        self.save_state() 
                                        node_copy = dict(node)
                                        if self.replace_idx != -1:
                                            active_path[self.replace_idx] = node_copy
                                            self.replace_idx = -1
                                        elif self.insert_idx != -1:
                                            active_path.insert(self.insert_idx + 1, node_copy)
                                            self.insert_idx += 1 
                                        else:
                                            active_path.append(node_copy)
                    else:
                        if event.button == 1:
                            # 2. Sidebar Left Clicks
                            if self.btn_prev_tt.collidepoint(event.pos): self._navigate_tt(-1)
                            elif self.btn_next_tt.collidepoint(event.pos): self._navigate_tt(1)
                            elif self.btn_load_tt.collidepoint(event.pos): self.load_existing_timetable()
                            elif self.btn_direction.collidepoint(event.pos):
                                self.direction_val = "left" if self.direction_val == "right" else "right"
                            elif self.btn_despawn.collidepoint(event.pos):
                                self.despawn = not self.despawn
                            
                            # Path Management
                            elif self.btn_new_path.collidepoint(event.pos):
                                self.save_state() 
                                self.prev_path_idx = self.active_path_idx
                                self.paths.append([])
                                self.active_path_idx = len(self.paths) - 1
                                self.replace_idx = -1
                                self.insert_idx = -1
                                self.node_list_scroll_y = 0
                            elif self.btn_clone_path.collidepoint(event.pos):
                                self.save_state() 
                                self.prev_path_idx = self.active_path_idx
                                self.paths.append([dict(n) for n in self.get_active_path()])
                                self.active_path_idx = len(self.paths) - 1
                                self.replace_idx = -1
                                self.insert_idx = -1
                                self.node_list_scroll_y = 0
                            elif self.btn_del_path.collidepoint(event.pos):
                                if len(self.paths) > 1:
                                    self.save_state() 
                                    self.paths.pop(self.active_path_idx)
                                    self.active_path_idx = max(0, self.active_path_idx - 1)
                                    self.prev_path_idx = -1
                                    self.replace_idx = -1
                                    self.insert_idx = -1
                                    self.node_list_scroll_y = 0
                            elif self.btn_clone_route.collidepoint(event.pos):
                                self.save_state()
                                self.input_load_tt.text = "NEW"
                                print("Cloned current route to NEW workspace. Ready to edit and Save As New.")
                                
                            elif self.btn_undo.collidepoint(event.pos):
                                self.undo()
                                
                            # Insert Node Logic
                            elif self.btn_insert_node.collidepoint(event.pos):
                                if self.replace_idx != -1:
                                    self.insert_idx = self.replace_idx
                                    self.replace_idx = -1
                                    
                            # Delete Node Logic
                            elif self.btn_del_node.collidepoint(event.pos):
                                active_path = self.get_active_path()
                                if active_path:
                                    self.save_state()
                                    if self.replace_idx != -1:
                                        active_path.pop(self.replace_idx)
                                        self.replace_idx = -1
                                    elif self.insert_idx != -1:
                                        active_path.pop(self.insert_idx)
                                        self.insert_idx = -1
                                    else:
                                        active_path.pop()

                            # Calculation and Save
                            elif self.btn_calculate.collidepoint(event.pos):
                                self.run_needle_threader()
                            elif self.btn_save_update.collidepoint(event.pos):
                                self.save_unified_data(is_new=False)
                            elif self.btn_save_new.collidepoint(event.pos):
                                self.save_unified_data(is_new=True)
                            else:
                                # --- Check Tabs (With drag preparation) ---
                                for rect, i in getattr(self, "tab_rects", []):
                                    if rect.collidepoint(event.pos):
                                        self.dragging_tab_idx = i
                                        if self.active_path_idx != i:
                                            self.prev_path_idx = self.active_path_idx
                                            self.active_path_idx = i
                                            self.replace_idx = -1
                                            self.insert_idx = -1
                                            self.node_list_scroll_y = 0
                                
                                # Check Node List Editing
                                if event.pos[1] > 400:
                                    for rect, i in getattr(self, "node_list_rects", []):
                                        if rect.collidepoint(event.pos):
                                            mods = pygame.key.get_mods()
                                            if mods & pygame.KMOD_SHIFT:
                                                self.insert_idx = i
                                                self.replace_idx = -1
                                            else:
                                                self.replace_idx = i
                                                self.insert_idx = -1
                        
                        elif event.button == 3:
                            # 3. Sidebar Right Clicks (For Reversing Direction Toggle)
                            if event.pos[1] > 400:
                                for rect, i in getattr(self, "node_list_rects", []):
                                    if rect.collidepoint(event.pos):
                                        node = self.get_active_path()[i]
                                        if node["type"] in ("platform", "entrance_exit"):
                                            self.save_state()
                                            node["change_dir"] = not node.get("change_dir", False)
                        
                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1:
                        # --- NEW: Drop Tab Logic for Swapping Paths ---
                        if getattr(self, "dragging_tab_idx", -1) != -1:
                            for rect, i in getattr(self, "tab_rects", []):
                                if rect.collidepoint(event.pos) and i != self.dragging_tab_idx:
                                    self.save_state()
                                    # Swap paths in the array
                                    self.paths[self.dragging_tab_idx], self.paths[i] = self.paths[i], self.paths[self.dragging_tab_idx]
                                    self.active_path_idx = i
                                    self.prev_path_idx = -1
                                    self.replace_idx = -1
                                    self.insert_idx = -1
                                    break
                            self.dragging_tab_idx = -1
                            
                    elif event.button == 3: 
                        self.panning = False
                        
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
        print("\n--- RUNNING NEEDLE THREADER (MULTI-LENGTH PATHS) ---")

        valid_paths = [p for p in self.paths if len(p) >= 2]
        if not valid_paths:
            print("Error: No valid paths to simulate! Please draw a path.")
            return

        print(f"Train Prefix: {self.input_headcode.text} | Direction: {self.direction_val}")
        schedule_path = JSON_PATH / f"{self.scenario}_ars_schedule.json"
        timetable_path = JSON_PATH / f"{self.scenario}_timetable.json"

        if not schedule_path.exists() or not timetable_path.exists():
            print("Error: Required JSON files not found!")
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

        ghost_footprints = []
        for path_index, path in enumerate(valid_paths):
            relative_second = 0
            footprint = []
            for i in range(len(path) - 1):
                curr_node = path[i]
                next_node = path[i+1]
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

                if next_node["type"] == "platform": relative_second += 30

            change_tt_str = self.input_change_tt.text.strip()
            if change_tt_str.isdigit():
                continued_path = get_continued_footprint(int(change_tt_str), relative_second)
                footprint.extend(continued_path)

            ghost_footprints.append(footprint)

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
            for start, end in safe_windows:
                if end - start < 120: continue
                st_h, st_m, st_s = start // 3600, (start % 3600) // 60, start % 60
                en_h, en_m, en_s = end // 3600, (end % 3600) // 60, end % 60
                en_h_display = 23 if en_h >= 24 else en_h
                en_m_display = 59 if en_h >= 24 else en_m
                en_s_display = 59 if en_h >= 24 else en_s
                print(f"Safe spawn: {st_h:02d}:{st_m:02d}:{st_s:02d}  to  {en_h_display:02d}:{en_m_display:02d}:{en_s_display:02d}")
        print("--------------------------\n")

    def save_unified_data(self, is_new=False):
        print("\n=== SAVING TIMETABLE AND ARS DATA ===")
        valid_paths = [p for p in self.paths if len(p) >= 2]
        if not valid_paths:
            print("Error: Need at least a start point and one stop/signal.")
            return

        change_tt_text = self.input_change_tt.text.strip()
        if not self.despawn and not change_tt_text:
            print("Error: You must select 'Despawn' or input a 'Change TT Index' before saving!")
            return

        spawns_raw = [t.strip() for t in self.input_spawns.text.split(",") if t.strip()]

        timetable_path = JSON_PATH / f"{self.scenario}_timetable.json"
        ars_path = JSON_PATH / f"{self.scenario}_ars_routes.json"

        tt_data = []
        if timetable_path.exists():
            try: tt_data = json.loads(timetable_path.read_text(encoding="utf-8"))
            except Exception: pass

        loaded_idx_str = self.input_load_tt.text.strip()

        if is_new or loaded_idx_str == "NEW":
            new_index = max([t.get("index", 0) for t in tt_data], default=0) + 1
        else:
            if loaded_idx_str.isdigit():
                new_index = int(loaded_idx_str)
                tt_data = [t for t in tt_data if t.get("index") != new_index]
            else:
                new_index = max([t.get("index", 0) for t in tt_data], default=0) + 1

        primary_path = valid_paths[0]
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

                if node.get("change_dir"):
                    stop_entry["change_direction"] = True

                stops.append(stop_entry)

        if stops:
            if self.despawn:
                stops[-1]["despawn"] = True
            elif change_tt_text:
                try: stops[-1]["change_timetable"] = int(change_tt_text)
                except ValueError: pass

        new_tt_entry = {
            "index": new_index,
            "headcode_prefix": self.input_headcode.text.strip().upper(),
            "start_location": start_location,
            "direction": self.direction_val,
            "stops": stops,
            "spawn_times": spawns_raw
        }

        tt_data.append(new_tt_entry)

        ars_data = []
        if ars_path.exists():
            try:
                raw_payload = json.loads(ars_path.read_text(encoding="utf-8"))
                if isinstance(raw_payload, dict): ars_data = raw_payload.get("routes", [])
                elif isinstance(raw_payload, list): ars_data = raw_payload
            except Exception: pass

        if not is_new and loaded_idx_str != "NEW":
            ars_data = [r for r in ars_data if r.get("timetable_index") != new_index]

        signal_paths = []
        editor_paths_cache = []

        for path in valid_paths:
            ep_path = []
            for n in path:
                n_data = [n["coord"][0], n["coord"][1]]
                if n.get("change_dir"):
                    n_data.append({"change_dir": True})
                ep_path.append(n_data)
            editor_paths_cache.append(ep_path)

            sigs = [list(n["coord"]) for n in path if n["type"] == "signal"]
            if sigs and sigs not in signal_paths:
                signal_paths.append(sigs)

        if not signal_paths:
            print("Error: No signals selected. Cannot build ARS route.")
            return

        new_ars_entry = {
            "name": str(new_index),
            "timetable_index": new_index,
            "signals": signal_paths[0],
            "signal_paths": signal_paths,
            "editor_paths": editor_paths_cache
        }

        ars_data.append(new_ars_entry)
        tt_data.sort(key=lambda x: x.get("index", 999))
        ars_data.sort(key=lambda x: x.get("timetable_index", 999))

        try: timetable_path.write_text(json.dumps(tt_data, indent=4), encoding="utf-8")
        except Exception as e: print(f"CRITICAL ERROR saving Timetable: {e}")

        try: ars_path.write_text(json.dumps({"routes": ars_data}, indent=4), encoding="utf-8")
        except Exception as e: print(f"CRITICAL ERROR saving ARS: {e}")

        print(f"SUCCESS! Timetable Index {new_index} saved.")
        self.input_load_tt.text = str(new_index)
        self._refresh_available_tts()

if __name__ == "__main__":
    scenario = choose_scenario()
    if scenario:
        app = UnifiedBuilder(scenario)
        app.run()
