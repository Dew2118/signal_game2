import json
import os
CWD = os.path.dirname(__file__)
JSON_PATH = os.path.join("..", "..","..", "json")
INPUT_FILE = os.path.join(CWD, JSON_PATH, "zone_6_timetable.json")
OUTPUT_FILE = os.path.join(CWD, JSON_PATH, "double_timetable.json")

def to_seconds(t):
    h, m, s = map(int, t.split(":"))
    return h*3600 + m*60 + s

def to_time(sec):
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h}:{m:02}:{s:02}"

with open(INPUT_FILE) as f:
    data = json.load(f)

for route in data:
    times = route["spawn_times"]
    if len(times) < 2:
        continue

    seconds = [to_seconds(t) for t in times]
    new = []

    for i in range(len(seconds)-1):
        new.append(seconds[i])
        mid = (seconds[i] + seconds[i+1]) // 2
        new.append(mid)

    new.append(seconds[-1])
    route["spawn_times"] = [to_time(t) for t in new]

with open(OUTPUT_FILE,"w") as f:
    json.dump(data,f,indent=4)