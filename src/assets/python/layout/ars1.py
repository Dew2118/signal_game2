"""
ARS v1 - predictive Automatic Route Setting.

Architecture
============

Startup:
    1. Load game.ars_routes.
    2. Force-build/load the ARS predictive schedule.
    3. Build a conflict index from the cached schedule.
    4. Live ticks only inspect the precomputed data.

The live ARS tick deliberately does NOT:
    - calculate station dwell times
    - call pathfinding to predict timings
    - rebuild conflicts
    - enumerate physical coordinates
    - use timetable stop offsets

The ARS schedule is authoritative for predicted timing.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.assets.python.layout.ars_schedule import ensure_schedule

Coord = Tuple[int, int]
HORIZON_SECONDS = 60


# ============================================================================
# Generic helpers
# ============================================================================

def _coord(value: Any) -> Coord:
    """Convert a coordinate-like object into (x, y)."""
    if isinstance(value, dict):
        if "coord" in value:
            return _coord(value["coord"])
        if "x" in value and "y" in value:
            return (int(value["x"]), int(value["y"]))

    if isinstance(value, str):
        value = value.strip().replace("(", "").replace(")", "")
        if "," in value:
            x, y = value.split(",", 1)
            return (int(x.strip()), int(y.strip()))

    if isinstance(value, (list, tuple)):
        if len(value) >= 2:
            return (int(value[0]), int(value[1]))

    raise ValueError(f"Cannot convert {value!r} to coordinate")


def _signal_key(entry: Coord, exit: Coord) -> Tuple[Coord, Coord]:
    return (tuple(entry), tuple(exit))


def _find_signal(game, coord: Coord, caches=None):
    """Find a signal by its actual signal coordinate, utilizing fast cache if available."""
    wanted = tuple(coord)
    if caches and "signals" in caches:
        return caches["signals"].get(wanted)

    # Fallback if cache not provided
    for signal in getattr(game, "signals", []):
        if tuple(getattr(signal, "coord", ())) == wanted:
            return signal
    return None


def _is_manual(signal) -> bool:
    return (
        signal is not None
        and getattr(signal, "signal_type", None) == "manual"
    )


# ============================================================================
# Schedule helpers
# ============================================================================

def _schedule_relative_coords(schedule_route: Dict[str, Any]) -> Sequence[Any]:
    return schedule_route.get("coords") or []


def _schedule_time(schedule_coord: Any) -> Optional[float]:
    """Extract the relative schedule time."""
    if not isinstance(schedule_coord, (list, tuple)) or len(schedule_coord) < 3:
        return None
    try:
        return float(schedule_coord[2])
    except (TypeError, ValueError):
        return None


def _schedule_entry_signal(schedule_coord: Any) -> Optional[Coord]:
    if not isinstance(schedule_coord, (list, tuple)) or len(schedule_coord) < 4:
        return None
    value = schedule_coord[3]
    if value is None:
        return None
    try:
        return _coord(value)
    except (TypeError, ValueError):
        return None


def _schedule_exit_signal(schedule_coord: Any) -> Optional[Coord]:
    if not isinstance(schedule_coord, (list, tuple)) or len(schedule_coord) < 5:
        return None
    value = schedule_coord[4]
    if value is None:
        return None
    try:
        return _coord(value)
    except (TypeError, ValueError):
        return None


def _absolute_schedule_time(train, relative_time: float) -> float:
    """Convert cached schedule time into game time."""
    return float(getattr(train, "game_seconds_at_spawn", 0)) + relative_time


# ============================================================================
# ARS Manager
# ============================================================================

class ARSManager:

    def __init__(
        self,
        routes: Optional[Sequence[Dict[str, Any]]] = None,
        routes_path: str | Path | None = None,
        map_path: str | Path | None = None,
    ):
        self.routes = list(routes or [])
        self.routes_path = Path(routes_path) if routes_path is not None else None
        self.map_path = Path(map_path) if map_path is not None else None

        if self.map_path is not None:
            self.routes_path = self._routes_path_from_map(self.map_path)

        self.schedule: Dict[str, Any] = {}
        self.conflicts: Dict[Tuple[Coord, Coord], Dict[str, Any]] = {}
        self.conflicts_by_entry: Dict[Coord, List[Dict[str, Any]]] = {}
        self.routes_by_timetable: Dict[Any, Dict[str, Any]] = {}

        self._prepared = False
        self.is_ready = False
        self.last_attempt_second: Optional[float] = None
        self.debug = False

        if self.routes_path is not None:
            self.load(self.routes_path)
        self.path_hop_coords: Dict[Tuple[Any, Any, Coord, Coord], set[Coord]] = {}

    @staticmethod
    def _routes_path_from_map(map_path: str | Path) -> Path:
        map_path = Path(map_path)
        stem = map_path.stem
        scenario = stem[:-4] if stem.endswith("_map") else stem

        project_root = map_path.resolve().parent
        while project_root != project_root.parent:
            if (project_root / "src").is_dir() and (project_root / "src" / "json").is_dir():
                break
            project_root = project_root.parent

        return project_root / "src" / "json" / f"{scenario}_ars_routes.json"

    def load(
        self,
        path: str | Path | None = None,
        map_path: str | Path | None = None,
    ) -> List[Dict[str, Any]]:

        if path is not None:
            route_path = Path(path)
        elif map_path is not None:
            self.map_path = Path(map_path)
            route_path = self._routes_path_from_map(self.map_path)
        else:
            route_path = self.routes_path

        if route_path is None:
            self.routes = []
            self.routes_path = None
            return []

        self.routes_path = route_path

        if not route_path.exists():
            self.routes = []
            return []

        with route_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

        if isinstance(payload, list):
            raw_routes = payload
        elif isinstance(payload, dict):
            raw_routes = payload.get("routes", [])
        else:
            raw_routes = []

        self.routes = [route for route in raw_routes if isinstance(route, dict)]
        self.routes_by_timetable = {}

        for route in self.routes:
            index = route.get("timetable_index")
            if index is not None:
                self.routes_by_timetable[index] = route

        return self.routes

    def prepare_schedule(self, game, log=print):
        """Prepare EVERYTHING required by predictive ARS."""
        self.routes = list(getattr(game, "ars_routes", None) or self.routes or [])
        routes_path = self.routes_path

        if routes_path is None:
            scenario = getattr(game, "scenario", None)
            if scenario:
                routes_path = Path(f"{scenario}_ars_routes.json")
            elif self.map_path is not None:
                routes_path = self._routes_path_from_map(self.map_path)
            else:
                routes_path = Path("zone_6_ars_routes.json")

        log("[ARS] preparing predictive schedule and conflict map...")
        self.schedule = ensure_schedule(game, routes_path, self.routes, force=True, log=log)

        predictive_count = sum(1 for _ in (self.schedule.get("routes", []) or []))
        log(f"[ARS] schedule contains {predictive_count} predictive path(s)")

        self.build_conflicts(game, log=log)
        self._prepared = True
        return self.schedule

    def build_conflicts(self, game, log=print):
        self.conflicts = {}
        self.conflicts_by_entry = {}
        route_segments: List[Dict[str, Any]] = []
        self.path_hop_coords = {}
        schedule_routes = self.schedule.get("routes", []) or []
        
        for schedule_route_index, route in enumerate(schedule_routes):
            timetable_index = route.get("timetable_index")
            paths = route.get("paths", []) or []

            for path_index, path in enumerate(paths):
                coords = path.get("coords", []) if isinstance(path, dict) else []
                signal_hops: Dict[Tuple[Coord, Coord], set] = {}

                for item in coords:
                    entry = _schedule_entry_signal(item)
                    exit_signal = _schedule_exit_signal(item)
                    if entry is None or exit_signal is None:
                        continue
                    try:
                        position = _coord(item)
                    except (ValueError, TypeError):
                        continue
                    hop = _signal_key(entry, exit_signal)
                    signal_hops.setdefault(hop, set()).add(position)

                for hop, coordinates in signal_hops.items():
                    # ⚡ Cache the physical coordinates for this specific path hop
                    self.path_hop_coords[(timetable_index, path_index, hop[0], hop[1])] = coordinates
                    
                    route_segments.append({
                        "timetable_index": timetable_index,
                        "path_index": path_index,
                        "schedule_route_index": schedule_route_index,
                        "entry_signal": hop[0],
                        "exit_signal": hop[1],
                        "coordinates": coordinates,
                    })

        coordinate_index: Dict[Coord, List[int]] = {}
        for segment_index, segment in enumerate(route_segments):
            for position in segment["coordinates"]:
                coordinate_index.setdefault(position, []).append(segment_index)

        candidate_pairs: set[Tuple[int, int]] = set()
        for segment_indices in coordinate_index.values():
            if len(segment_indices) < 2:
                continue
            unique_indices = list(set(segment_indices))
            for i in range(len(unique_indices)):
                left = unique_indices[i]
                for j in range(i + 1, len(unique_indices)):
                    right = unique_indices[j]
                    if left == right:
                        continue
                    candidate_pairs.add((left, right) if left < right else (right, left))

        for left_index, right_index in candidate_pairs:
            left = route_segments[left_index]
            right = route_segments[right_index]
            overlap = left["coordinates"] & right["coordinates"]
            if not overlap:
                continue

            left_key = _signal_key(left["entry_signal"], left["exit_signal"])
            right_key = _signal_key(right["entry_signal"], right["exit_signal"])

            if left_key == right_key:
                continue

            conflict_key = left_key if left_key < right_key else right_key
            other_key = right_key if left_key < right_key else left_key
            record_key = (conflict_key, other_key)

            record = self.conflicts.get(record_key)
            if record is None:
                record = {
                    "route_a": {
                        "entry": list(left["entry_signal"]),
                        "exit": list(left["exit_signal"]),
                        "timetable_index": left["timetable_index"],
                        "path_index": left["path_index"],
                    },
                    "route_b": {
                        "entry": list(right["entry_signal"]),
                        "exit": list(right["exit_signal"]),
                        "timetable_index": right["timetable_index"],
                        "path_index": right["path_index"],
                    },
                    "overlap": [],
                }
                self.conflicts[record_key] = record

            overlap_list = record["overlap"]
            existing = {tuple(coord) for coord in overlap_list}
            for position in overlap:
                if position not in existing:
                    overlap_list.append(list(position))

        for record in self.conflicts.values():
            for side in ("route_a", "route_b"):
                route = record[side]
                entry = tuple(route["entry"])
                self.conflicts_by_entry.setdefault(entry, []).append(record)

        log(f"[ARS] conflict map contains {len(self.conflicts)} conflicting route pair(s)")
        return self.conflicts


    # ======================================================================
    # Train -> predicted route indexing
    # ======================================================================

        # ======================================================================
    # Train -> predicted route indexing
    # ======================================================================

    def _build_train_predictions(self, game, caches):
        now = float(getattr(game, "game_seconds", 0))
        horizon = now + HORIZON_SECONDS
        by_entry: Dict[Tuple[int, int], List[Dict[str, Any]]] = {}

        schedule_routes = self.schedule.get("routes", []) or []
        schedule_by_tt = {
            r.get("timetable_index"): r
            for r in schedule_routes
            if r.get("timetable_index") is not None
        }

        for train in getattr(game, "trains", []) or []:
            timetable_index = getattr(train, "timetable_index", None)
            if timetable_index not in schedule_by_tt:
                continue

            schedule_route = schedule_by_tt[timetable_index]
            paths = schedule_route.get("paths", []) or []
            if not paths:
                continue

            spawn_time = float(getattr(train, "game_seconds_at_spawn", 0))

            # =================================================================
            # 1. SUCCESSIVE PATH ELIMINATION LOGIC
            # =================================================================
            active_paths = list(enumerate(paths)) # [(0, path0), (1, path1), ...]

            def filter_by_max_intersect(paths_to_filter, target_coords):
                if not target_coords:
                    return paths_to_filter
                
                scores = []
                for idx, p in paths_to_filter:
                    path_set = {tuple(_coord(c)) for c in p.get("coords", []) if c}
                    scores.append((idx, p, len(path_set & target_coords)))
                    
                max_score = max((s[2] for s in scores), default=0)
                
                # Only eliminate if we actually found overlapping coordinates
                if max_score > 0:
                    return [(idx, p) for idx, p, score in scores if score == max_score]
                return paths_to_filter

            # Check 1: Eliminate using train.route_coords (FLAT LIST OF TUPLES)
            train_route_coords = set()
            for c in getattr(train, "route_coords", []) or []:
                if c:
                    try:
                        train_route_coords.add(tuple(_coord(c)))
                    except (ValueError, TypeError):
                        pass

            active_paths = filter_by_max_intersect(active_paths, train_route_coords)

            # Check 2: Eliminate using train.coords (LIST OF LISTS OF TUPLES)
            if len(active_paths) > 1:
                train_phys_coords = set()
                for coord_group in getattr(train, "coords", []) or []:
                    if isinstance(coord_group, (list, tuple)):
                        for c in coord_group:
                            if c:
                                try:
                                    train_phys_coords.add(tuple(_coord(c)))
                                except (ValueError, TypeError):
                                    pass
                    else:
                        # Fallback just in case
                        if coord_group:
                            try:
                                train_phys_coords.add(tuple(_coord(coord_group)))
                            except (ValueError, TypeError):
                                pass

                active_paths = filter_by_max_intersect(active_paths, train_phys_coords)


            # Check 3: Eliminate using entry signal's route_coords
            if len(active_paths) > 1:
                first_entry_signal_coord = None
                for _, p in active_paths:
                    for item in p.get("coords", []) or []:
                        entry = _schedule_entry_signal(item)
                        if entry:
                            first_entry_signal_coord = tuple(entry)
                            break
                    if first_entry_signal_coord:
                        break
                
                if first_entry_signal_coord:
                    entry_signal = _find_signal(game, first_entry_signal_coord, caches)
                    if entry_signal and getattr(entry_signal, "route_coords", None):
                        signal_route_coords = {
                            tuple(_coord(c)) for c in entry_signal.route_coords if c
                        }
                        active_paths = filter_by_max_intersect(active_paths, signal_route_coords)

            # =================================================================

            # Safely extract train's physical head coordinate
            head_coord = None
            train_coords_raw = getattr(train, "coords", [])
            if train_coords_raw and isinstance(train_coords_raw[0], (list, tuple)) and train_coords_raw[0]:
                try: head_coord = tuple(_coord(train_coords_raw[0][0]))
                except (IndexError, TypeError, ValueError): pass

            # TIME LOCK: Force alternative paths to share the exact same entry time
            entry_time_lock: Dict[Tuple[int, int], float] = {}

            # Generate predictions for the surviving active paths
            for path_index, path in active_paths:
                coords = path.get("coords", []) if isinstance(path, dict) else []
                head_index = -1
                
                if head_coord:
                    for i, item in enumerate(coords):
                        try:
                            if tuple(_coord(item)) == head_coord:
                                head_index = i; break
                        except (ValueError, TypeError): continue
                
                if head_index == -1:
                    if getattr(train, "status", "") == "spawning" or spawn_time >= now:
                        head_index = 0
                    else: continue

                delay = 0.0
                if 0 <= head_index < len(coords):
                    head_relative_time = _schedule_time(coords[head_index])
                    if head_relative_time is not None:
                        expected_absolute_time = spawn_time + head_relative_time
                        if now > expected_absolute_time:
                            delay = now - expected_absolute_time

                seen_hops = set()
                for item_index, item in enumerate(coords):
                    if item_index < head_index: continue

                    relative_time = _schedule_time(item)
                    if relative_time is None: continue

                    absolute_time = spawn_time + relative_time + delay
                    entry = _schedule_entry_signal(item)
                    exit_signal = _schedule_exit_signal(item)

                    if absolute_time < now: continue
                    if absolute_time > horizon: break
                    if entry is None or exit_signal is None: continue

                    entry_tuple = tuple(entry)
                    exit_tuple = tuple(exit_signal)

                    hop_key = (path_index, entry_tuple, exit_tuple)
                    if hop_key in seen_hops: continue
                    seen_hops.add(hop_key)

                    if entry_tuple not in entry_time_lock:
                        entry_time_lock[entry_tuple] = absolute_time
                    sync_time = entry_time_lock[entry_tuple]

                    by_entry.setdefault(entry_tuple, []).append({
                        "train": train,
                        "timetable_index": timetable_index,
                        "path_index": path_index,
                        "entry_signal": entry_tuple,
                        "exit_signal": exit_tuple,
                        "absolute_time": sync_time,
                        "relative_time": relative_time,
                        "delay": delay,
                        "coord_index": item_index,
                    })

        return by_entry


    # ======================================================================
    # Route ordering / dependency helpers
    # ======================================================================


    def _previous_hop_is_set(self, game, prediction: Dict[str, Any], caches) -> bool:
        train = prediction["train"]
        timetable_index = prediction["timetable_index"]
        path_index = prediction["path_index"]
        current_relative = prediction["relative_time"]
        headcode = getattr(train, "headcode", "UNKNOWN")

        head_coord = None
        train_coords = getattr(train, "coords", [])
        if train_coords:
            try:
                head_coord = _coord(train_coords[0][0])
            except (IndexError, TypeError, ValueError):
                try:
                    head_coord = _coord(train_coords[0])
                except (IndexError, TypeError, ValueError):
                    pass

        schedule_routes = self.schedule.get("routes", []) or []
        target_path = None
        for route in schedule_routes:
            if route.get("timetable_index") != timetable_index:
                continue
            paths = route.get("paths", []) or []
            if path_index < len(paths):
                target_path = paths[path_index]
            break

        if not target_path:
            return True

        coords = target_path.get("coords", []) or []
        head_index = -1
        if head_coord:
            for i, item in enumerate(coords):
                try:
                    if _coord(item) == head_coord:
                        head_index = i
                        break
                except (ValueError, TypeError):
                    continue

        previous_hop = None
        previous_hop_last_index = -1

        for i, item in enumerate(coords):
            relative_time = _schedule_time(item)
            if relative_time is None:
                continue
            if relative_time >= current_relative:
                break
            entry = _schedule_entry_signal(item)
            exit_signal = _schedule_exit_signal(item)
            if entry is not None and exit_signal is not None:
                previous_hop = (tuple(entry), tuple(exit_signal))
                previous_hop_last_index = i

        if previous_hop is None:
            return True

        active_hop = None
        if head_index != -1:
            e = _schedule_entry_signal(coords[head_index])
            x = _schedule_exit_signal(coords[head_index])
            if e is not None and x is not None:
                active_hop = (tuple(e), tuple(x))

        if active_hop == previous_hop:
            return True
        if head_index > previous_hop_last_index:
            return True

        previous_entry, previous_exit = previous_hop
        is_set = self._route_is_already_set(game, previous_entry, previous_exit, caches)
        
        if not is_set:
            print(
                "[ARS DEBUG] "
                f"[Train:{headcode}] T{timetable_index}/P{path_index} "
                f"previous_hop {previous_entry}->{previous_exit} is NOT set. "
                f"(Train is currently at hop {active_hop})"
            )
        return is_set


    # ======================================================================
    # Physical safety check
    # ======================================================================

    # In ars1.py

    def _route_has_headcode(self, game, coords, caches: Dict) -> bool:
        if not coords:
            return False
        try:
            # Ensure we are working with a set of tuples
            route_coords = {tuple(_coord(c)) for c in coords}
        except (TypeError, ValueError):
            # If conversion fails for any reason, assume it's occupied for safety
            return True
        
        # The caches["headcodes"] set is already composed of tuples now.
        return bool(route_coords & caches["headcodes"])


    def _route_has_conflict(self, route_key: Tuple[Coord, Coord]) -> bool:
        entry, exit_signal = route_key
        for record in self.conflicts_by_entry.get(entry, []):
            for side in ("route_a", "route_b"):
                route = record[side]
                if tuple(route["entry"]) == entry and tuple(route["exit"]) == exit_signal:
                    return True
        return False

    def print_conflicts(self, limit: Optional[int] = None):
        records = list(self.conflicts.values())
        if limit is not None:
            records = records[:limit]
        print(f"[ARS] {len(self.conflicts)} precomputed conflict(s)")
        for index, record in enumerate(records):
            a = record["route_a"]
            b = record["route_b"]
            print(
                f"[ARS CONFLICT {index}] "
                f"T{a['timetable_index']}/P{a['path_index']} "
                f"{tuple(a['entry'])} -> {tuple(a['exit'])}  <->  "
                f"T{b['timetable_index']}/P{b['path_index']} "
                f"{tuple(b['entry'])} -> {tuple(b['exit'])}"
            )

    def save_conflicts(self, path: str | Path) -> str:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "horizon_seconds": HORIZON_SECONDS,
            "conflicts": list(self.conflicts.values()),
        }
        with destination.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        return str(destination)


    # ======================================================================
    # Route attempt
    # ======================================================================

    def _route_is_already_set(self, game, entry: Coord, exit_signal: Coord, caches) -> bool:
        signal = _find_signal(game, entry, caches)
        if signal is None:
            return False

        # Check for commitment using route_coords array length instead of boolean flag
        signal_route_coords = getattr(signal, "route_coords", None)
        if signal_route_coords is not None and len(signal_route_coords) > 0:
            next_signal = getattr(signal, "next_signal", None)
            if next_signal is None:
                return True
            return tuple(getattr(next_signal, "coord", ())) == tuple(exit_signal)

        return False

    def _try_route(self, game, prediction: Dict[str, Any], caches: Dict) -> Tuple[bool, str]:
        train = prediction["train"]
        headcode = getattr(train, "headcode", "UNKNOWN")
        entry_coord = prediction["entry_signal"]
        exit_coord = prediction["exit_signal"]
        timetable_index = prediction["timetable_index"]
        path_index = prediction["path_index"]

        hop_key = (timetable_index, path_index, entry_coord, exit_coord)
        hop_coords = getattr(self, "path_hop_coords", {}).get(hop_key, set())

        # 1. PHYSICAL SUCCESS: Train is already inside this hop!
        train_body_coords = set()
        for coord_group in getattr(train, "coords", []) or []:
            if isinstance(coord_group, (list, tuple)):
                for c in coord_group:
                    if c:
                        try: train_body_coords.add(tuple(_coord(c)))
                        except (ValueError, TypeError): pass
            else:
                if coord_group:
                    try: train_body_coords.add(tuple(_coord(coord_group)))
                    except (ValueError, TypeError): pass

        if hop_coords and (hop_coords & train_body_coords):
            # Return TRUE so ARS stops looking for alternative paths
            return True, "ALREADY_IN_ROUTE"

        # 2. INSTANT COLLISION CHECK
        if hop_coords and (hop_coords & caches["collisions"]):
            return False, "COLLISION_DETECTED"

        if not self._previous_hop_is_set(game, prediction, caches):
            return False, "PREVIOUS_HOP_NOT_SET"

        entry_signal = _find_signal(game, entry_coord, caches)
        exit_signal = _find_signal(game, exit_coord, caches)

        if entry_signal is None: return False, "NO_ENTRY_SIGNAL"
        if exit_signal is None: return False, "NO_EXIT_SIGNAL"
        if not _is_manual(entry_signal): return False, "ENTRY_NOT_MANUAL"

        # 3. ALREADY SET LOGIC (UPDATED)
        # Use route_coords array to determine if the signal is committed
        signal_route_coords = getattr(entry_signal, "route_coords", None)
        if signal_route_coords is not None and len(signal_route_coords) > 0:
            if self._route_is_already_set(game, entry_coord, exit_coord, caches):
                # Route is correctly set for THIS specific path.
                return True, "ALREADY_SET"
            else:
                # Route is set, but it goes somewhere else. The path is committed.
                return False, "ROUTE_SET_FOR_OTHER_PATH"

        old_entry = getattr(game, "entry_signal", None)
        old_exit = getattr(game, "exit_signal", None)

        try:
            game.entry_signal = entry_signal
            game.exit_signal = exit_signal
            coords = game.set_route()

            if not coords:
                return False, "SET_ROUTE_FAILED"

            absolute_time = prediction["absolute_time"]
            now = float(getattr(game, "game_seconds", 0))
            print(f"[ARS SET] [Train:{headcode}] T{timetable_index}/P{path_index} {entry_coord} -> {exit_coord}")
            return True, "SUCCESS"

        except Exception as exc:
            return False, "EXCEPTION"
        finally:
            game.entry_signal = old_entry
            game.exit_signal = old_exit


    def tick(self, game):
        if not getattr(game, "ars_on", False): return
        if not self._prepared:
            if not hasattr(self, "is_ready") or not self.is_ready: return

        now = float(getattr(game, "game_seconds", 0))
        if self.last_attempt_second is not None and now - self.last_attempt_second < 0.9: return
        self.last_attempt_second = now

        # Build Master Collision Set
        collision_set = set()
        for signal in getattr(game, "signals", []):
            for coord in getattr(signal, "route_coords", []) or []:
                try: collision_set.add(tuple(_coord(coord)))
                except (ValueError, TypeError): pass

        for train in getattr(game, "trains", []):
            for coord_group in getattr(train, "coords", []) or []:
                if isinstance(coord_group, (list, tuple)):
                    for coord in coord_group:
                        try: collision_set.add(tuple(_coord(coord)))
                        except (ValueError, TypeError): pass
                else:
                    try: collision_set.add(tuple(_coord(coord_group)))
                    except (ValueError, TypeError): pass
            for coord in getattr(train, "route_coords", []) or []:
                try: collision_set.add(tuple(_coord(coord)))
                except (ValueError, TypeError): pass

        caches = {
            "signals": {tuple(s.coord): s for s in getattr(game, "signals", [])},
            "collisions": collision_set
        }

        predictions_by_entry = self._build_train_predictions(game, caches)
        if not predictions_by_entry: return

        set_count = 0
        fail_count = 0

        # Process each entry signal independently
        for entry, candidates in predictions_by_entry.items():
            
            # Sort to establish Train Priority (Time -> Delay -> Spawn Time -> Path Index)
            candidates.sort(
                key=lambda prediction: (
                    prediction["absolute_time"],
                    -prediction.get("delay", 0.0),
                    getattr(prediction["train"], "game_seconds_at_spawn", 0),
                    prediction["path_index"],
                )
            )

            # Group candidates by Train
            train_queue = []
            train_paths = {}
            for pred in candidates:
                t = pred["train"]
                if t not in train_paths:
                    train_queue.append(t)
                    train_paths[t] = []
                train_paths[t].append(pred)

            signal_claimed = False

            # Loop through trains in order of priority (1st place, 2nd place, etc)
            for train in train_queue:
                if signal_claimed:
                    break 
                
                # Loop through the current train's paths (Path 0, Path 1, etc)
                for prediction in train_paths[train]:
                    headcode = getattr(train, "headcode", "UNKNOWN")
                    path_idx = prediction["path_index"]
                    
                    success, reason = self._try_route(game, prediction, caches)
                    
                    if success:
                        signal_claimed = True
                        if reason == "SUCCESS":
                            set_count += 1
                        break # Success! Stop trying alternative paths for this train.
                    else:
                        fail_count += 1
                        if hasattr(game, "display_class") and hasattr(game.display_class, "add_log"):
                            path_type = "Primary" if path_idx == 0 else f"Alt Path {path_idx}"
                            game.display_class.add_log(
                                f"ARS: {headcode} {path_type} failed ({reason})."
                            )

                # ⚡ YOUR CHANGE: Do not go to the next train if this one failed.
                # If the first train in line is stuck, everyone behind it must wait!
                if not signal_claimed:
                    break


