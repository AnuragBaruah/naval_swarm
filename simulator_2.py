import json
import plotly.graph_objects as go

with open("viz.json") as f:
    frames_data = json.load(f)

# infer bounds from data
xs, ys = [], []
for frame in frames_data:
    for task in frame["tasks"]:
        xs.append(task["x"])
        ys.append(task["y"])

xmin, xmax = min(xs) - 50, max(xs) + 50
ymin, ymax = min(ys) - 50, max(ys) + 50

# build frames
frames = []
for frame in frames_data:
    tasks = frame["tasks"]

    frames.append(
        go.Frame(
            name=str(frame["t"]),
            data=[
                go.Scatter(
                    x=[t["x"] for t in tasks],
                    y=[t["y"] for t in tasks],
                    mode="markers",
                    marker=dict(size=10, color="red"),
                    text=[f"Task {t['id']}" for t in tasks],
                    hoverinfo="text"
                )
            ]
        )
    )

# initial figure
fig = go.Figure(
    data=frames[0].data,
    layout=go.Layout(
        title="Dynamic Task Visualization",
        xaxis=dict(range=[xmin, xmax]),
        yaxis=dict(range=[ymin, ymax], scaleanchor="x"),
        updatemenus=[{
            "type": "buttons",
            "buttons": [
                {
                    "label": "Play",
                    "method": "animate",
                    "args": [None, {"frame": {"duration": 150}, "fromcurrent": True}]
                },
                {
                    "label": "Pause",
                    "method": "animate",
                    "args": [[None], {"frame": {"duration": 0}}]
                }
            ]
        }],
        sliders=[{
            "steps": [
                {
                    "method": "animate",
                    "args": [[str(f["t"])], {"frame": {"duration": 0}}],
                    "label": str(f["t"])
                } for f in frames_data
            ],
            "currentvalue": {"prefix": "t = "}
        }]
    ),
    frames=frames
)

fig.show()
