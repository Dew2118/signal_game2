import json
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

Coord = Tuple[int, int]


def _coerce_coord(value: Any) -> Coord:
    if isinstance(value, dict):
        if "coord" in value:
            return _coerce_coord(value["coord"])

        if "x" in value and "y" in value:
            return (
                int(value["x"]),
                int(value["y"]),
            )

    if isinstance(value, str):
        value = (
            value
            .strip()
            .replace("(", "")
            .replace(")", "")
        )

        if "," in value:
            x_text, y_text = value.split(",", 1)

            return (
                int(x_text.strip()),
                int(y_text.strip()),
            )

    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return (
            int(value[0]),
            int(value[1]),
        )

    raise ValueError(
        f"Unable to coerce signal coordinate: {value!r}"
    )


def _normalise_signal_path(
    path: Any,
) -> List[Coord]:
    """Convert one signal path into a clean list of coordinates."""

    if not isinstance(path, (list, tuple)):
        return []

    coords: List[Coord] = []

    for item in path:
        try:
            coord = _coerce_coord(item)
        except (ValueError, TypeError, IndexError):
            continue

        if coord not in coords:
            coords.append(coord)

    return coords


def _get_route_paths(
    route: Dict[str, Any],
) -> List[List[Coord]]:
    """Return every signal path belonging to a route.

    New format:
        signal_paths = [
            [[x, y], [x, y]],
            [[x, y], [x, y]],
        ]

    Old format:
        signals = [
            [x, y],
            [x, y],
        ]

    Old routes are automatically treated as one path.
    """

    if not isinstance(route, dict):
        return []

    signal_paths = route.get("signal_paths")

    if isinstance(signal_paths, list):
        paths: List[List[Coord]] = []

        for raw_path in signal_paths:
            path = _normalise_signal_path(raw_path)

            if path:
                paths.append(path)

        if paths:
            return paths

    # Backwards compatibility with the old flat format.
    signals = route.get("signals", [])

    path = _normalise_signal_path(signals)

    if path:
        return [path]

    return []


def _normalise_route(
    route: Dict[str, Any],
) -> List[Coord]:
    """Return the first/primary path for backwards compatibility."""

    paths = _get_route_paths(route)

    if not paths:
        return []

    return paths[0]


def _normalise_route_dict(
    route: Dict[str, Any],
) -> Dict[str, Any]:
    if not isinstance(route, dict):
        return {
            "name": "",
            "signals": [],
            "signal_paths": [],
            "timetable_index": None,
        }

    paths = _get_route_paths(route)

    primary_path = paths[0] if paths else []

    normalised = {
        "name": route.get("name", ""),
        "timetable_index": route.get(
            "timetable_index"
        ),
        "signals": [
            list(coord)
            for coord in primary_path
        ],
        "signal_paths": [
            [
                list(coord)
                for coord in path
            ]
            for path in paths
        ],
    }

    return normalised


def build_ars_lookup(
    routes: Sequence[Dict[str, Any]],
) -> Dict[Coord, List[Coord]]:
    """Build a global signal -> candidate next-signal lookup.

    All signal paths from all routes are merged.

    This means if one route contains:

        A -> B
        A -> C

    then:

        lookup[A] == [B, C]
    """

    lookup: Dict[Coord, List[Coord]] = {}

    for route in routes or []:
        if not isinstance(route, dict):
            continue

        paths = _get_route_paths(route)

        for sequence in paths:
            if len(sequence) < 2:
                continue

            for idx in range(
                len(sequence) - 1
            ):
                current = sequence[idx]
                nxt = sequence[idx + 1]

                bucket = lookup.setdefault(
                    current,
                    [],
                )

                if nxt not in bucket:
                    bucket.append(nxt)

    return lookup


def build_ars_lookup_by_timetable(
    routes: Sequence[Dict[str, Any]],
) -> Dict[Any, Dict[Coord, List[Coord]]]:
    """Build signal lookup grouped by timetable index.

    Each timetable index can have exactly one route,
    but that route may contain multiple signal paths.

    Example:

        timetable index 5

            A -> B
            A -> C

    produces:

        {
            5: {
                A: [B, C]
            }
        }
    """

    lookup_by_index: Dict[
        Any,
        Dict[Coord, List[Coord]],
    ] = {}

    for route in routes or []:
        if not isinstance(route, dict):
            continue

        timetable_index = route.get(
            "timetable_index"
        )

        paths = _get_route_paths(route)

        if not paths:
            continue

        bucket_lookup = lookup_by_index.setdefault(
            timetable_index,
            {},
        )

        for sequence in paths:
            if len(sequence) < 2:
                continue

            for idx in range(
                len(sequence) - 1
            ):
                current = sequence[idx]
                nxt = sequence[idx + 1]

                bucket = bucket_lookup.setdefault(
                    current,
                    [],
                )

                if nxt not in bucket:
                    bucket.append(nxt)

    return lookup_by_index


def save_ars_routes(
    path: str | Path,
    routes: Sequence[Dict[str, Any]],
) -> str:
    """Save ARS routes.

    There is one route object per timetable index.

    The primary path is stored in `signals` for compatibility.
    All paths are stored in `signal_paths`.
    """

    destination = Path(path)

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    serialisable_routes = []

    # Enforce one route per timetable index.
    routes_by_index: Dict[Any, Dict[str, Any]] = {}

    routes_without_index = []

    for route in routes or []:
        if not isinstance(route, dict):
            continue

        timetable_index = route.get(
            "timetable_index"
        )

        if timetable_index is None:
            routes_without_index.append(route)
        else:
            routes_by_index[
                timetable_index
            ] = route

    unique_routes = list(
        routes_by_index.values()
    ) + routes_without_index

    # Sort indexed routes numerically where possible.
    def sort_key(route):
        index = route.get(
            "timetable_index"
        )

        if index is None:
            return (
                1,
                0,
            )

        try:
            return (
                0,
                int(index),
            )
        except (
            TypeError,
            ValueError,
        ):
            return (
                0,
                str(index),
            )

    unique_routes.sort(
        key=sort_key
    )

    for route in unique_routes:
        paths = _get_route_paths(route)

        if not paths:
            continue

        primary_path = paths[0]

        timetable_index = route.get(
            "timetable_index"
        )

        # The route name is ALWAYS the timetable index
        # when an index is present.
        if timetable_index is not None:
            route_name = str(
                timetable_index
            )
        else:
            route_name = route.get(
                "name",
                "",
            )

        serialisable_routes.append(
            {
                "name": route_name,
                "timetable_index": timetable_index,

                # Backwards-compatible primary route.
                "signals": [
                    list(coord)
                    for coord in primary_path
                ],

                # All alternative paths.
                "signal_paths": [
                    [
                        list(coord)
                        for coord in path
                    ]
                    for path in paths
                ],
            }
        )

    with destination.open(
        "w",
        encoding="utf-8",
    ) as handle:
        json.dump(
            {
                "routes": serialisable_routes
            },
            handle,
            indent=2,
        )

    return str(destination)


def load_ars_routes(
    path: str | Path,
) -> List[Dict[str, Any]]:
    destination = Path(path)

    if not destination.exists():
        return []

    with destination.open(
        "r",
        encoding="utf-8",
    ) as handle:
        payload = json.load(handle)

    routes: List[
        Dict[str, Any]
    ] = []

    if isinstance(payload, list):
        items = payload

    elif isinstance(payload, dict):
        items = payload.get(
            "routes",
            [],
        )

    else:
        items = []

    # Enforce one route per timetable index while loading too.
    routes_by_index: Dict[
        Any,
        Dict[str, Any],
    ] = {}

    routes_without_index: List[
        Dict[str, Any]
    ] = []

    for route in items:
        if not isinstance(route, dict):
            continue

        normalised = _normalise_route_dict(
            route
        )

        timetable_index = normalised.get(
            "timetable_index"
        )

        if timetable_index is None:
            routes_without_index.append(
                normalised
            )
        else:
            routes_by_index[
                timetable_index
            ] = normalised

    routes.extend(
        routes_by_index.values()
    )

    routes.extend(
        routes_without_index
    )

    return routes


class ARSManager:
    def __init__(
        self,
        routes: Sequence[Dict[str, Any]] | None = None,
        routes_path: str | Path | None = None,
        map_path: str | Path | None = None,
    ):
        self.routes = list(routes or [])

        self.routes_path = (
            Path(routes_path)
            if routes_path is not None
            else None
        )

        if map_path is not None:
            self.map_path = Path(map_path)

            self.routes_path = self._routes_path_from_map(
                self.map_path
            )
        else:
            self.map_path = None

        # Automatically load the matching JSON when
        # map_path/routes_path was supplied.
        if self.routes_path is not None:
            self.routes = load_ars_routes(
                self.routes_path
            )

        self.lookup = build_ars_lookup(
            self.routes
        )

        self.lookup_by_index = (
            build_ars_lookup_by_timetable(
                self.routes
            )
        )

        self.retry_times: Dict[
            Tuple[Any, Coord],
            float,
        ] = {}

        self.retry_interval_seconds = 10.0

    @staticmethod
    def _routes_path_from_map(
        map_path: str | Path,
    ) -> Path:
        """Derive the ARS route JSON from a map filename.

        Example:

            zone_6_map.txt
                ->
            zone_6_ars_routes.json
        """

        map_path = Path(map_path)

        map_stem = map_path.stem

        if map_stem.endswith("_map"):
            scenario = map_stem[:-4]
        else:
            scenario = map_stem

        project_root = map_path.resolve().parents[0]

        while project_root != project_root.parent:
            if (
                (project_root / "src").is_dir()
                and (project_root / "src" / "json").is_dir()
            ):
                break

            project_root = project_root.parent

        return (
            project_root
            / "src"
            / "json"
            / f"{scenario}_ars_routes.json"
        )

    def load(
        self,
        path: str | Path | None = None,
        map_path: str | Path | None = None,
    ) -> List[Dict[str, Any]]:
        """Load ARS routes.

        Priority:

        1. Explicit `path`
        2. `map_path`, converted automatically to
           `<scenario>_ars_routes.json`
        3. Previously configured routes_path
        """

        if path is not None:
            route_path = Path(path)

        elif map_path is not None:
            self.map_path = Path(map_path)

            route_path = self._routes_path_from_map(
                self.map_path
            )

        else:
            route_path = self.routes_path

        if route_path is None:
            self.routes = []
            self.lookup = {}
            self.lookup_by_index = {}
            return []

        self.routes = load_ars_routes(
            route_path
        )

        self.lookup = build_ars_lookup(
            self.routes
        )

        self.lookup_by_index = (
            build_ars_lookup_by_timetable(
                self.routes
            )
        )

        self.routes_path = route_path

        return self.routes

    def get_candidates_for_signal(
        self,
        signal_coord: Coord | Sequence[int],
        timetable_index: Optional[Any] = None,
    ) -> List[Coord]:
        """Look up candidate next-signals.

        When timetable_index is supplied, only paths belonging
        to that timetable entry are considered.
        """

        key = tuple(signal_coord)

        if timetable_index is not None:
            return list(
                self.lookup_by_index
                .get(
                    timetable_index,
                    {},
                )
                .get(
                    key,
                    [],
                )
            )

        return list(
            self.lookup.get(
                key,
                [],
            )
        )

    def find_signal_for_coord(
        self,
        game,
        coord: Coord,
    ) -> Any:
        coord = tuple(coord)

        for signal in getattr(
            game,
            "signals",
            [],
        ):
            if tuple(
                signal.coord
            ) == coord:
                return signal

        return None

    def find_intersection_with_headcodes(self, game, coords):
        if not coords:
            return True
        coord_set = set(coords[1:])
        headcode_list = []
        for train in game.trains:
            headcode_list.extend(train.headcode_coords)
        print(headcode_list)
        headcode_set = set(headcode_list)
        print(len(coord_set & headcode_set))
        if (len(coord_set & headcode_set) > 0):
            return True
        return False

    def try_set_route_for_signal(
        self,
        game,
        signal,
        timetable_index: Optional[Any] = None,
    ):
        if not game.ars_on:
            return False
        """Attempt to set a route starting at `signal`.

        If a timetable index is provided, only paths associated
        with that timetable index are considered.

        Multiple candidate next-signals are tried in turn.
        """
        print(f"trying to set route from signal at coord  {signal.coord}")

        if (
            signal is None
            or getattr(
                signal,
                "signal_type",
                None,
            )
            != "manual"
        ):
            return False

        if getattr(
            signal,
            "route_set",
            False,
        ):
            return False
        candidates = (
            self.get_candidates_for_signal(
                signal.coord,
                timetable_index,
            )
        )
        if not candidates:
            return False

        for next_coord in candidates:
            next_signal = (
                self.find_signal_for_coord(
                    game,
                    next_coord,
                )
            )

            if next_signal is None:
                continue

            existing_entry = getattr(
                game,
                "entry_signal",
                None,
            )

            existing_exit = getattr(
                game,
                "exit_signal",
                None,
            )

            game.entry_signal = signal
            game.exit_signal = next_signal
            coords = game.set_route(dont_set = True)
            if not self.find_intersection_with_headcodes(game, coords):
                print("INSIDE")
                game.set_route()
                game.entry_signal = None
                game.exit_signal = None
                return True
            else:
                game.entry_signal = None
                game.exit_signal = None
                print("OUTSIDE")
        return False

    def predictive_route_setting_try(self, game):
        if not game.ars_on:
            return
        headcode_coord_to_signal_dict = {}
        for signal in game.signals:
            coord = signal.coord
            if signal.mount == "up":
                headcode_coord_to_signal_dict[(coord[0], coord[1] + 1)] = signal
            else:
                headcode_coord_to_signal_dict[(coord[0], coord[1] - 1)] = signal
            
        route_coords_master_dict = {}
        time_to_entry_signal_dict = {}
        for train in game.trains:
            train_coord_list = []
            entry_signal = None
            for headcode_coord in train.headcode_coords:
                if headcode_coord in headcode_coord_to_signal_dict:
                    entry_signal = headcode_coord_to_signal_dict[headcode_coord]
                    break

            if not entry_signal:
                continue
            if entry_signal.next_signal and (entry_signal.signal_type == "automatic" or len(entry_signal.route_coords) > 0):
                entry_signal = entry_signal.next_signal
            if len(train.headcode_coords) == 0:
                continue
            dx = abs(train.headcode_coords[0][0] - entry_signal.coord[0])
            dy = abs(train.headcode_coords[0][1] - entry_signal.coord[1])
            time = dx+dy
            current_stop = train.timetable[train.current_stop_index]
            stop_coords = train._get_stop_coord(current_stop)
            if train._at_stop_coord(stop_coords):
                dep_offset = current_stop.get('departure_offset', 0)
                arr_offset = current_stop.get('arrival_offset', 0)
                
                time_since_spawn = game.game_seconds - train.game_seconds_at_spawn
                if dep_offset != arr_offset:
                    time += max(dep_offset-time_since_spawn,30-train.start_to_stop_time)
            candidates = self.get_candidates_for_signal(entry_signal.coord,train.timetable_index)
            for next_coord in candidates:
                next_signal = (
                                self.find_signal_for_coord(
                                    game,
                                    next_coord,
                                )
                            )
                if next_signal is None:
                    continue
                train_coord_list.append((entry_signal, next_signal))
            route_coords_master_dict[train] = train_coord_list
            time_to_entry_signal_dict[train] = time
        sorted_dict = dict(sorted(time_to_entry_signal_dict.items(), key=lambda item: item[1]))
        for train, time in sorted_dict.items():
            for signal_tuple in route_coords_master_dict[train]:
                game.entry_signal, game.exit_signal = signal_tuple
                coords = game.set_route(dont_set = True)
                if not self.find_intersection_with_headcodes(game, coords):
                    game.set_route()
                    game.entry_signal = None
                    game.exit_signal = None
                    break
                else:
                    game.entry_signal = None
                    game.exit_signal = None
        
        

            