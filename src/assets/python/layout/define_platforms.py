import pygame
import json
import re

class DefinePlatforms:
    def __init__(self, layout_file):
        pygame.init()
        self.SCREEN_WIDTH, self.SCREEN_HEIGHT = 1000, 750
        self.FONT_PATH = "../../fonts/S-box.ttf"
        self.FONT_SIZE = 20
        self.BLACK = (0, 0, 0)
        self.GRAY = (180, 180, 180)
        self.WHITE = (255, 255, 255)
        self.RED = (255, 0, 0)

        self.scroll_x = 0
        self.scroll_y = 0
        self.scroll_speed = 70
        self.line_height = 16
        self.layout_file = "../../../../" + layout_file
        self.layout_text = self.read_layout()

        self.segments = self.extract_segments(self.layout_text)
        self.portals = self.extract_portals(self.layout_text)

        self.annotated_segments = []
        self.highlight_coords = set()

        self.font = pygame.font.Font(self.FONT_PATH, self.FONT_SIZE)
        self.screen = pygame.display.set_mode((self.SCREEN_WIDTH, self.SCREEN_HEIGHT))
        pygame.display.set_caption("Timetable Segment Highlighter")

        self.current_index = 0
        self.running = True
        self.input_mode = "station"
        self.current_input = ""
        self.current_segment_data = {}
        self.prefilled_current_segment = False

    # -------------------------
    # FILE READING
    # -------------------------
    def read_layout(self):
        with open(self.layout_file, "r", encoding='utf-8') as file:
            return file.read()

    # -------------------------
    # STATION DETECTION HELPERS
    # -------------------------
    def extract_station_from_line(self, row, x_center, platform_left, platform_right, y, radius=20):
        width = len(row)
        potential_stations = []

        # Split by 5 or more spaces to detect separate stations
        parts = row.split("      ")
        for part in parts:
            part = part.strip()  # Remove leading/trailing whitespace

            # Validate that the part contains only capitalized letters, dashes, and a single space between words
            if self.is_valid_station_name(part):
                left = row.find(part)
                right = left + len(part) - 1

                # Check if the station is within the platform bounds
                if right >= platform_left and left <= platform_right:
                    potential_stations.append({
                        "name": part,
                        "start": (left, y),
                        "end": (right, y)
                    })

        return potential_stations

    def is_valid_station_name(self, name):
        """
        Validate the station name:
        - Only capitalized letters (A-Z), dash ("-"), and one space allowed between words.
        """
        # The regex will now:
        # 1. Match capital letters at the beginning.
        # 2. Allow multiple dashes between letters.
        # 3. Allow multiple spaces between words, but no consecutive spaces.
        # 4. Allow the station name to end with letters or dashes.
        pattern = r'^[A-Z]+(?:-[A-Z]+)*(?: [A-Z]+(?:-[A-Z]+)*)*$'
        
        # Return true if the name matches the pattern
        return bool(re.match(pattern, name))


    def extract_station_name(self, grid, x_center, y_start, platform_left, platform_right, direction, radius):
        height = len(grid)
        best_station = None
        best_overlap = 0

        y = y_start
        while 0 <= y < height:
            row = grid[y]
            potential_stations = self.extract_station_from_line(row, x_center, platform_left, platform_right, y, radius)
            for station in potential_stations:
                # Calculate how much the station overlaps with the platform
                station_start, station_end = station["start"][0], station["end"][0]
                overlap = max(0, min(station_end, platform_right) - max(station_start, platform_left))

                if overlap > best_overlap:
                    best_overlap = overlap
                    best_station = station

            y += direction

        return best_station

    # -------------------------
    # SEGMENT EXTRACTION
    # -------------------------
    def extract_segments(self, text):
        lines = text.splitlines()
        width = max(len(line) for line in lines)
        grid = [line.ljust(width) for line in lines]

        segments = []
        for y, line in enumerate(grid):
            x = 0
            while x < len(line):
                char = line[x]

                if char == '¯':
                    start_x = x
                    digits = ""

                    while x < len(line) and (line[x] == '¯' or line[x].isdigit()):
                        if line[x].isdigit():
                            digits += line[x]
                        x += 1

                    end_x = x - 1
                    center_x = (start_x + end_x) // 2
                    platform_width = end_x - start_x
                    radius = max(10, platform_width)
                    platform_left, platform_right = start_x, end_x

                    # Detect station
                    name_up = self.extract_station_name(
                        grid, center_x, y - 1, platform_left, platform_right, -1, radius
                    )
                    name_down = self.extract_station_name(
                        grid, center_x, y + 1, platform_left, platform_right, 1, radius
                    )

                    station_data = name_up if name_up else name_down

                    if station_data:
                        print(
                            f"[AUTO-DETECT] Station: '{station_data['name']}' | "
                            f"Station coords: {station_data['start']} -> {station_data['end']} | "
                            f"Platform coords: ({start_x}, {y}) -> ({end_x}, {y})"
                        )

                    # Set prefill_station to "" if no station is found (leave it blank)
                    prefill_station = station_data["name"] if station_data else ""
                    prefill_platform = digits if digits else ""

                    segments.append({
                        'left': (start_x, y),
                        'right': (end_x, y),
                        'type': 'platform',
                        'prefill_station': prefill_station,
                        'prefill_platform': prefill_platform
                    })

                elif char == 'x':
                    segments.append({
                        'left': (x, y),
                        'right': (x, y),
                        'type': 'entrance_exit'
                    })
                    x += 1
                else:
                    x += 1

        return segments

    # -------------------------
    # PORTALS
    # -------------------------
    def extract_portals(self, text):
        from collections import defaultdict

        lines = text.splitlines()
        height = len(lines)
        width = max(len(line) for line in lines)
        grid = [line.ljust(width) for line in lines]

        visited = set()
        portal_columns = []

        for x in range(width):
            y = 0
            while y < height:
                if grid[y][x] in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" and (x, y) not in visited:
                    start_y = y
                    letter = grid[y][x]
                    y += 1
                    middle = []
                    while y < height and grid[y][x] == '÷':
                        middle.append((x, y))
                        visited.add((x, y))
                        y += 1
                    if y < height and grid[y][x] in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                        end_letter = grid[y][x]
                        if end_letter != letter:
                            continue
                        if middle:
                            portal_columns.append({"letter": letter, "x": x, "middle": middle})
                    visited.add((x, start_y))
                    if y < height:
                        visited.add((x, y))
                else:
                    y += 1

        grouped = defaultdict(list)
        for portal in portal_columns:
            grouped[portal["letter"]].append(portal)

        portals = []
        for letter, group in grouped.items():
            if len(group) != 2:
                continue
            p1, p2 = group
            for (x1, y1), (x2, y2) in zip(p1["middle"], p2["middle"]):
                def track_side(x, y):
                    left = x - 1 >= 0 and grid[y][x - 1] == 'a'
                    right = x + 1 < width and grid[y][x + 1] == 'a'
                    if left: return "left"
                    if right: return "right"
                    return None

                side1 = track_side(x1, y1)
                side2 = track_side(x2, y2)

                if side1 and side2:
                    direction = "same" if side1 != side2 else "opposite"
                    portals.append([[x1, y1], [x2, y2], direction])

        return portals

    # -------------------------
    # INPUT HANDLING
    # -------------------------
    def handle_events(self, w, h):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_RETURN:
                    self.process_input()
                elif event.key == pygame.K_BACKSPACE:
                    self.current_input = self.current_input[:-1]
                else:
                    if event.unicode.isprintable():
                        self.current_input += event.unicode
            elif event.type == pygame.MOUSEWHEEL:
                mods = pygame.key.get_mods()
                shift_held = mods & pygame.KMOD_SHIFT
                if shift_held:
                    self.scroll_y = max(0, min(self.scroll_y - event.y * self.scroll_speed, h - self.SCREEN_HEIGHT))
                else:
                    self.scroll_x = max(0, min(self.scroll_x - event.y * self.scroll_speed, w - self.SCREEN_WIDTH))

        # Continuous backspace
        keys = pygame.key.get_pressed()
        if keys[pygame.K_BACKSPACE]:
            self.current_input = self.current_input[:-1]
            pygame.time.delay(150)

    def process_input(self):
        if self.current_index >= len(self.segments):
            return

        segment = self.segments[self.current_index]

        if self.input_mode == "station":
            self.current_segment_data['station'] = self.current_input
            self.current_input = segment.get('prefill_platform', "")
            self.input_mode = "platform"
            self.prefilled_current_segment = False

        elif self.input_mode == "platform":
            self.current_segment_data['platform'] = self.current_input
            self.current_input = ""
            self.current_index += 1
            segment.update(self.current_segment_data)

            self.annotated_segments.append({
                "left": segment['left'],
                "right": segment['right'],
                "type": segment['type'],
                "station": segment['station'],
                "platform": segment['platform']
            })

            if self.current_index < len(self.segments):
                next_segment = self.segments[self.current_index]
                self.highlight_coords = {next_segment['left'], next_segment['right']}
                self.input_mode = "station"
                self.current_segment_data = {}
                self.prefilled_current_segment = False
            else:
                self.highlight_coords = set()
                self.input_mode = None
                print("All segments annotated.")
                self.save_to_json()

    # -------------------------
    # RENDERING + MAIN LOOP unchanged
    # -------------------------
    def render_text(self, temp_highlight=None):
        lines = self.layout_text.splitlines()
        char_width = self.font.size('M')[0]
        surface_width = char_width * max(len(line) for line in lines)
        surface_height = self.line_height * len(lines)

        surf = pygame.Surface((surface_width, surface_height))
        surf.fill(self.BLACK)

        for y, line in enumerate(lines):
            for x, char in enumerate(line):
                color = self.GRAY
                if (x, y) in self.highlight_coords or (temp_highlight and (x, y) in temp_highlight):
                    color = self.RED
                surf.blit(self.font.render(char, True, color), (x * char_width, y * self.line_height))

        return surf, surface_width, surface_height

    def draw_input_box(self):
        if self.current_index < len(self.segments) and self.input_mode:
            prompt = f"ENTER {self.input_mode.upper()}: {self.current_input}"
            pygame.draw.rect(self.screen, self.RED, (0, self.SCREEN_HEIGHT - 30, self.SCREEN_WIDTH, 30))
            self.screen.blit(self.font.render(prompt, True, self.WHITE), (10, self.SCREEN_HEIGHT - 28))

    def save_to_json(self, filename="dovedale_annotated_segments.json"):
        with open("../../../json/" + filename, "w") as f:
            json.dump({
                "segments": self.annotated_segments,
                "portals": self.portals
            }, f, indent=4)
        print(f"Saved to {filename}")

    def run(self):
        clock = pygame.time.Clock()
        while self.running:
            temp_highlight = None

            if self.current_index < len(self.segments):
                seg = self.segments[self.current_index]
                temp_highlight = {seg['left'], seg['right']}

                if self.input_mode == "station" and not self.prefilled_current_segment and not self.current_input:
                    self.current_input = seg.get("prefill_station", "")
                    if self.current_input:
                        self.prefilled_current_segment = True
                elif self.input_mode == "platform" and not self.prefilled_current_segment and not self.current_input:
                    self.current_input = seg.get("prefill_platform", "")
                    if self.current_input:
                        self.prefilled_current_segment = True

                x_center = (seg['left'][0] + seg['right'][0]) // 2
                y_center = (seg['left'][1] + seg['right'][1]) // 2
                char_width = self.font.size('M')[0]

                self.scroll_x = max(0, x_center * char_width - self.SCREEN_WIDTH // 2)
                self.scroll_y = max(0, y_center * self.line_height - self.SCREEN_HEIGHT // 2)

            surface, w, h = self.render_text(temp_highlight)
            self.handle_events(w, h)

            self.screen.fill(self.BLACK)
            self.screen.blit(surface, (-self.scroll_x, -self.scroll_y))

            if self.current_index < len(self.segments):
                self.draw_input_box()
            else:
                msg = "ALL SEGMENTS ANNOTATED, PLEASE PRESS ESC TO EXIT."
                done_surf = self.font.render(msg, True, self.RED)
                self.screen.blit(done_surf, (10, self.SCREEN_HEIGHT - 28))

            pygame.display.flip()
            clock.tick(60)

        pygame.quit()


if __name__ == "__main__":
    app = DefinePlatforms("dovedale_map.txt")
    app.run()