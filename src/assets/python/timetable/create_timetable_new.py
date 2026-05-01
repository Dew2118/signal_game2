import json
from datetime import datetime, timedelta
import os
from collections import Counter

TIME_FORMAT = "%H:%M:%S"


def parse_time(t):
    return datetime.strptime(t, TIME_FORMAT)


def format_time(dt):
    return dt.strftime(TIME_FORMAT)


def detect_interval(times):
    """Detect most common interval instead of assuming first gap"""
    if len(times) < 2:
        return timedelta(minutes=10)

    diffs = []
    for i in range(1, len(times)):
        diffs.append(parse_time(times[i]) - parse_time(times[i - 1]))

    most_common = Counter(diffs).most_common(1)[0][0]
    return most_common


def expand_to_24h(times):
    """Expand timetable to full 24h using detected interval"""
    if not times:
        return times

    interval = detect_interval(times)
    start = parse_time(times[0])

    result = []
    current = start
    end = start.replace(hour=23, minute=59, second=59)

    while current <= end:
        result.append(format_time(current))
        current += interval

    return result


def build_global_schedule(data):
    """Flatten all spawn events into one list"""
    events = []

    for i, timetable in enumerate(data):
        for t in timetable.get("spawn_times", []):
            events.append({
                "time": parse_time(t),
                "timetable_index": i
            })

    return sorted(events, key=lambda x: x["time"])


def resolve_global_conflicts(events, min_gap_seconds):
    """Shift events forward, drop anything that exceeds 24h"""
    if not events:
        return events

    resolved = [events[0]]
    end_of_day = events[0]["time"].replace(hour=23, minute=59, second=59)

    for e in events[1:]:
        prev_time = resolved[-1]["time"]
        current_time = e["time"]

        gap = (current_time - prev_time).total_seconds()

        if gap < min_gap_seconds:
            current_time = prev_time + timedelta(seconds=min_gap_seconds)

        # 🚫 Drop anything beyond 24h
        if current_time > end_of_day:
            break  # everything after will also be later → safe to stop

        resolved.append({
            "time": current_time,
            "timetable_index": e["timetable_index"]
        })

    return resolved


def rebuild_timetables(data, resolved_events):
    """Put cleaned times back into timetables"""
    new_times = {i: [] for i in range(len(data))}

    for e in resolved_events:
        new_times[e["timetable_index"]].append(format_time(e["time"]))

    for i, timetable in enumerate(data):
        timetable["spawn_times"] = new_times[i]


def process_file(filename, min_gap_seconds=60):
    with open(filename, "r") as f:
        data = json.load(f)

    # Step 1: expand all to 24h
    for timetable in data:
        if timetable.get("spawn_times"):
            timetable["spawn_times"] = expand_to_24h(timetable["spawn_times"])

    # Step 2: build global schedule
    events = build_global_schedule(data)

    # Step 3: resolve conflicts globally (delay instead of delete)
    resolved = resolve_global_conflicts(events, min_gap_seconds)

    # Step 4: rebuild per timetable
    rebuild_timetables(data, resolved)

    output_file = filename.replace(".json", "_fixed.json")

    with open(output_file, "w") as f:
        json.dump(data, f, indent=4)

    print(f"Done. Output written to: {output_file}")


# ===== RUN =====
if __name__ == "__main__":
    CWD = os.path.dirname(__file__)
    JSON_PATH = os.path.join("..", "..", "..", "json")
    filename = os.path.join(CWD, JSON_PATH, "zone_E_timetable.json")

    process_file(filename, min_gap_seconds=120)