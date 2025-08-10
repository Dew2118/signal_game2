import pygame
import json

class DefinePlatforms:
    def __init__(self, layout_file="test.txt"):
        pygame.init()
        self.SCREEN_WIDTH, self.SCREEN_HEIGHT = 1000, 750
        self.FONT_PATH = "S-box.ttf"
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
        self.layout_file = layout_file
        self.layout_text = self.read_layout()
        self.segments = self.extract_segments(self.layout_text)
        self.annotated_segments = []
        self.highlight_coords = set()

        self.font = pygame.font.Font(self.FONT_PATH, self.FONT_SIZE)
        self.screen = pygame.display.set_mode((self.SCREEN_WIDTH, self.SCREEN_HEIGHT))
        pygame.display.set_caption("Timetable Segment Highlighter")

        self.current_index = 0
        self.running = True
        self.input_mode = "station"  # "station" or "platform"
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
                    while x < len(line) and line[x] == '¯':
                        x += 1
                    end_x = x - 1
                    segments.append({'left': (start_x, y), 'right': (end_x, y), 'type': 'platform'})
                elif char == 'x':
                    # single 'x' detected
                    segments.append({'left': (x, y), 'right': (x, y), 'type': 'entrance_exit'})
                    x += 1
                else:
                    x += 1
        return segments


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
                    # Horizontal scroll
                    self.scroll_x = max(0, min(self.scroll_x - event.y * self.scroll_speed, w - self.SCREEN_WIDTH))
                else:
                    # Vertical scroll
                    self.scroll_y = max(0, min(self.scroll_y - event.y * self.scroll_speed, h - self.SCREEN_HEIGHT))


    def process_input(self):
        if self.input_mode == "station":
            self.current_segment_data['station'] = self.current_input
            self.current_input = ""
            self.input_mode = "platform"

        elif self.input_mode == "platform":
            self.current_segment_data['platform'] = self.current_input
            self.current_input = ""

            # Save the current segment data
            segment = self.segments[self.current_index]
            segment.update(self.current_segment_data)
            self.annotated_segments.append(segment)

            # Move to the next segment
            self.current_index += 1

            if self.current_index < len(self.segments):
                # Update highlight coords to new segment
                next_segment = self.segments[self.current_index]
                self.highlight_coords = {next_segment['left'], next_segment['right']}

                # Reset for next input
                self.input_mode = "station"
                self.current_segment_data = {}
            else:
                # No more segments
                self.highlight_coords = set()
                self.input_mode = None
                print("All segments annotated.")
                self.save_to_json()


    def render_text(self, temp_highlight=None):
        lines = self.layout_text.splitlines()
        line_height = self.line_height
        char_width = self.font.size('M')[0]
        surface_width = char_width * max(len(line) for line in lines)
        surface_height = line_height * len(lines)

        surf = pygame.Surface((surface_width, surface_height))
        surf.fill(self.BLACK)

        for y, line in enumerate(lines):
            for x, char in enumerate(line):
                color = self.GRAY
                if (x, y) in self.highlight_coords or (temp_highlight and (x, y) in temp_highlight):
                    color = self.RED
                char_surf = self.font.render(char, True, color)
                surf.blit(char_surf, (x * char_width, y * line_height))
        return surf, surface_width, surface_height

    def draw_input_box(self):
        if self.current_index < len(self.segments):
            seg_type = self.segments[self.current_index].get('type', 'segment').upper()
            prompt = f"ENTER {seg_type} {self.input_mode.upper()} NAME: {self.current_input}"
            input_surf = self.font.render(prompt, True, self.WHITE)
            pygame.draw.rect(self.screen, self.RED, (0, self.SCREEN_HEIGHT - 30, self.SCREEN_WIDTH, 30))
            self.screen.blit(input_surf, (10, self.SCREEN_HEIGHT - 28))

    def save_to_json(self, filename="annotated_segments.json"):
        with open(filename, "w") as f:
            json.dump(self.annotated_segments, f, indent=4)
        print(f"Saved annotated segments to {filename}")

    def run(self):
        clock = pygame.time.Clock()
        while self.running:
            # Prepare highlight
            temp_highlight = None
            if self.current_index < len(self.segments):
                seg = self.segments[self.current_index]
                temp_highlight = {seg['left'], seg['right']}

            # Render layout
            surface, w, h = self.render_text(temp_highlight)
            self.handle_events(w, h)

            # --- draw everything ---
            self.screen.fill(self.BLACK)
            self.screen.blit(surface, (-self.scroll_x, -self.scroll_y))  # layout

            # ✅ draw input bar LAST
            if self.current_index < len(self.segments):
                self.draw_input_box()
            else:
                msg = "ALL SEGMENTS ANNOTATED, PLEASE PRESS ESC TO EXIT."
                done_surf = self.font.render(msg, True, self.RED)
                self.screen.blit(done_surf, (10, self.SCREEN_HEIGHT - 28))

            pygame.display.flip()
            clock.tick(60)

        # Exit log
        print("\nFinal Annotated Segments:")
        for seg in self.annotated_segments:
            print(seg)
        pygame.quit()


if __name__ == "__main__":
    app = DefinePlatforms("test.txt")
    app.run()
