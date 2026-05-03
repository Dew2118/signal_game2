import json
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import os

CYCLE_LENGTH = 2880
CWD = os.path.dirname(__file__)
JSON_PATH = os.path.join("..", "..", "..", "json")


# ---------------- TIME ----------------
def time_to_seconds(t):
    h, m, s = map(int, t.split(":"))
    return h * 3600 + m * 60 + s


# ---------------- LOAD ----------------
def load_data(filename):
    path_name = os.path.join(CWD, JSON_PATH, filename)
    with open(path_name, "r") as f:
        return json.load(f)


# ---------------- PLATFORM LOGIC ----------------
def normalize_platform(platform):
    if not platform:
        return "MAIN"

    p = platform.upper().strip()

    if p in ["UP", "DOWN"]:
        return "MAIN"

    parts = p.split()

    if len(parts) == 1:
        return "MAIN"

    extra = [x for x in parts if x not in ["UP", "DOWN"]]

    return " ".join(extra) if extra else "MAIN"


def get_display_station(station, platform):
    group = normalize_platform(platform)
    return station if group == "MAIN" else f"{station} ({group})"


# ---------------- STATION ORDER ----------------
def extract_stations(data):
    routes = []

    for entry in data:
        route = []

        route.append(get_display_station(
            entry["start_location"]["station"],
            entry["start_location"].get("platform", "")
        ))

        for stop in entry["stops"]:
            route.append(get_display_station(
                stop["station"],
                stop.get("platform", "")
            ))

        routes.append(route)

    routes.sort(key=len, reverse=True)

    ordered = []
    seen = set()

    for station in routes[0]:
        if station not in seen:
            ordered.append(station)
            seen.add(station)

    for route in routes[1:]:
        for i, station in enumerate(route):
            if station in seen:
                continue

            prev_station = route[i - 1] if i > 0 else None
            next_station = route[i + 1] if i < len(route) - 1 else None

            if prev_station in seen:
                idx = ordered.index(prev_station)
                ordered.insert(idx + 1, station)
            elif next_station in seen:
                idx = ordered.index(next_station)
                ordered.insert(idx, station)
            else:
                ordered.append(station)

            seen.add(station)

    return ordered


def build_station_index(stations):
    return {station: i for i, station in enumerate(stations)}


# ---------------- CHAINING ----------------
def build_train_path(entry, data, base_time, station_index):
    times = []
    positions = []

    visited = set()
    current_entry = entry
    current_time = base_time

    start_station = get_display_station(
        current_entry["start_location"]["station"],
        current_entry["start_location"].get("platform", "")
    )

    times.append(current_time)
    positions.append(station_index[start_station])

    while True:
        stops = current_entry["stops"]

        for stop in stops:
            station_name = get_display_station(
                stop["station"],
                stop.get("platform", "")
            )

            arrival = current_time + stop["arrival_offset"]
            departure = current_time + stop["departure_offset"]

            times.append(arrival)
            positions.append(station_index[station_name])

            times.append(departure)
            positions.append(station_index[station_name])

            if "change_timetable" in stop:
                next_idx = stop["change_timetable"]

                if next_idx in visited:
                    return times, positions

                visited.add(next_idx)
                current_entry = data[next_idx]
                current_time = departure
                break
        else:
            break

    return times, positions


# ---------------- PLOT ----------------
def plot_timetable(data):
    stations = extract_stations(data)
    station_index = build_station_index(stations)

    fig, ax = plt.subplots(figsize=(14, 7))

    # Color mapping by headcode
    unique_headcodes = list(set(
        entry.get("headcode_prefix", str(i))
        for i, entry in enumerate(data)
    ))

    cmap = cm.get_cmap("tab20", len(unique_headcodes))
    headcode_to_color = {
        hc: cmap(i) for i, hc in enumerate(unique_headcodes)
    }

    for entry in data:
        if not entry["spawn_times"]:
            continue

        headcode = entry.get("headcode_prefix", "?")
        color = headcode_to_color[headcode]

        for spawn in entry["spawn_times"]:
            base_time = time_to_seconds(spawn)

            times, positions = build_train_path(
                entry, data, base_time, station_index
            )

            # Clip
            times_clipped = []
            positions_clipped = []

            for t, p in zip(times, positions):
                if 0 <= t <= CYCLE_LENGTH:
                    times_clipped.append(t)
                    positions_clipped.append(p)

            if len(times_clipped) > 1:
                ax.plot(
                    times_clipped,
                    positions_clipped,
                    linewidth=1.5,
                    color=color,
                    alpha=0.85
                )

                # ---- LABEL HEADCODE ----
                mid = len(times_clipped) // 2
                ax.text(
                    times_clipped[mid],
                    positions_clipped[mid],
                    headcode,
                    fontsize=7,
                    color=color,
                    ha='center',
                    va='center',
                    bbox=dict(
                        facecolor='white',
                        alpha=0.6,
                        edgecolor='none',
                        pad=1
                    )
                )

    ax.set_yticks(range(len(stations)))
    ax.set_yticklabels(stations, fontsize=8)

    ax.set_xlabel("Time (seconds)")
    ax.set_ylabel("Stations")
    ax.set_title("Train Timetable Graph")

    ax.grid(True)
    ax.invert_yaxis()

    plt.tight_layout()
    plt.show()


# ---------------- MAIN ----------------
if __name__ == "__main__":
    data = load_data("zone_A_timetable.json")
    plot_timetable(data)