import json
import random
from datetime import timedelta
import os
CWD = os.path.dirname(__file__)
JSON_PATH = os.path.join("..", "..","..", "json")
INPUT_FILE = os.path.join(CWD, JSON_PATH, "zone_6_timetable.json")
OUTPUT_FILE = os.path.join(CWD, JSON_PATH, "randomized.json")

REMOVE_CHANCE = 0.10
MIN_SHIFT = -20
MAX_SHIFT = 20

def parse_time(t):
    h, m, s = map(int, t.split(":"))
    return timedelta(hours=h, minutes=m, seconds=s)

def format_time(td):
    total = int(td.total_seconds())
    if total < 0:
        total = 0
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h}:{m:02}:{s:02}"

with open(INPUT_FILE) as f:
    data = json.load(f)

for service in data:
    new_times = []

    for t in service["spawn_times"]:
        if random.random() < REMOVE_CHANCE:
            continue

        base = parse_time(t)
        shift = random.randint(MIN_SHIFT, MAX_SHIFT)
        new = base + timedelta(seconds=shift)

        new_times.append(format_time(new))

        # small chance to add an extra spawn
        if random.random() < 0.05:
            extra = new + timedelta(seconds=random.randint(60,180))
            new_times.append(format_time(extra))

    # keep chronological order
    new_times.sort(key=parse_time)

    service["spawn_times"] = new_times

with open(OUTPUT_FILE, "w") as f:
    json.dump(data, f, indent=4)

print("Randomized spawn file saved as", OUTPUT_FILE)