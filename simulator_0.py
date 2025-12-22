import json
import matplotlib.pyplot as plt

# ---------- LOAD JSON ----------
json_path = "scenarios\S5.json"

with open(json_path, "r") as f:
    data = json.load(f)

tasks = data["tasks"]
area = data["area"]
comm = data["comm"]

# ---------- EXTRACT TASK DATA ----------
xs = [t["x"] for t in tasks]
ys = [t["y"] for t in tasks]
ids = [t["id"] for t in tasks]
t0 = [t["t0"] for t in tasks]
deadlines = [t["deadline"] for t in tasks]
service = [t["service"] for t in tasks]
value = [t["value"] for t in tasks]

# ---------- PLOT 1: TASK LOCATIONS ----------
plt.figure()
plt.scatter(xs, ys)
for i, tid in enumerate(ids):
    plt.text(xs[i], ys[i], str(tid), fontsize=8)

plt.title("Task Locations")
plt.xlabel("X")
plt.ylabel("Y")
plt.xlim(area[0], area[1])
plt.ylim(area[2], area[3])
plt.grid(True)
plt.show()

# ---------- PLOT 2: TIME WINDOWS ----------
plt.figure()
for i in range(len(tasks)):
    plt.plot([t0[i], deadlines[i]], [i, i])

plt.yticks(range(len(tasks)), ids)
plt.xlabel("Time")
plt.ylabel("Task ID")
plt.title("Task Time Windows (t0 → deadline)")
plt.grid(True)
plt.show()

# ---------- PLOT 3: SERVICE vs VALUE ----------
plt.figure()
plt.scatter(service, value)
plt.xlabel("Service Time")
plt.ylabel("Task Value")
plt.title("Service Time vs Value")
plt.grid(True)
plt.show()

# ---------- COMM SUMMARY ----------
print("Communication Model")
print("-------------------")
print(f"Bandwidth (kbps): {comm['kbps']}")
print(f"Packet loss probability: {comm['loss']}")
print(f"Jitter range (ms): {comm['jitter_ms']}")
