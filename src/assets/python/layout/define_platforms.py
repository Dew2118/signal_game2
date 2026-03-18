import pygame
import json

class DefinePlatforms:
    def __init__(self, layout_file):
        pygame.init()
        self.SCREEN_WIDTH, self.SCREEN_HEIGHT = 1000, 750
        self.FONT_PATH = "../../fonts/S-box.ttf"
        self.FONT_SIZE = 20
        self.BLACK = (0, 0, 0)
        self.GRAY = (180, 180, 180)
        self.YELLOW = (255, 255, 0)
        self.WHITE = (255, 255, 255)
        self.RED = (255, 0, 0)

        self.scroll_x = 0
        self.scroll_y = 0
        self.scroll_speed = 20
        self.line_height = 16
        self.layout_file = "../../../../" + layout_file
        self.layout_text = self.read_layout()

        self.segments = self.extract_segments(self.layout_text)
        self.portals = self.extract_portals(self.layout_text)  # ✅ NEW

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

    def read_layout(self):
        with open(self.layout_file, "r", encoding='utf-8') as file:
            return file.read()

    def extract_segments(self, text):
        lines = text.splitlines()
        segments = []

        for y, line in enumerate(lines):
            x = 0
            while x < len(line):
                char = line[x]

                if char == '¯':
                    start_x = x
                    while x < len(line) and (line[x] == '¯' or line[x].isdigit()):
                        x += 1
                    end_x = x - 1
                    segments.append({
                        'left': (start_x, y),
                        'right': (end_x, y),
                        'type': 'platform'
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

    def extract_portals(self, text):
        from collections import defaultdict

        lines = text.splitlines()
        height = len(lines)
        width = max(len(line) for line in lines)

        grid = [line.ljust(width) for line in lines]

        visited = set()
        portal_columns = []

        # =========================
        # STEP 1: DETECT PORTALS
        # =========================
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

                        # must match top letter
                        if end_letter != letter:
                            continue

                        if middle:
                            portal_columns.append({
                                "letter": letter,
                                "x": x,
                                "middle": middle
                            })

                    visited.add((x, start_y))
                    if y < height:
                        visited.add((x, y))
                else:
                    y += 1
        print(f"Detected portal columns: {portal_columns}")
        # =========================
        # STEP 2: GROUP BY LETTER
        # =========================
        grouped = defaultdict(list)
        for portal in portal_columns:
            grouped[portal["letter"]].append(portal)

        portals = []

        # =========================
        # STEP 3: PAIR PORTALS
        # =========================
        for letter, group in grouped.items():
            if len(group) != 2:
                continue  # skip invalid sets

            p1, p2 = group

            pairs = []
            directions = []
            print(f"Processing portal {letter} with groups: {p1}, {p2}")
            # =========================
            # STEP 4: MATCH BY INDEX
            # =========================
            for (x1, y1), (x2, y2) in zip(p1["middle"], p2["middle"]):
                print(f"Matching points: {(x1, y1)} <-> {(x2, y2)}")
                def track_side(x, y):
                    left = x - 1 >= 0 and grid[y][x - 1] == 'a'
                    right = x + 1 < width and grid[y][x + 1] == 'a'

                    if left:
                        return "left"
                    if right:
                        return "right"
                    return None

                side1 = track_side(x1, y1)
                side2 = track_side(x2, y2)

                # only keep valid track connections
                if side1 and side2:
                    pairs.append([[x1, y1], [x2, y2]])

                    if side1 != side2:
                        directions.append("same")
                    else:
                        directions.append("opposite")

            # =========================
            # STEP 5: SAVE RESULT
            # =========================
            for pair, direction in zip(pairs, directions):
                portals.append([
                    pair[0],   # [x1, y1]
                    pair[1],   # [x2, y2]
                    direction  # "same" or "opposite"
                ])

        return portals

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
                    char = event.unicode
                    if char.isprintable():
                        self.current_input += char

            elif event.type == pygame.MOUSEWHEEL:
                mods = pygame.key.get_mods()
                shift_held = mods & pygame.KMOD_SHIFT

                if shift_held:
                    self.scroll_x = max(0, min(self.scroll_x - event.y * self.scroll_speed, w - self.SCREEN_WIDTH))
                else:
                    self.scroll_y = max(0, min(self.scroll_y - event.y * self.scroll_speed, h - self.SCREEN_HEIGHT))

    def process_input(self):
        if self.input_mode == "station":
            self.current_segment_data['station'] = self.current_input
            self.current_input = ""
            self.input_mode = "platform"

        elif self.input_mode == "platform":
            self.current_segment_data['platform'] = self.current_input
            self.current_input = ""

            segment = self.segments[self.current_index]
            segment.update(self.current_segment_data)
            self.annotated_segments.append(segment)

            self.current_index += 1

            if self.current_index < len(self.segments):
                next_segment = self.segments[self.current_index]
                self.highlight_coords = {next_segment['left'], next_segment['right']}

                self.input_mode = "station"
                self.current_segment_data = {}
            else:
                self.highlight_coords = set()
                self.input_mode = None
                print("All segments annotated.")
                self.save_to_json()

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
                char_surf = self.font.render(char, True, color)
                surf.blit(char_surf, (x * char_width, y * self.line_height))
        return surf, surface_width, surface_height

    def draw_input_box(self):
        if self.current_index < len(self.segments):
            seg_type = self.segments[self.current_index].get('type', 'segment').upper()
            prompt = f"ENTER {seg_type} {self.input_mode.upper()} NAME: {self.current_input}"
            input_surf = self.font.render(prompt, True, self.WHITE)
            pygame.draw.rect(self.screen, self.RED, (0, self.SCREEN_HEIGHT - 30, self.SCREEN_WIDTH, 30))
            self.screen.blit(input_surf, (10, self.SCREEN_HEIGHT - 28))

    def save_to_json(self, filename="zone_10_annotated_segments.json"):
        data = {
            "segments": self.annotated_segments,
            "portals": self.portals  # ✅ INCLUDED
        }

        with open("../../../json/" + filename, "w") as f:
            json.dump(data, f, indent=4)

        print(f"Saved annotated segments + portals to {filename}")

    def run(self):
        clock = pygame.time.Clock()
        while self.running:
            temp_highlight = None
            if self.current_index < len(self.segments):
                seg = self.segments[self.current_index]
                temp_highlight = {seg['left'], seg['right']}

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

        print("\nFinal Annotated Segments:")
        for seg in self.annotated_segments:
            print(seg)

        print("\nDetected Portals:")
        for portal in self.portals:
            print(portal)

        pygame.quit()


if __name__ == "__main__":
    app = DefinePlatforms("zone_10_map.txt")
    app.run()