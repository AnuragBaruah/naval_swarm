import json
import numpy as np
import plotly.graph_objects as go

# ---------- LOAD JSON ----------
with open("scenarios\S1.json", "r") as f:
    data = json.load(f)

tasks = data["tasks"]
area = data["area"]
T = data["sim_time"]

# ---------- TIME STEPS ----------
time_steps = np.linspace(0, T, 200)

frames = []

for t in time_steps:
    xs, ys, colors, texts = [], [], [], []

    for task in tasks:
        if task["t0"] <= t <= task["deadline"]:
            xs.append(task["x"])
            ys.append(task["y"])

            urgency = (t - task["t0"]) / (task["deadline"] - task["t0"])
            colors.append(urgency)

            texts.append(
                f"Task {task['id']}<br>"
                f"Value: {task['value']}<br>"
                f"Service: {task['service']:.1f}<br>"
                f"Deadline: {task['deadline']:.1f}"
            )

    frames.append(
        go.Frame(
            data=[
                go.Scatter(
                    x=xs,
                    y=ys,
                    mode="markers",
                    marker=dict(
                        size=14,
                        color=colors,
                        colorscale="Turbo",
                        cmin=0,
                        cmax=1,
                        showscale=True,
                        colorbar=dict(title="Urgency")
                    ),
                    text=texts,
                    hoverinfo="text"
                )
            ],
            name=f"{t:.1f}"
        )
    )

# ---------- INITIAL FIGURE ----------
fig = go.Figure(
    data=[
        go.Scatter(
            x=[],
            y=[],
            mode="markers",
            marker=dict(size=14)
        )
    ],

    layout=go.Layout(
    title="Dynamic Task Visualization",
    autosize=True,
    margin=dict(l=20, r=20, t=50, b=20),
    xaxis=dict(
        range=[area[0], area[1]],
        title="X",
        scaleanchor="y"   # keeps square aspect
    ),
    yaxis=dict(
        range=[area[2], area[3]],
        title="Y"
    ),
    updatemenus=[
        dict(
            type="buttons",
            buttons=[
                dict(
                    label="Play",
                    method="animate",
                    args=[None, {"frame": {"duration": 80, "redraw": True}}]
                )
            ]
        )
    ]
),
frames=frames
)

fig.show()
