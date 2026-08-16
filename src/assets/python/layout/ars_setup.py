import itertools
import json
import sys
from pathlib import Path

import pygame

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.assets.python.layout.ars import save_ars_routes

# NOTE: folder is "fonts" (plural), not "font".
FONT_PATH = PROJECT_ROOT / "src" / "assets" / "fonts" / "S-box.ttf"

MANUAL_SIGNAL_CHARS = {"à", "ã", "â", "á"}
AUTOMATIC_SIGNAL_CHARS = {"ø", "û", "ù", "ú", "©"}
ALL_SELECTABLE_SIGNALS = (
    MANUAL_SIGNAL_CHARS
    | AUTOMATIC_SIGNAL_CHARS
)

# Colors
COL_BG = (17, 17, 17)
COL_DEFAULT_CELL = (23, 23, 23)
COL_DEFAULT_TEXT = (223, 230, 240)
COL_MANUAL = (118, 169, 255)
COL_AUTOMATIC = (111, 201, 255)
COL_SIGNAL_TEXT = (0, 26, 57)
COL_CANDIDATE = (247, 209, 84)
COL_SELECTED = (107, 211, 139)
COL_SELECTED_ALT = (183, 232, 120)
COL_GRID_LINE = (43, 43, 43)
COL_ROUTE_LINE = (0, 255, 0)
COL_ROUTE_LINE_ALT = (150, 220, 90)
COL_SIDEBAR_BG = (29, 29, 29)
COL_PANEL_TEXT = (240, 240, 240)
COL_LIST_BG = (16, 16, 16)
COL_LIST_SEL = (60, 90, 60)
COL_BUTTON = (60, 60, 60)
COL_BUTTON_HOVER = (85, 85, 85)
COL_INPUT_BG = (10, 10, 10)
COL_INPUT_ACTIVE = (40, 40, 60)

CELL_SIZE = 16
SIDEBAR_WIDTH = 300
TOPBAR_HEIGHT = 90
STATUS_HEIGHT = 26


def load_font(
    size: int,
    bold: bool = False,
    custom: bool = False,
) -> pygame.font.Font:
    """Load a font for use in the app."""

    if custom:
        if FONT_PATH.exists():
            font = pygame.font.Font(
                str(FONT_PATH),
                size,
            )
        else:
            font = pygame.font.Font(
                None,
                size,
            )

        font.set_bold(bold)
        return font

    font = pygame.font.Font(None, size)
    font.set_bold(bold)
    return font


def load_scenario_data(map_path: Path):
    scenario = map_path.stem.replace("_map", "")

    timetable_path = (
        PROJECT_ROOT
        / "src"
        / "json"
        / f"{scenario}_timetable.json"
    )

    annotated_path = (
        PROJECT_ROOT
        / "src"
        / "json"
        / f"{scenario}_annotated_segments.json"
    )

    timetable = []

    if timetable_path.exists():
        with timetable_path.open(
            "r",
            encoding="utf-8",
        ) as handle:
            timetable = json.load(handle)

    annotated_segments = []

    if annotated_path.exists():
        with annotated_path.open(
            "r",
            encoding="utf-8",
        ) as handle:
            payload = json.load(handle)

            annotated_segments = (
                payload.get("segments", [])
                if isinstance(payload, dict)
                else payload
            )

    return (
        scenario,
        timetable,
        annotated_segments,
    )


def candidate_coords_for_station(
    annotated_segments,
    station_name,
    platform_name=None,
):
    points = set()

    for segment in annotated_segments or []:
        if segment.get("station") != station_name:
            continue

        if segment.get("type") not in {
            "platform",
            "entrance_exit",
        }:
            continue

        if platform_name:
            platform_value = str(
                segment.get("platform", "")
            ).strip()

            if (
                platform_value
                and platform_value != str(platform_name)
            ):
                continue

        for key in ("left", "right"):
            point = segment.get(key)

            if point is not None:
                try:
                    points.add(
                        (
                            int(point[0]),
                            int(point[1]),
                        )
                    )
                except (
                    TypeError,
                    ValueError,
                    IndexError,
                ):
                    pass

    return points


def build_route_candidates(
    timetable,
    annotated_segments,
):
    candidates = []

    # Enumerate the RAW timetable list so timetable_index
    # always corresponds to the real position in the timetable JSON.
    for timetable_index, entry in enumerate(
        timetable or []
    ):
        prefix = str(
            entry.get("headcode_prefix", "")
        ).strip()

        if not prefix:
            continue

        stations = []
        coords = set()

        for stop in entry.get("stops", []):
            station = stop.get("station")

            if not station:
                continue

            stations.append(station)

            platform = stop.get("platform")

            if platform and str(platform).strip():
                coords |= candidate_coords_for_station(
                    annotated_segments,
                    station,
                    str(platform).strip(),
                )
            else:
                coords |= candidate_coords_for_station(
                    annotated_segments,
                    station,
                )

        if not stations:
            continue

        candidates.append(
            {
                "prefix": prefix,
                "stations": stations,
                "coords": sorted(coords),
                "timetable_index": timetable_index,
            }
        )

    return candidates


class Button:
    def __init__(
        self,
        rect,
        label,
        font,
    ):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.font = font

    def draw(
        self,
        surface,
        mouse_pos,
    ):
        hovered = self.rect.collidepoint(mouse_pos)

        pygame.draw.rect(
            surface,
            (
                COL_BUTTON_HOVER
                if hovered
                else COL_BUTTON
            ),
            self.rect,
            border_radius=4,
        )

        text = self.font.render(
            self.label,
            True,
            COL_PANEL_TEXT,
        )

        surface.blit(
            text,
            text.get_rect(
                center=self.rect.center
            ),
        )

    def clicked(self, pos):
        return self.rect.collidepoint(pos)


class ARSRouteBuilder:
    def __init__(
        self,
        map_path: Path,
        screen,
        clock,
    ):
        self.map_path = Path(map_path)

        self.lines = self.map_path.read_text(
            encoding="utf-8"
        ).splitlines()

        (
            self.scenario,
            self.timetable,
            self.annotated_segments,
        ) = load_scenario_data(
            self.map_path
        )

        self.route_candidates = build_route_candidates(
            self.timetable,
            self.annotated_segments,
        )

        self.selected_route_index = (
            0
            if self.route_candidates
            else None
        )

        # Current route being edited.
        #
        # Example:
        #
        # [
        #     [(1, 2)],
        #     [(3, 4), (3, 5)],
        #     [(6, 7)],
        # ]
        #
        # The first item in each step is the primary signal.
        # Additional items are alternatives.
        self.route_steps = []

        # All saved routes loaded from the ARS JSON.
        self.routes = []

        self.signal_coords = (
            self._collect_signal_coords()
        )

        self.screen = screen
        self.clock = clock

        self.width, self.height = screen.get_size()

        # Only the map content uses S-box.ttf.
        self.font_map = load_font(
            13,
            bold=True,
            custom=True,
        )

        self.font_ui = load_font(
            15,
            custom=False,
        )

        self.font_ui_bold = load_font(
            15,
            bold=True,
            custom=False,
        )

        self.font_small = load_font(
            12,
            custom=False,
        )

        self.status_text = (
            "Click: extend/combine route. "
            "Shift+Click: add alternate connected "
            "from the previous signal. "
            "Ctrl+Click: remove. "
            "Scroll: left/right, "
            "Shift+Scroll: up/down."
        )

        self.camera_x = 0
        self.camera_y = 0

        self.map_area_rect = pygame.Rect(
            SIDEBAR_WIDTH,
            TOPBAR_HEIGHT,
            self.width - SIDEBAR_WIDTH,
            self.height
            - TOPBAR_HEIGHT
            - STATUS_HEIGHT,
        )

        self.panning = False
        self.pan_start = (0, 0)
        self.pan_start_camera = (0, 0)

        self.route_list_scroll = 0

        self.route_list_rect = pygame.Rect(
            10,
            40,
            SIDEBAR_WIDTH - 20,
            self.height - 50,
        )

        # Buttons only.
        # Route name is determined by timetable_index.
        btn_y = 8

        self.btn_save_route = Button(
            (
                SIDEBAR_WIDTH + 10,
                btn_y,
                110,
                30,
            ),
            "Save route",
            self.font_ui,
        )

        self.btn_cancel_last = Button(
            (
                SIDEBAR_WIDTH + 130,
                btn_y,
                110,
                30,
            ),
            "Cancel last",
            self.font_ui,
        )

        self.btn_save_all = Button(
            (
                SIDEBAR_WIDTH + 250,
                btn_y,
                130,
                30,
            ),
            "Save all routes",
            self.font_ui,
        )

        self.map_pixel_w = (
            max(
                (
                    len(line)
                    for line in self.lines
                ),
                default=0,
            )
            * CELL_SIZE
        )

        self.map_pixel_h = (
            len(self.lines)
            * CELL_SIZE
        )

        # -------------------------------------------------
        # IMPORTANT:
        # Load existing ARS work immediately.
        # -------------------------------------------------
        self.load_existing_routes()

    # -----------------------------------------------------
    # ARS JSON PATH
    # -----------------------------------------------------

    def get_ars_routes_path(self):
        """Return the ARS JSON path for the current map.

        Example:

            zone_6_map.txt
                ->
            src/json/zone_6_ars_routes.json
        """

        map_stem = self.map_path.stem

        if map_stem.endswith("_map"):
            scenario = map_stem[:-4]
        else:
            scenario = map_stem

        return (
            PROJECT_ROOT
            / "src"
            / "json"
            / f"{scenario}_ars_routes.json"
        )

    # -----------------------------------------------------
    # LOAD EXISTING WORK
    # -----------------------------------------------------

    def load_existing_routes(self):
        """Load previously saved ARS routes.

        This is deliberately done when the ARS builder opens,
        so closing and reopening the editor does not lose
        previously completed routes.
        """

        output_path = self.get_ars_routes_path()

        if not output_path.exists():
            self.routes = []

            self.status_text = (
                "No existing ARS routes found. "
                "Starting a new route file."
            )

            return

        try:
            with output_path.open(
                "r",
                encoding="utf-8",
            ) as handle:
                payload = json.load(handle)

        except (
            OSError,
            json.JSONDecodeError,
        ) as exc:
            self.routes = []

            self.status_text = (
                f"Could not load existing ARS file: "
                f"{exc}"
            )

            return

        if isinstance(payload, dict):
            raw_routes = payload.get(
                "routes",
                [],
            )
        elif isinstance(payload, list):
            raw_routes = payload
        else:
            raw_routes = []

        loaded_routes = []

        for route in raw_routes:
            if not isinstance(route, dict):
                continue

            timetable_index = route.get(
                "timetable_index"
            )

            # -------------------------------------------------
            # Prefer signal_paths.
            #
            # New format:
            #
            # "signal_paths": [
            #     [
            #         [[1,2], [3,4]]
            #     ],
            #     ...
            # ]
            #
            # Also support the simple legacy "signals" format.
            # -------------------------------------------------

            raw_signal_paths = route.get(
                "signal_paths"
            )

            if (
                isinstance(
                    raw_signal_paths,
                    list,
                )
                and raw_signal_paths
            ):
                signal_paths = []

                for raw_path in raw_signal_paths:
                    if not isinstance(
                        raw_path,
                        (list, tuple),
                    ):
                        continue

                    path = []

                    for raw_coord in raw_path:
                        coord = self._coerce_coord_safe(
                            raw_coord
                        )

                        if coord is not None:
                            path.append(coord)

                    if path:
                        signal_paths.append(path)

            else:
                raw_signals = route.get(
                    "signals",
                    [],
                )

                signal_paths = []

                if isinstance(
                    raw_signals,
                    list,
                ):
                    path = []

                    for raw_coord in raw_signals:
                        coord = self._coerce_coord_safe(
                            raw_coord
                        )

                        if coord is not None:
                            path.append(coord)

                    if path:
                        signal_paths.append(path)

            if not signal_paths:
                continue

            normalised_route = {
                "name": str(
                    route.get(
                        "name",
                        timetable_index
                        if timetable_index is not None
                        else "",
                    )
                ),
                "timetable_index": timetable_index,
                "signals": signal_paths[0],
                "signal_paths": signal_paths,
            }

            loaded_routes.append(
                normalised_route
            )

        # One route per timetable index.
        #
        # If an older/broken JSON contains duplicates,
        # keep the last one.
        unique_routes = {}

        for route in loaded_routes:
            timetable_index = route.get(
                "timetable_index"
            )

            unique_routes[timetable_index] = route

        self.routes = list(
            unique_routes.values()
        )

        self.routes.sort(
            key=lambda route: (
                route.get("timetable_index")
                if route.get("timetable_index")
                is not None
                else float("inf")
            )
        )

        if self.routes:
            self.status_text = (
                f"Loaded {len(self.routes)} saved "
                f"route(s) from "
                f"{output_path.name}. "
                f"Select a route to continue editing."
            )

            # Automatically select the first saved route
            # if possible and load it into the editor.
            first_index = self.routes[0].get(
                "timetable_index"
            )

            candidate_index = (
                self._find_candidate_index(
                    first_index
                )
            )

            if candidate_index is not None:
                self.selected_route_index = (
                    candidate_index
                )
                self._load_route_into_editor(
                    first_index
                )

        else:
            self.status_text = (
                f"No usable routes found in "
                f"{output_path.name}."
            )

    @staticmethod
    def _coerce_coord_safe(value):
        """Safely convert a JSON coordinate into (x, y).

        This specifically prevents the old error:

            int() argument ... not 'list'

        when nested lists are encountered.
        """

        # {"coord": [x, y]}
        if isinstance(value, dict):
            if "coord" in value:
                return (
                    ARSRouteBuilder
                    ._coerce_coord_safe(
                        value["coord"]
                    )
                )

            if (
                "x" in value
                and "y" in value
            ):
                try:
                    return (
                        int(value["x"]),
                        int(value["y"]),
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    return None

            return None

        # "x,y"
        if isinstance(value, str):
            value = (
                value
                .strip()
                .replace("(", "")
                .replace(")", "")
            )

            if "," in value:
                x_text, y_text = (
                    value.split(",", 1)
                )

                try:
                    return (
                        int(x_text.strip()),
                        int(y_text.strip()),
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    return None

            return None

        # [x, y]
        if isinstance(
            value,
            (list, tuple),
        ):
            if len(value) < 2:
                return None

            # IMPORTANT:
            # Do NOT call int(value[0]) if value[0]
            # is itself a list.
            #
            # This handles malformed/nested data safely.
            if isinstance(
                value[0],
                (list, tuple, dict),
            ):
                return None

            if isinstance(
                value[1],
                (list, tuple, dict),
            ):
                return None

            try:
                return (
                    int(value[0]),
                    int(value[1]),
                )
            except (
                TypeError,
                ValueError,
            ):
                return None

        return None

    def _find_candidate_index(
        self,
        timetable_index,
    ):
        for index, candidate in enumerate(
            self.route_candidates
        ):
            if (
                candidate.get("timetable_index")
                == timetable_index
            ):
                return index

        return None

    def _load_route_into_editor(
        self,
        timetable_index,
    ):
        """Load a saved route back into route_steps.

        If a route has alternatives, reconstruct them as:

            [
                [(x1, y1)],
                [(x2, y2), (x2_alt, y2_alt)],
                [(x3, y3)],
            ]

        This means Shift+Click alternatives can be edited
        after reopening the program.
        """

        route = next(
            (
                route
                for route in self.routes
                if route.get(
                    "timetable_index"
                )
                == timetable_index
            ),
            None,
        )

        if route is None:
            self.route_steps = []
            return False

        signal_paths = route.get(
            "signal_paths"
        )

        # If signal_paths is missing, use the primary path.
        if not signal_paths:
            signals = route.get(
                "signals",
                [],
            )

            if signals:
                signal_paths = [
                    signals
                ]
            else:
                self.route_steps = []
                return False

        # Clean all paths.
        cleaned_paths = []

        for raw_path in signal_paths:
            if not isinstance(
                raw_path,
                (list, tuple),
            ):
                continue

            path = []

            for raw_coord in raw_path:
                coord = self._coerce_coord_safe(
                    raw_coord
                )

                if coord is not None:
                    path.append(coord)

            if path:
                cleaned_paths.append(path)

        if not cleaned_paths:
            self.route_steps = []
            return False

        # Reconstruct route steps from all paths.
        #
        # Example:
        #
        # path 1 = A B C
        # path 2 = A D C
        #
        # becomes:
        #
        # [
        #     [A],
        #     [B, D],
        #     [C],
        # ]
        #
        # Paths must have the same number of steps
        # to be combined this way.
        max_length = max(
            len(path)
            for path in cleaned_paths
        )

        steps = []

        for step_index in range(
            max_length
        ):
            step_coords = []

            for path in cleaned_paths:
                if (
                    step_index
                    >= len(path)
                ):
                    continue

                coord = path[
                    step_index
                ]

                if coord not in step_coords:
                    step_coords.append(
                        coord
                    )

            if step_coords:
                steps.append(
                    step_coords
                )

        self.route_steps = steps

        return True

    # -----------------------------------------------------
    # MAP / ROUTE HELPERS
    # -----------------------------------------------------

    def _collect_signal_coords(self):
        coords = {}

        for y, line in enumerate(
            self.lines
        ):
            for x, char in enumerate(line):
                if char in ALL_SELECTABLE_SIGNALS:
                    coords[(x, y)] = char

        return coords

    def _selected_route_coords(self):
        if self.selected_route_index is None:
            return set()

        return set(
            tuple(coord)
            for coord in self.route_candidates[
                self.selected_route_index
            ].get(
                "coords",
                [],
            )
        )

    def _all_selected_coords(self):
        return {
            coord
            for step in self.route_steps
            for coord in step
        }

    def _screen_to_grid(self, pos):
        mx, my = pos

        gx = (
            mx
            - self.map_area_rect.x
            + self.camera_x
        ) // CELL_SIZE

        gy = (
            my
            - self.map_area_rect.y
            + self.camera_y
        ) // CELL_SIZE

        return int(gx), int(gy)

    def _clamp_camera(self):
        max_cam_x = max(
            0,
            self.map_pixel_w
            - self.map_area_rect.width,
        )

        max_cam_y = max(
            0,
            self.map_pixel_h
            - self.map_area_rect.height,
        )

        self.camera_x = min(
            max(0, self.camera_x),
            max_cam_x,
        )

        self.camera_y = min(
            max(0, self.camera_y),
            max_cam_y,
        )

    # -----------------------------------------------------
    # ROUTE EDITING
    # -----------------------------------------------------

    def handle_signal_click(
        self,
        coord,
        shift,
        ctrl,
    ):
        if coord not in self.signal_coords:
            return

        selected = self._all_selected_coords()

        if ctrl:
            removed = False

            for step in self.route_steps:
                if coord in step:
                    step.remove(coord)
                    removed = True
                    break

            self.route_steps = [
                step
                for step in self.route_steps
                if step
            ]

            if removed:
                self.status_text = (
                    f"Removed {coord}."
                )
            else:
                self.route_steps.append(
                    [coord]
                )

                self.status_text = (
                    f"Added {coord} as a new step."
                )

            return

        if coord in selected:
            self.status_text = (
                f"{coord} is already selected. "
                "Ctrl+Click to remove."
            )
            return

        if shift and self.route_steps:
            # Add an alternate to the current step.
            self.route_steps[-1].append(
                coord
            )

            self.status_text = (
                f"Added {coord} as an alternate "
                f"for step {len(self.route_steps)} "
                "(connected from the previous signal)."
            )

        else:
            self.route_steps.append(
                [coord]
            )

            if (
                len(self.route_steps) > 1
                and len(
                    self.route_steps[-2]
                ) > 1
            ):
                self.status_text = (
                    f"Combined "
                    f"{len(self.route_steps[-2])} "
                    f"alternates into {coord}."
                )
            else:
                self.status_text = (
                    f"Added {coord} as step "
                    f"{len(self.route_steps)}."
                )

    def cancel_last_signal(self):
        if not self.route_steps:
            self.status_text = (
                "No signal has been selected yet."
            )
            return

        last_step = self.route_steps[-1]

        last_step.pop()

        if not last_step:
            self.route_steps.pop()

        self.status_text = (
            f"Route steps: {self.route_steps}"
        )

    # -----------------------------------------------------
    # SAVE
    # -----------------------------------------------------

    def save_route(self):
        """Save exactly one route for the selected timetable index."""

        if len(self.route_steps) < 2:
            self.status_text = (
                "A route needs at least 2 steps "
                "before saving."
            )
            return False

        if self.selected_route_index is None:
            self.status_text = (
                "Select a timetable route in the "
                "sidebar before saving."
            )
            return False

        candidate = self.route_candidates[
            self.selected_route_index
        ]

        timetable_index = candidate[
            "timetable_index"
        ]

        # Route number/name is ALWAYS timetable index.
        route_name = str(
            timetable_index
        )

        # Expand Shift+Click alternatives into
        # separate signal paths.
        combinations = list(
            itertools.product(
                *self.route_steps
            )
        )

        if not combinations:
            self.status_text = (
                "No valid route combinations."
            )
            return False

        signal_paths = [
            [
                [x, y]
                for x, y in combo
            ]
            for combo in combinations
        ]

        route_data = {
            "name": route_name,
            "timetable_index": timetable_index,

            # Primary path retained for compatibility.
            "signals": signal_paths[0],

            # All alternatives.
            "signal_paths": signal_paths,
        }

        existing_index = next(
            (
                i
                for i, route in enumerate(
                    self.routes
                )
                if route.get(
                    "timetable_index"
                )
                == timetable_index
            ),
            None,
        )

        if existing_index is not None:
            self.routes[
                existing_index
            ] = route_data

            action_text = (
                f"Updated route {route_name}"
            )

        else:
            self.routes.append(
                route_data
            )

            action_text = (
                f"Saved route {route_name}"
            )

        # Keep routes ordered by timetable index.
        self.routes.sort(
            key=lambda route: (
                route.get(
                    "timetable_index"
                )
                if route.get(
                    "timetable_index"
                ) is not None
                else float("inf")
            )
        )

        # -------------------------------------------------
        # IMPORTANT:
        # Save immediately.
        #
        # This means if you close and reopen ARS,
        # the route is already there.
        # -------------------------------------------------
        output_path = (
            self.get_ars_routes_path()
        )

        try:
            save_ars_routes(
                output_path,
                self.routes,
            )

        except OSError as exc:
            self.status_text = (
                f"{action_text}, but failed to "
                f"write JSON: {exc}"
            )

            return False

        self.status_text = (
            f"{action_text} "
            f"(timetable index "
            f"{timetable_index}) "
            f"with {len(signal_paths)} path(s). "
            f"Saved to {output_path.name}"
        )

        # Clear editor after successful save.
        self.route_steps = []

        return True

    def finish_and_save(self):
        """Save every route and exit the editor."""

        # If the user has an unsaved route currently
        # being edited, save it first.
        if self.route_steps:
            if (
                len(self.route_steps) >= 2
                and self.selected_route_index
                is not None
            ):
                self.save_route()
            else:
                self.status_text = (
                    "Current route is incomplete. "
                    "Saving existing routes."
                )

        output_path = (
            self.get_ars_routes_path()
        )

        self.routes.sort(
            key=lambda route: (
                route.get(
                    "timetable_index"
                )
                if route.get(
                    "timetable_index"
                ) is not None
                else float("inf")
            )
        )

        try:
            save_ars_routes(
                output_path,
                self.routes,
            )

        except OSError as exc:
            self.status_text = (
                f"Failed to save routes: {exc}"
            )

            return False

        self.status_text = (
            f"Saved {len(self.routes)} routes to "
            f"{output_path}"
        )

        pygame.display.flip()
        pygame.time.wait(600)

        return True

    # -----------------------------------------------------
    # SIDEBAR
    # -----------------------------------------------------

    def draw_sidebar(self, mouse_pos):
        pygame.draw.rect(
            self.screen,
            COL_SIDEBAR_BG,
            (
                0,
                0,
                SIDEBAR_WIDTH,
                self.height,
            ),
        )

        title = self.font_ui_bold.render(
            "Candidate routes",
            True,
            COL_PANEL_TEXT,
        )

        self.screen.blit(
            title,
            (10, 12),
        )

        pygame.draw.rect(
            self.screen,
            COL_LIST_BG,
            self.route_list_rect,
        )

        row_height = 26

        clip = self.screen.get_clip()

        self.screen.set_clip(
            self.route_list_rect
        )

        for i, route in enumerate(
            self.route_candidates
        ):
            row_y = (
                self.route_list_rect.y
                + i * row_height
                - self.route_list_scroll
            )

            if (
                row_y + row_height
                < self.route_list_rect.y
                or row_y
                > self.route_list_rect.bottom
            ):
                continue

            row_rect = pygame.Rect(
                self.route_list_rect.x,
                row_y,
                self.route_list_rect.width,
                row_height,
            )

            if (
                i
                == self.selected_route_index
            ):
                pygame.draw.rect(
                    self.screen,
                    COL_LIST_SEL,
                    row_rect,
                )

            station_text = ", ".join(
                route["stations"][:4]
            )

            if len(
                route["stations"]
            ) > 4:
                station_text += "..."

            timetable_index = route[
                "timetable_index"
            ]

            label = (
                f"{timetable_index}: "
                f"{route['prefix']} - "
                f"{station_text}"
            )

            # Show a small marker when this route
            # already exists in the JSON.
            saved = any(
                saved_route.get(
                    "timetable_index"
                )
                == timetable_index
                for saved_route in self.routes
            )

            if saved:
                label = "✓ " + label

            text = self.font_small.render(
                label,
                True,
                COL_PANEL_TEXT,
            )

            self.screen.blit(
                text,
                (
                    row_rect.x + 6,
                    row_rect.y + 5,
                ),
            )

        self.screen.set_clip(clip)

    # -----------------------------------------------------
    # TOP BAR
    # -----------------------------------------------------

    def draw_topbar(self, mouse_pos):
        pygame.draw.rect(
            self.screen,
            (25, 25, 25),
            (
                SIDEBAR_WIDTH,
                0,
                self.width
                - SIDEBAR_WIDTH,
                TOPBAR_HEIGHT,
            ),
        )

        self.btn_save_route.draw(
            self.screen,
            mouse_pos,
        )

        self.btn_cancel_last.draw(
            self.screen,
            mouse_pos,
        )

        self.btn_save_all.draw(
            self.screen,
            mouse_pos,
        )

        step_count = len(
            self.route_steps
        )

        alt_count = sum(
            len(step) - 1
            for step in self.route_steps
            if len(step) > 1
        )

        info = f"Steps: {step_count}"

        if alt_count:
            info += (
                f" ({alt_count} alternate"
                f"{'s' if alt_count != 1 else ''})"
            )

        info_text = self.font_small.render(
            info,
            True,
            (170, 170, 170),
        )

        self.screen.blit(
            info_text,
            (
                SIDEBAR_WIDTH + 400,
                16,
            ),
        )

        if (
            self.route_candidates
            and self.selected_route_index
            is not None
        ):
            candidate = self.route_candidates[
                self.selected_route_index
            ]

            prefix = candidate[
                "prefix"
            ]

            timetable_index = candidate[
                "timetable_index"
            ]

            saved = any(
                route.get(
                    "timetable_index"
                )
                == timetable_index
                for route in self.routes
            )

            saved_text = (
                " | SAVED"
                if saved
                else ""
            )

            sel_text = self.font_ui.render(
                (
                    f"Route {timetable_index}  |  "
                    f"{prefix} selected"
                    f"{saved_text}"
                ),
                True,
                COL_PANEL_TEXT,
            )

            self.screen.blit(
                sel_text,
                (
                    SIDEBAR_WIDTH + 400,
                    48,
                ),
            )

    # -----------------------------------------------------
    # STATUS
    # -----------------------------------------------------

    def draw_status(self):
        rect = pygame.Rect(
            0,
            self.height - STATUS_HEIGHT,
            self.width,
            STATUS_HEIGHT,
        )

        pygame.draw.rect(
            self.screen,
            (20, 20, 20),
            rect,
        )

        text = self.font_small.render(
            self.status_text,
            True,
            (200, 200, 200),
        )

        self.screen.blit(
            text,
            (
                8,
                rect.y + 5,
            ),
        )

    # -----------------------------------------------------
    # MAP DRAWING
    # -----------------------------------------------------

    def _cell_center(self, coord):
        x, y = coord

        sx = (
            self.map_area_rect.x
            + x * CELL_SIZE
            - self.camera_x
            + CELL_SIZE // 2
        )

        sy = (
            self.map_area_rect.y
            + y * CELL_SIZE
            - self.camera_y
            + CELL_SIZE // 2
        )

        return sx, sy

    def _draw_connector(
        self,
        color,
        start,
        end,
        width,
    ):
        pygame.draw.line(
            self.screen,
            color,
            start,
            end,
            width,
        )

        dx = end[0] - start[0]
        dy = end[1] - start[1]

        length = (
            dx ** 2
            + dy ** 2
        ) ** 0.5

        if length < 1:
            return

        ux = dx / length
        uy = dy / length

        tip = end

        back = (
            end[0] - ux * 9,
            end[1] - uy * 9,
        )

        left = (
            back[0] - uy * 4,
            back[1] + ux * 4,
        )

        right = (
            back[0] + uy * 4,
            back[1] - ux * 4,
        )

        pygame.draw.polygon(
            self.screen,
            color,
            [
                tip,
                left,
                right,
            ],
        )

    def draw_map(self):
        pygame.draw.rect(
            self.screen,
            COL_BG,
            self.map_area_rect,
        )

        clip = self.screen.get_clip()

        self.screen.set_clip(
            self.map_area_rect
        )

        highlight_coords = (
            self._selected_route_coords()
        )

        primary_coords = {
            step[0]
            for step in self.route_steps
            if step
        }

        alt_coords = {
            coord
            for step in self.route_steps
            for coord in step[1:]
        }

        first_col = max(
            0,
            self.camera_x // CELL_SIZE,
        )

        first_row = max(
            0,
            self.camera_y // CELL_SIZE,
        )

        visible_cols = (
            self.map_area_rect.width
            // CELL_SIZE
            + 2
        )

        visible_rows = (
            self.map_area_rect.height
            // CELL_SIZE
            + 2
        )

        for y in range(
            first_row,
            min(
                len(self.lines),
                first_row + visible_rows,
            ),
        ):
            line = self.lines[y]

            for x in range(
                first_col,
                min(
                    len(line),
                    first_col + visible_cols,
                ),
            ):
                char = line[x]

                coord = (x, y)

                screen_x = (
                    self.map_area_rect.x
                    + x * CELL_SIZE
                    - self.camera_x
                )

                screen_y = (
                    self.map_area_rect.y
                    + y * CELL_SIZE
                    - self.camera_y
                )

                cell_rect = pygame.Rect(
                    screen_x,
                    screen_y,
                    CELL_SIZE,
                    CELL_SIZE,
                )

                if char == " ":
                    continue

                fill = COL_DEFAULT_CELL
                text_fill = COL_DEFAULT_TEXT

                if coord in primary_coords:
                    fill = COL_SELECTED
                    text_fill = (0, 0, 0)

                elif coord in alt_coords:
                    fill = COL_SELECTED_ALT
                    text_fill = (0, 0, 0)

                elif coord in self.signal_coords:
                    if (
                        self.signal_coords[coord]
                        in MANUAL_SIGNAL_CHARS
                    ):
                        fill = COL_MANUAL
                    else:
                        fill = COL_AUTOMATIC

                    text_fill = COL_SIGNAL_TEXT

                elif coord in highlight_coords:
                    fill = COL_CANDIDATE
                    text_fill = (0, 0, 0)

                pygame.draw.rect(
                    self.screen,
                    fill,
                    cell_rect,
                )

                pygame.draw.rect(
                    self.screen,
                    COL_GRID_LINE,
                    cell_rect,
                    width=1,
                )

                glyph = self.font_map.render(
                    char,
                    True,
                    text_fill,
                )

                self.screen.blit(
                    glyph,
                    glyph.get_rect(
                        center=cell_rect.center
                    ),
                )

        # Connect each step to the next step.
        for i in range(len(self.route_steps) - 1):
            current_step = self.route_steps[i]
            next_step = self.route_steps[i + 1]

            if not current_step or not next_step:
                continue

            for current_index, current_coord in enumerate(
                current_step
            ):
                for next_index, next_coord in enumerate(
                    next_step
                ):
                    # Primary -> primary is the main route.
                    # Any connection involving an alternate is drawn
                    # using the alternate colour/width.
                    is_primary = (
                        current_index == 0
                        and next_index == 0
                    )

                    color = (
                        COL_ROUTE_LINE
                        if is_primary
                        else COL_ROUTE_LINE_ALT
                    )

                    width = 3 if is_primary else 2

                    self._draw_connector(
                        color,
                        self._cell_center(current_coord),
                        self._cell_center(next_coord),
                        width,
                    )

        # Node markers + step numbers.
        for i, step in enumerate(
            self.route_steps
        ):
            for j, coord in enumerate(
                step
            ):
                center = self._cell_center(
                    coord
                )

                if j == 0:
                    pygame.draw.circle(
                        self.screen,
                        (255, 255, 255),
                        center,
                        5,
                        width=2,
                    )

                    badge = self.font_small.render(
                        str(i + 1),
                        True,
                        (255, 255, 255),
                    )

                    self.screen.blit(
                        badge,
                        (
                            center[0] + 6,
                            center[1] - 18,
                        ),
                    )

                else:
                    pygame.draw.circle(
                        self.screen,
                        COL_ROUTE_LINE_ALT,
                        center,
                        4,
                        width=2,
                    )

        self.screen.set_clip(clip)

    # -----------------------------------------------------
    # MAIN LOOP
    # -----------------------------------------------------

    def run(self):
        running = True

        while running:
            mouse_pos = pygame.mouse.get_pos()

            for event in pygame.event.get():

                if event.type == pygame.QUIT:
                    # Routes that were already saved are safe.
                    # Save them once more on exit.
                    try:
                        save_ars_routes(
                            self.get_ars_routes_path(),
                            self.routes,
                        )
                    except OSError:
                        pass

                    running = False

                elif event.type == pygame.KEYDOWN:
                    pass

                elif (
                    event.type
                    == pygame.MOUSEBUTTONDOWN
                ):

                    if event.button == 1:

                        if self.btn_save_route.clicked(
                            event.pos
                        ):
                            self.save_route()

                        elif self.btn_cancel_last.clicked(
                            event.pos
                        ):
                            self.cancel_last_signal()

                        elif self.btn_save_all.clicked(
                            event.pos
                        ):
                            if self.finish_and_save():
                                running = False

                        elif self.route_list_rect.collidepoint(
                            event.pos
                        ):
                            row_height = 26

                            index = (
                                (
                                    event.pos[1]
                                    - self.route_list_rect.y
                                    + self.route_list_scroll
                                )
                                // row_height
                            )

                            if (
                                0
                                <= index
                                < len(
                                    self.route_candidates
                                )
                            ):
                                self.selected_route_index = (
                                    index
                                )

                                prefix = (
                                    self.route_candidates[
                                        index
                                    ]["prefix"]
                                )

                                timetable_index = (
                                    self.route_candidates[
                                        index
                                    ]["timetable_index"]
                                )

                                # -------------------------------------------------
                                # IMPORTANT:
                                # If this timetable route already exists in
                                # the JSON, load it into the editor.
                                # -------------------------------------------------
                                loaded = (
                                    self._load_route_into_editor(
                                        timetable_index
                                    )
                                )

                                if loaded:
                                    self.status_text = (
                                        f"Loaded saved route "
                                        f"{prefix} "
                                        f"(index "
                                        f"{timetable_index}) "
                                        f"for editing."
                                    )
                                else:
                                    self.route_steps = []

                                    self.status_text = (
                                        f"Selected timetable "
                                        f"route {prefix} "
                                        f"(index "
                                        f"{timetable_index})"
                                    )

                        elif self.map_area_rect.collidepoint(
                            event.pos
                        ):
                            coord = self._screen_to_grid(
                                event.pos
                            )

                            mods = pygame.key.get_mods()

                            shift = bool(
                                mods
                                & pygame.KMOD_SHIFT
                            )

                            ctrl = bool(
                                mods
                                & pygame.KMOD_CTRL
                            )

                            self.handle_signal_click(
                                coord,
                                shift,
                                ctrl,
                            )

                    elif event.button == 3:
                        # Right-click drag to pan.
                        self.panning = True
                        self.pan_start = event.pos

                        self.pan_start_camera = (
                            self.camera_x,
                            self.camera_y,
                        )

                    elif event.button == 4:
                        # Scroll up / left.
                        if self.route_list_rect.collidepoint(
                            event.pos
                        ):
                            self.route_list_scroll = max(
                                0,
                                self.route_list_scroll
                                - 30,
                            )

                        elif self.map_area_rect.collidepoint(
                            event.pos
                        ):
                            if (
                                pygame.key.get_mods()
                                & pygame.KMOD_SHIFT
                            ):
                                self.camera_y -= 40
                            else:
                                self.camera_x -= 40

                            self._clamp_camera()

                    elif event.button == 5:
                        # Scroll down / right.
                        if self.route_list_rect.collidepoint(
                            event.pos
                        ):
                            max_scroll = max(
                                0,
                                len(
                                    self.route_candidates
                                )
                                * 26
                                - self.route_list_rect.height,
                            )

                            self.route_list_scroll = min(
                                max_scroll,
                                self.route_list_scroll
                                + 30,
                            )

                        elif self.map_area_rect.collidepoint(
                            event.pos
                        ):
                            if (
                                pygame.key.get_mods()
                                & pygame.KMOD_SHIFT
                            ):
                                self.camera_y += 40
                            else:
                                self.camera_x += 40

                            self._clamp_camera()

                elif (
                    event.type
                    == pygame.MOUSEBUTTONUP
                ):

                    if event.button == 3:
                        self.panning = False

                elif (
                    event.type
                    == pygame.MOUSEMOTION
                ):

                    if self.panning:
                        dx = (
                            event.pos[0]
                            - self.pan_start[0]
                        )

                        dy = (
                            event.pos[1]
                            - self.pan_start[1]
                        )

                        self.camera_x = (
                            self.pan_start_camera[0]
                            - dx
                        )

                        self.camera_y = (
                            self.pan_start_camera[1]
                            - dy
                        )

                        self._clamp_camera()

            self.screen.fill(COL_BG)

            self.draw_map()
            self.draw_sidebar(mouse_pos)
            self.draw_topbar(mouse_pos)
            self.draw_status()

            pygame.display.flip()

            self.clock.tick(60)

        pygame.quit()

        return self.routes


def choose_map_file(
    screen,
    clock,
    font,
    font_small,
):
    map_files = sorted(
        PROJECT_ROOT.glob("*_map.txt")
    )

    if not map_files:
        raise FileNotFoundError(
            "No *_map.txt files were found "
            "in the project root."
        )

    selected_index = 0
    row_height = 32

    while True:
        for event in pygame.event.get():

            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)

            elif event.type == pygame.KEYDOWN:

                if event.key == pygame.K_UP:
                    selected_index = max(
                        0,
                        selected_index - 1,
                    )

                elif event.key == pygame.K_DOWN:
                    selected_index = min(
                        len(map_files) - 1,
                        selected_index + 1,
                    )

                elif event.key == pygame.K_RETURN:
                    return map_files[
                        selected_index
                    ]

            elif (
                event.type
                == pygame.MOUSEBUTTONDOWN
                and event.button == 1
            ):
                mx, my = event.pos

                list_top = 60

                for i, _ in enumerate(
                    map_files
                ):
                    row_rect = pygame.Rect(
                        20,
                        list_top
                        + i * row_height,
                        380,
                        row_height,
                    )

                    if row_rect.collidepoint(
                        mx,
                        my,
                    ):
                        if (
                            i
                            == selected_index
                        ):
                            return map_files[i]

                        selected_index = i

        screen.fill(COL_BG)

        title = font.render(
            "Choose a map file:",
            True,
            COL_PANEL_TEXT,
        )

        screen.blit(
            title,
            (20, 18),
        )

        list_top = 60

        for i, map_file in enumerate(
            map_files
        ):
            row_rect = pygame.Rect(
                20,
                list_top
                + i * row_height,
                380,
                row_height,
            )

            bg = (
                COL_LIST_SEL
                if i == selected_index
                else COL_LIST_BG
            )

            pygame.draw.rect(
                screen,
                bg,
                row_rect,
                border_radius=3,
            )

            text = font_small.render(
                map_file.name,
                True,
                COL_PANEL_TEXT,
            )

            screen.blit(
                text,
                (
                    row_rect.x + 8,
                    row_rect.y
                    + (
                        row_height
                        - text.get_height()
                    )
                    // 2,
                ),
            )

        hint = font_small.render(
            "Double-click or Enter to open",
            True,
            (150, 150, 150),
        )

        screen.blit(
            hint,
            (
                20,
                list_top
                + len(map_files)
                * row_height
                + 12,
            ),
        )

        pygame.display.flip()

        clock.tick(60)


def build_route_file_from_prompt(
    default_path: str | None = None,
):
    pygame.init()

    screen = pygame.display.set_mode(
        (1220, 820)
    )

    pygame.display.set_caption(
        "ARS route builder"
    )

    clock = pygame.time.Clock()

    picker_font = load_font(
        18,
        bold=True,
        custom=False,
    )

    picker_font_small = load_font(
        15,
        custom=False,
    )

    map_path = (
        Path(default_path)
        if default_path
        else choose_map_file(
            screen,
            clock,
            picker_font,
            picker_font_small,
        )
    )

    pygame.display.set_caption(
        f"ARS route builder - {map_path.name}"
    )

    builder = ARSRouteBuilder(
        map_path,
        screen,
        clock,
    )

    return builder.run()


if __name__ == "__main__":
    build_route_file_from_prompt()