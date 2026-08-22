import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

Coord = Tuple[int, int]
TaggedCoord = Tuple[
    int,
    int,
    Optional[Coord],
    Optional[Coord],
]

SCHEDULE_VERSION = 2
SECONDS_PER_COORD = 1
MINIMUM_DWELL = 30
MAX_SPAWN_WALK = 500

# ---------------------------------------------------------------------------
# File / cache handling
# ---------------------------------------------------------------------------

def schedule_path_for_routes(routes_path: str | Path) -> Path:
    """Return the schedule filename corresponding to an ARS routes file."""
    routes_path = Path(routes_path)
    stem = routes_path.stem
    if stem.endswith("_ars_routes"):
        stem = stem[: -len("_ars_routes")]
    return routes_path.with_name(f"{stem}_ars_schedule.json")


def _routes_fingerprint(routes_path: str | Path) -> Optional[float]:
    try:
        return Path(routes_path).stat().st_mtime
    except OSError:
        return None


def save_schedule(path: str | Path, payload: Dict[str, Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=1)


def load_schedule(path: str | Path) -> Optional[Dict[str, Any]]:
    destination = Path(path)
    if not destination.exists():
        return None
    try:
        with destination.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError):
        return None

    if not isinstance(payload, dict):
        return None
    return payload


def is_current(payload: Optional[Dict[str, Any]], routes_path: str | Path) -> bool:
    """Return True if a cached schedule matches the current routes file."""
    if not payload:
        return False
    if payload.get("version") != SCHEDULE_VERSION:
        return False
    return payload.get("routes_mtime") == _routes_fingerprint(routes_path)


def ensure_schedule(
    game,
    routes_path: str | Path,
    routes: Sequence[Dict[str, Any]],
    force: bool = False,
    log=print,
) -> Dict[str, Any]:
    """Load the cached schedule or rebuild it when necessary."""
    schedule_path = schedule_path_for_routes(routes_path)
    payload = None if force else load_schedule(schedule_path)

    if is_current(payload, routes_path):
        log(f"[ARS] using cached schedule {schedule_path.name}")
        return payload

    log(f"[ARS] building schedule for {len(routes)} route(s)")
    
    # EXTREME OPTIMIZATION: Build O(1) Cache Dictionaries
    signal_cache = {}
    overlap_cache = {}
    
    for signal in getattr(game, "signals", []):
        coord_tuple = tuple(signal.coord)
        signal_cache[coord_tuple] = signal
        if getattr(signal, "signal_type", None) == "manual" and hasattr(signal, "overlap") and signal.overlap:
            overlap_cache[tuple(signal.overlap)] = signal
            
    timetable_cache = {t.get("index"): t for t in getattr(game, "timetables", []) or []}
    
    segment_cache = {}
    for seg in getattr(game, "annotated_segments", []) or []:
        station = seg.get("station")
        if station:
            segment_cache.setdefault(station, []).append(seg)
            
    caches = {
        "signals": signal_cache,
        "overlaps": overlap_cache,
        "timetables": timetable_cache,
        "segments": segment_cache
    }

    # Pass the caches to the builder
    payload = build_schedule(game, routes, caches, log=log)

    payload["routes_mtime"] = _routes_fingerprint(routes_path)
    payload["routes_file"] = Path(routes_path).name

    try:
        save_schedule(schedule_path, payload)
        log(f"[ARS] wrote schedule to {schedule_path.name}")

        debug_path = Path("DEBUG_ars_schedule_output.json").resolve()
        save_schedule(debug_path, payload)
        log(f"[ARS DEBUG] [SAVE] Saved a readable copy of the schedule for you to check at: {debug_path}")

    except OSError as exc:
        log(f"[ARS] could not write schedule: {exc}")

    return payload


# ---------------------------------------------------------------------------
# Signal helpers
# ---------------------------------------------------------------------------

def _coord_key(coord: Coord) -> str:
    return f"{int(coord[0])},{int(coord[1])}"


def _normalise_coord(coord) -> Coord:
    return (int(coord[0]), int(coord[1]))


def _coord_json(coord: Optional[Coord]):
    if coord is None:
        return None
    return [int(coord[0]), int(coord[1])]


def _find_signal(game, coord: Coord, caches=None):
    """Find a signal by its actual signal coordinate, heavily optimized."""
    wanted = tuple(coord)
    if caches and "signals" in caches:
        return caches["signals"].get(wanted)
        
    for signal in getattr(game, "signals", []):
        if tuple(signal.coord) == wanted:
            return signal
    return None


def _is_manual(signal) -> bool:
    return signal is not None and getattr(signal, "signal_type", None) == "manual"


def _is_automatic(signal) -> bool:
    return signal is not None and getattr(signal, "signal_type", None) == "automatic"


# ---------------------------------------------------------------------------
# Timetable helpers
# ---------------------------------------------------------------------------

def _find_timetable(game, timetable_index, caches=None) -> Optional[Dict[str, Any]]:
    if caches and "timetables" in caches:
        return caches["timetables"].get(timetable_index)
        
    for timetable in getattr(game, "timetables", None) or []:
        if timetable.get("index") == timetable_index:
            return timetable
    return None


def _start_coord(game, timetable) -> Optional[Coord]:
    try:
        coord = game.get_timetable_start_coord(timetable)
    except (AttributeError, TypeError, IndexError, KeyError):
        return None
    if not coord:
        return None
    return _normalise_coord(coord)


# ---------------------------------------------------------------------------
# Physical path finding
# ---------------------------------------------------------------------------

def walk_to_first_manual_signal(
    game,
    start_coord: Coord,
    direction: str,
    caches=None,
    target_manual_signal: Optional[Any] = None,
) -> Tuple[Optional[Any], List[Coord]]:
    """
    Walks from spawn until the first manual signal's overlap using the simple pathfinder.
    """
    x, y = start_coord
    last_char = "F"
    last_last_char = "F"
    coords: List[Coord] = [start_coord]

    if not (target_manual_signal and hasattr(target_manual_signal, "overlap") and target_manual_signal.overlap):
        return None, []

    target_overlap = tuple(target_manual_signal.overlap)
    
    try:
        for _ in range(MAX_SPAWN_WALK):
            if (x, y) == target_overlap:
                return (target_manual_signal, coords)

            result = game.path_find(game.lines, x, y, direction, direction, last_char, last_last_char, [])
            
            if not result or result[0] == -1:
                return None, []
            
            (x, y, direction, last_char, _, _, _) = result
            coords.append((int(x), int(y)))
        
        return None, []
    except Exception as exc:
        print(f"[ARS] targeted physical walk failed: {exc}")
        return None, []


def _coords_between(game, entry_signal, exit_signal, pair_cache) -> Optional[List[Coord]]:
    """Get the physical route between two signals via set_route()."""
    key = (tuple(entry_signal.coord), tuple(exit_signal.coord))
    if key in pair_cache:
        return pair_cache[key]

    previous_entry = getattr(game, "entry_signal", None)
    previous_exit = getattr(game, "exit_signal", None)

    game.entry_signal = entry_signal
    game.exit_signal = exit_signal

    try:
        coords = game.set_route(dont_set=True, ordered=True)
    except Exception as exc:
        print(f"[ARS] pair {key} failed: {exc}")
        coords = None
    finally:
        game.entry_signal = previous_entry
        game.exit_signal = previous_exit

    if coords:
        coords = [_normalise_coord(coord) for coord in coords]
    else:
        coords = None

    pair_cache[key] = coords
    return coords


def _find_physical_path_to_manual(game, automatic_signal, target_manual, pair_cache) -> Optional[List[Coord]]:
    """Physically continue from an automatic signal to a manual signal."""
    key = ("physical", tuple(automatic_signal.coord), tuple(target_manual.coord))
    if key in pair_cache:
        return pair_cache[key]

    last_char = "F"
    last_last_char = "F"
    direction = automatic_signal.direction
    
    if not hasattr(automatic_signal, "overlap") or not automatic_signal.overlap:
        return None
        
    x, y = automatic_signal.overlap
    coords: List[Coord] = []
    target_overlap = tuple(target_manual.overlap) if hasattr(target_manual, "overlap") else None

    try:
        for _ in range(MAX_SPAWN_WALK):
            if target_overlap and (x, y) == target_overlap:
                break

            result = game.path_find(
                game.lines, x, y, direction, direction, last_char, last_last_char, []
            )
            (x, y, direction, last_char, direction_change, last_last_char, temporary_characters) = result
            coords.append((int(x), int(y)))
        else:
            coords = None
    except Exception as exc:
        print(f"[ARS] physical continuation {automatic_signal.coord} -> {target_manual.coord} failed: {exc}")
        coords = None

    pair_cache[key] = coords
    return coords


# ---------------------------------------------------------------------------
# Coordinate helpers
# ---------------------------------------------------------------------------

def _append_unique_coords(
    destination: List[TaggedCoord],
    source: Sequence[Coord],
    entry_signal_coord: Optional[Coord] = None,
    exit_signal_coord: Optional[Coord] = None,
) -> None:
    if not source:
        return
        
    first_coord = _normalise_coord(source[0])
    if destination and destination[-1][0] == first_coord[0] and destination[-1][1] == first_coord[1]:
        source_to_process = source[1:]
    else:
        source_to_process = source

    for coord in source_to_process:
        x, y = _normalise_coord(coord)
        destination.append((x, y, entry_signal_coord, exit_signal_coord))


# ---------------------------------------------------------------------------
# Stop handling
# ---------------------------------------------------------------------------

def _stop_coords(game, stop, direction, caches=None) -> List[Coord]:
    station = stop.get("station")
    coords: List[Coord] = []
    
    if caches and "segments" in caches:
        segments = caches["segments"].get(station, [])
    else:
        segments = [s for s in (getattr(game, "annotated_segments", None) or []) if s.get("station") == station]

    for segment in segments:
        if direction == "right":
            point = segment.get("right", segment.get("end"))
        else:
            point = segment.get("left", segment.get("start"))

        if point:
            coords.append(_normalise_coord(point))

    return coords


def _at_stop(coord: Coord, stop_coords: Sequence[Coord]) -> bool:
    x, y = coord
    for (stop_x, stop_y) in stop_coords:
        if x == stop_x and abs(y - stop_y) <= 1:
            return True
    return False


def _dwell_for_stop(stop, arrival: int) -> Tuple[int, Optional[str]]:
    arrival_offset = stop.get("arrival_offset", 0)
    departure_offset = stop.get("departure_offset", 0)
    despawn = stop.get("despawn", False) is True

    if despawn:
        ends_with = "despawn"
    elif "change_timetable" in stop:
        ends_with = "change_timetable"
    else:
        ends_with = None

    if despawn:
        return (max(departure_offset - arrival, MINIMUM_DWELL), ends_with)
    if departure_offset == arrival_offset:
        return (0, ends_with)
    return (max(departure_offset - arrival, MINIMUM_DWELL), ends_with)


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def _normalise_signal_path(signal_path) -> List[Coord]:
    return [_normalise_coord(coord) for coord in (signal_path or [])]


def _build_signal_graph(game, signal_paths: Sequence[Sequence[Coord]], caches=None) -> Dict[str, Any]:
    nodes: Dict[str, Dict[str, Any]] = {}
    edges: Dict[str, Dict[str, Any]] = {}
    valid_paths = []

    for raw_path in signal_paths or []:
        path = _normalise_signal_path(raw_path)
        if len(path) < 2:
            continue

        cleaned = []
        for coord in path:
            if not cleaned or cleaned[-1] != coord:
                cleaned.append(coord)

        if len(cleaned) < 2:
            continue

        valid_paths.append(cleaned)

        for index, coord in enumerate(cleaned):
            node_id = _coord_key(coord)
            if node_id not in nodes:
                signal = _find_signal(game, coord, caches)
                nodes[node_id] = {
                    "id": node_id,
                    "coord": [coord[0], coord[1]],
                    "signal_type": getattr(signal, "signal_type", None) if signal else None,
                    "choices": [],
                    "incoming": [],
                }

            if index == 0:
                continue

            previous = cleaned[index - 1]
            from_id = _coord_key(previous)
            to_id = _coord_key(coord)
            edge_id = f"{from_id}->{to_id}"

            if edge_id not in edges:
                edges[edge_id] = {
                    "id": edge_id,
                    "from": from_id,
                    "to": to_id,
                }

    for edge in edges.values():
        from_node = nodes[edge["from"]]
        to_node = nodes[edge["to"]]
        if edge["to"] not in from_node["choices"]:
            from_node["choices"].append(edge["to"])
        if edge["from"] not in to_node["incoming"]:
            to_node["incoming"].append(edge["from"])

    for node in nodes.values():
        node["choices"].sort()
        node["incoming"].sort()

    return {
        "nodes": nodes,
        "edges": edges,
        "traversals": [[_coord_key(coord) for coord in path] for path in valid_paths],
    }


def _graph_edges_for_traversal(graph, traversal) -> List[str]:
    edge_ids = []
    for index in range(1, len(traversal)):
        from_id = traversal[index - 1]
        to_id = traversal[index]
        edge_id = f"{from_id}->{to_id}"
        if edge_id in graph["edges"]:
            edge_ids.append(edge_id)
    return edge_ids


# ---------------------------------------------------------------------------
# Segment generation
# ---------------------------------------------------------------------------

def _build_segment(game, entry_signal, exit_signal, pair_cache, physical_cache) -> Optional[Dict[str, Any]]:
    entry_coord = _normalise_coord(entry_signal.coord)
    exit_coord = _normalise_coord(exit_signal.coord)
    segment_id = f"{_coord_key(entry_coord)}->{_coord_key(exit_coord)}"

    if segment_id in physical_cache:
        return physical_cache[segment_id]

    coords = _coords_between(game, entry_signal, exit_signal, pair_cache)
    if coords is None:
        return None

    segment = {
        "id": segment_id,
        "entry_signal": _coord_json(entry_coord),
        "exit_signal": _coord_json(exit_coord),
        "exit_signal_type": getattr(exit_signal, "signal_type", None),
        "coords": [[x, y] for x, y in coords],
    }
    physical_cache[segment_id] = segment
    return segment


def _build_physical_continuation(game, automatic_signal, next_manual, pair_cache, physical_cache) -> Optional[Dict[str, Any]]:
    auto_coord = _normalise_coord(automatic_signal.coord)
    manual_coord = _normalise_coord(next_manual.coord)
    continuation_id = f"physical:{_coord_key(auto_coord)}->{_coord_key(manual_coord)}"

    if continuation_id in physical_cache:
        return physical_cache[continuation_id]

    coords = _find_physical_path_to_manual(game, automatic_signal, next_manual, pair_cache)
    if coords is None:
        return None

    continuation = {
        "id": continuation_id,
        "from_signal": _coord_json(auto_coord),
        "to_signal": _coord_json(manual_coord),
        "type": "physical_continuation",
        "coords": [[x, y] for x, y in coords],
    }
    physical_cache[continuation_id] = continuation
    return continuation


# ---------------------------------------------------------------------------
# Build one selected traversal
# ---------------------------------------------------------------------------

def _build_traversal_schedule(
    game,
    traversal,
    graph,
    segments,
    physical_continuations,
    start_coord,
    direction,
    stops,
    pair_cache,
    caches=None,
    log=print,
    primary_first_signal: Optional[Any] = None,
) -> Optional[Dict[str, Any]]:
    
    signal_coords = [_normalise_coord(graph["nodes"][node_id]["coord"]) for node_id in traversal]
    if len(signal_coords) < 2: return None

    signals = [_find_signal(game, coord, caches) for coord in signal_coords]
    if any(s is None for s in signals): return None

    first_manual_index = next((i for i, s in enumerate(signals) if _is_manual(s)), None)
    if first_manual_index is None: return None
    
    first_manual_signal = signals[first_manual_index]

    initial_seconds = 0
    is_divergent = False
    if primary_first_signal and first_manual_signal:
        if tuple(primary_first_signal.coord) != tuple(first_manual_signal.coord):
            is_divergent = True
            initial_seconds = 60
    
    # --- FINAL UNIFIED FALLBACK LOGIC ---
    
    # Attempt the simple physical walk first.
    _, spawn_walk_coords = walk_to_first_manual_signal(
        game,
        start_coord,
        direction,
        caches,
        target_manual_signal=first_manual_signal,
    )
    
    # If the walk fails for ANY reason (primary or divergent), fall back to a direct link.
    if not spawn_walk_coords:
        if is_divergent:
            log(f"[ARS BUILDER] Divergent path. Starting directly from overlap of signal {first_manual_signal.coord} with 60s penalty.")
            # For divergent, the path starts ONLY from the overlap.
            spawn_walk_coords = []
        else:
            log(f"[ARS BUILDER] Primary path walk failed. Falling back to direct link from spawn for signal {first_manual_signal.coord}.")
            # For primary, the path starts from the spawn point.
            spawn_walk_coords = [start_coord]

        # In both fallback cases, we link to the signal's overlap.
        if hasattr(first_manual_signal, "overlap") and first_manual_signal.overlap:
            spawn_walk_coords.append(_normalise_coord(first_manual_signal.overlap))
        else:
             log(f"[ARS BUILDER] Traversal failed: Fallback failed because signal {first_manual_signal.coord} has no overlap.")
             return None

    coords: List[TaggedCoord] = []
    _append_unique_coords(coords, spawn_walk_coords, None, None)

    # ... (The rest of the function remains unchanged) ...
    current_manual = first_manual_signal
    current_index = first_manual_index
    while True:
        next_index = current_index + 1
        if next_index >= len(signals): break
        exit_signal = signals[next_index]
        segment_id = f"{_coord_key(tuple(current_manual.coord))}->{_coord_key(tuple(exit_signal.coord))}"
        segment = segments.get(segment_id)
        if segment is None:
            log(f"[ARS BUILDER] Traversal failed: Missing pre-built segment {segment_id}.")
            return None
        segment_coords = [_normalise_coord(c) for c in segment["coords"]]
        try:
            overlap_coord = _normalise_coord(current_manual.overlap)
            if not segment_coords or _normalise_coord(segment_coords[0]) != overlap_coord:
                segment_coords.insert(0, overlap_coord)
        except (AttributeError, TypeError): overlap_coord = None
        entry_c = _normalise_coord(current_manual.coord)
        exit_c = _normalise_coord(exit_signal.coord)
        block_start_idx = 0
        if entry_c in segment_coords: block_start_idx = segment_coords.index(entry_c)
        elif overlap_coord and overlap_coord in segment_coords: block_start_idx = segment_coords.index(overlap_coord) + 1
        _append_unique_coords(coords, segment_coords[:block_start_idx], None, None)
        _append_unique_coords(coords, segment_coords[block_start_idx:], entry_c, exit_c)
        if _is_manual(exit_signal):
            current_manual, current_index = exit_signal, next_index
            continue
        next_manual_index = next((i for i, s in enumerate(signals[next_index + 1:], start=next_index + 1) if _is_manual(s)), None)
        if next_manual_index is None: break
        next_manual = signals[next_manual_index]
        continuation_id = f"physical:{_coord_key(tuple(exit_signal.coord))}->{_coord_key(tuple(next_manual.coord))}"
        continuation = physical_continuations.get(continuation_id)
        if continuation is None:
            log(f"[ARS BUILDER] Traversal failed: Missing physical continuation {continuation_id}.")
            return None
        _append_unique_coords(coords, [_normalise_coord(c) for c in continuation["coords"]], None, None)
        current_manual, current_index = next_manual, next_manual_index
    return _apply_times(game, coords, stops, direction, signal_coords, caches, initial_seconds=initial_seconds)
    
# ---------------------------------------------------------------------------
# Timing
# ---------------------------------------------------------------------------

def _apply_times(
    game,
    coords: List[TaggedCoord],
    stops: Sequence[Dict[str, Any]],
    direction: str,
    signal_coords: List[Coord],
    caches=None,
    initial_seconds: int = 0,
) -> Dict[str, Any]:
    """Apply coordinate timing and stop dwell times."""
    timed: List[List[Any]] = []
    stop_times: List[Dict[str, Any]] = []
    
    seconds = initial_seconds
    stop_index = 0
    ends_with = "end"
    continues_as = None
    working_direction = direction

    stop_coords = _stop_coords(game, stops[0], working_direction, caches) if stops else []

    def _signal_json(signal_coord):
        return _coord_json(signal_coord)

    for position, tagged_coord in enumerate(coords):
        x, y, entry_signal_coord, exit_signal_coord = tagged_coord
        coord = (x, y)

        if position:
            seconds += SECONDS_PER_COORD

        if stop_index < len(stops) and stop_coords and _at_stop(coord, stop_coords):
            stop = stops[stop_index]
            dwell, stop_ends_with = _dwell_for_stop(stop, seconds)
            
            stop_times.append({
                "station": stop.get("station"),
                "arrive": seconds,
                "depart": (seconds + dwell),
            })
            seconds += dwell

            if stop.get("reverse_direction"):
                working_direction = "left" if working_direction == "right" else "right"

            stop_index += 1
            stop_coords = _stop_coords(game, stops[stop_index], working_direction, caches) if stop_index < len(stops) else []

            if stop_ends_with:
                ends_with = stop_ends_with
            continues_as = stop.get("change_timetable")

            timed.append([
                coord[0], coord[1], seconds,
                _signal_json(entry_signal_coord), _signal_json(exit_signal_coord),
            ])

            if stop_ends_with == "despawn" or stop_ends_with == "change_timetable":
                break

        timed.append([
            coord[0], coord[1], seconds,
            _signal_json(entry_signal_coord), _signal_json(exit_signal_coord),
        ])

    return {
        "signals": [[x, y] for x, y in signal_coords],
        "coords": timed,
        "stops": stop_times,
        "ends_with": ends_with,
        "continues_as": continues_as,
    }


# ---------------------------------------------------------------------------
# Main schedule builder
# ---------------------------------------------------------------------------

def build_schedule(
    game,
    routes: Sequence[Dict[str, Any]],
    caches=None,
    log=print,
) -> Dict[str, Any]:
    
    pair_cache: Dict[Any, Optional[List[Coord]]] = {}
    physical_segments: Dict[str, Dict[str, Any]] = {}
    physical_continuations: Dict[str, Dict[str, Any]] = {}
    entries = []

    for route in routes or []:
        if not isinstance(route, dict):
            continue

        timetable_index = route.get("timetable_index")
        timetable = _find_timetable(game, timetable_index, caches)

        if timetable is None:
            log(f"[ARS] no timetable for index {timetable_index}, skipped")
            continue

        direction = timetable.get("direction", "right")
        start_coord = _start_coord(game, timetable)

        if start_coord is None:
            log(f"[ARS] no start coord for index {timetable_index}, skipped")
            continue

        signal_paths = route.get("signal_paths") or []
        if not signal_paths and route.get("signals"):
            signal_paths = [route["signals"]]

        if not signal_paths:
            log(f"[ARS] index {timetable_index}: no signal paths")
            continue

        graph = _build_signal_graph(game, signal_paths, caches)

        if not graph["traversals"]:
            log(f"[ARS] index {timetable_index}: no valid traversals")
            continue

        for edge in graph["edges"].values():
            from_coord = graph["nodes"][edge["from"]]["coord"]
            to_coord = graph["nodes"][edge["to"]]["coord"]

            entry_signal = _find_signal(game, tuple(from_coord), caches)
            exit_signal = _find_signal(game, tuple(to_coord), caches)

            if entry_signal is None or exit_signal is None:
                log(f"[ARS] missing signal for edge {edge['id']}")
                continue

            if not _is_manual(entry_signal):
                continue

            segment = _build_segment(game, entry_signal, exit_signal, pair_cache, physical_segments)
            if segment is not None:
                physical_segments[segment["id"]] = segment

        for traversal in graph["traversals"]:
            signal_objects = []
            for node_id in traversal:
                coord = graph["nodes"][node_id]["coord"]
                signal = _find_signal(game, tuple(coord), caches)
                if signal is None:
                    signal_objects = []
                    break
                signal_objects.append(signal)

            if not signal_objects:
                continue

            for index, signal in enumerate(signal_objects):
                if not _is_automatic(signal):
                    continue
                next_manual = None
                for later in signal_objects[index + 1:]:
                    if _is_manual(later):
                        next_manual = later
                        break
                if next_manual is None:
                    continue

                continuation = _build_physical_continuation(
                    game, signal, next_manual, pair_cache, physical_continuations
                )
                if continuation:
                    physical_continuations[continuation["id"]] = continuation

        # Determine the primary (first) traversal's starting signal.
        primary_first_signal = None
        if graph["traversals"]:
            primary_traversal = graph["traversals"][0]
            for node_id in primary_traversal:
                node = graph["nodes"][node_id]
                if node.get("signal_type") == "manual":
                    primary_first_signal = _find_signal(game, tuple(node["coord"]), caches)
                    break
        
        paths = []
        for traversal_index, traversal in enumerate(graph["traversals"]):
            simulated = _build_traversal_schedule(
                game,
                traversal,
                graph,
                physical_segments,
                physical_continuations,
                start_coord,
                direction,
                timetable.get("stops", []),
                pair_cache,
                caches,
                log,
                primary_first_signal=primary_first_signal,
            )

            if simulated is None:
                continue

            simulated["traversal_index"] = traversal_index
            simulated["traversal"] = list(traversal)
            simulated["edge_ids"] = _graph_edges_for_traversal(graph, traversal)
            paths.append(simulated)

        if not paths:
            log(f"[ARS] index {timetable_index}: no path could be simulated")
            continue

        entries.append({
            "timetable_index": timetable_index,
            "start_coord": [start_coord[0], start_coord[1]],
            "direction": direction,
            "graph": graph,
            "paths": paths,
        })

        primary = paths[0]
        log(
            f"[ARS] index {timetable_index}: {len(paths)} traversal(s), "
            f"{len(graph['nodes'])} graph node(s), {len(graph['edges'])} edge(s), "
            f"{primary['coords'][-1][2]}s on primary traversal"
        )

    return {
        "version": SCHEDULE_VERSION,
        "scenario": getattr(game, "scenario", None),
        "segments": {seg_id: seg for seg_id, seg in physical_segments.items()},
        "physical_continuations": {cont_id: cont for cont_id, cont in physical_continuations.items()},
        "routes": entries,
    }
