import json
import math
import plotly.graph_objects as go

# -------------------------------
# Load data
# -------------------------------
with open("viz.json", "r") as f:
    data = json.load(f)

num_agents = data["meta"]["num_agents"]
service_radius = data["meta"]["service_radius"] * 2  # Make it 5x larger for visibility
timeline = data["timeline"]

colors = [
    "#FF1744",  # Bright red
    "#FFD700",  # Gold
    "#00E676",  # Bright green
    "#FF6F00",  # Deep orange
    "#E040FB",  # Purple
    "#FFFF00",  # Yellow
    "#FF4081",  # Pink
    "#00BFA5",  # Teal
    "#FFFFFF",  # White
    "#FF9100"   # Amber
]

fig = go.Figure()
frames = []

# -------------------------------
# Helper: heading from velocity
# -------------------------------
def heading_deg(x1, y1, x0, y0):
    dx = x1 - x0
    dy = y1 - y0
    if dx == 0 and dy == 0:
        return 0
    return math.degrees(math.atan2(dy, dx)) - 90  # triangle-up correction

# -------------------------------
# Build frames
# -------------------------------
for i, frame in enumerate(timeline):
    traces = []
    shapes = []

    # ---- TASKS AS SERVICE CIRCLES ----
    for task in frame.get("tasks", []):
        shapes.append(
            dict(
                type="circle",
                xref="x",
                yref="y",
                x0=task["x"] - service_radius,
                y0=task["y"] - service_radius,
                x1=task["x"] + service_radius,
                y1=task["y"] + service_radius,
                line=dict(color="orange", width=2),
                fillcolor="rgba(255,165,0,0.35)",
                layer="below"
            )
        )

    # ---- TASK LABELS ----
    if frame.get("tasks"):
        traces.append(
            go.Scatter(
                x=[t["x"] for t in frame["tasks"]],
                y=[t["y"] for t in frame["tasks"]],
                mode="text",
                text=[str(t["id"]) for t in frame["tasks"]],
                textfont=dict(size=11, color="black"),
                showlegend=False,
                hoverinfo="skip"
            )
        )

    # ---- AGENTS AS ROTATED TRIANGLES ----
    for aid in range(num_agents):
        a = frame["agents"][aid]

        if i > 0:
            a_prev = timeline[i - 1]["agents"][aid]
            angle = heading_deg(a["x"], a["y"], a_prev["x"], a_prev["y"])
        else:
            angle = 0

        traces.append(
            go.Scatter(
                x=[a["x"]],
                y=[a["y"]],
                mode="markers+text",
                marker=dict(
                    symbol="triangle-up",
                    size=20,
                    angle=angle,
                    color=colors[aid],
                    line=dict(color="white", width=1.5)
                ),
                text=[str(aid)],
                textposition="middle center",
                textfont=dict(color="white", size=10),
                name=f"Agent {aid}",
                showlegend=(i == 0),
                hovertemplate=f"<b>Agent {aid}</b><br>X:%{{x:.1f}}<br>Y:%{{y:.1f}}<extra></extra>"
            )
        )

    # ---- AGENT TRAILS ----
    for aid in range(num_agents):
        px, py = [], []
        for t in range(i + 1):
            ag = timeline[t]["agents"][aid]
            px.append(ag["x"])
            py.append(ag["y"])

        traces.append(
            go.Scatter(
                x=px,
                y=py,
                mode="lines",
                line=dict(color=colors[aid], width=1.2, dash="dot"),
                opacity=0.4,
                showlegend=False,
                hoverinfo="skip"
            )
        )

    frame_layout = dict(title_text=f"Time: {frame['t']:.1f}")

    if shapes:
        frame_layout["shapes"] = shapes
    else:
        frame_layout["shapes"] = []  # FORCE CLEAR

    frames.append(
        go.Frame(
            data=traces,
            name=str(i),
            layout=frame_layout
        )
    )

# -------------------------------
# Initial frame setup
# -------------------------------
fig.frames = frames
first = timeline[0]

init_shapes = []
for task in first.get("tasks", []):
    init_shapes.append(
        dict(
            type="circle",
            xref="x",
            yref="y",
            x0=task["x"] - service_radius,
            y0=task["y"] - service_radius,
            x1=task["x"] + service_radius,
            y1=task["y"] + service_radius,
            line=dict(color="orange", width=2),
            fillcolor="rgba(255,165,0,0.35)",
            layer="below"
        )
    )

for aid in range(num_agents):
    a = first["agents"][aid]
    fig.add_trace(
        go.Scatter(
            x=[a["x"]],
            y=[a["y"]],
            mode="markers+text",
            marker=dict(
                symbol="triangle-up",
                size=20,
                color=colors[aid],
                line=dict(color="white", width=1.5)
            ),
            text=[str(aid)],
            textposition="middle center",
            textfont=dict(color="white", size=10),
            name=f"Agent {aid}"
        )
    )

    fig.add_trace(
        go.Scatter(
            x=[a["x"]],
            y=[a["y"]],
            mode="lines",
            line=dict(color=colors[aid], width=1.2, dash="dot"),
            opacity=0.4,
            showlegend=False
        )
    )

if first.get("tasks"):
    fig.add_trace(
        go.Scatter(
            x=[t["x"] for t in first["tasks"]],
            y=[t["y"] for t in first["tasks"]],
            mode="text",
            text=[str(t["id"]) for t in first["tasks"]],
            textfont=dict(size=11, color="black"),
            showlegend=False
        )
    )

# -------------------------------
# Layout
# -------------------------------
fig.update_layout(
    autosize=True,
    shapes=init_shapes,
    xaxis=dict(range=[0, 2000], title="X Position"),
    yaxis=dict(range=[0, 2000], title="Y Position", scaleanchor="x", scaleratio=1),
    plot_bgcolor="#5fbcde",  # Your preferred blue
    paper_bgcolor="#4a9ec4",  # Slightly darker blue for contrast
    hovermode="closest",
    margin=dict(l=80, r=80, t=100, b=150),
    updatemenus=[dict(
        type="buttons",
        buttons=[
            dict(label="▶ Play", method="animate",
                 args=[None, dict(frame=dict(duration=50, redraw=True), fromcurrent=True)]),
            dict(label="⏸ Pause", method="animate",
                 args=[[None], dict(frame=dict(duration=0), mode="immediate")])
        ]
    )],
    sliders=[dict(
        steps=[
            dict(method="animate",
                 args=[[str(i)], dict(mode="immediate")],
                 label=f"{timeline[i]['t']:.1f}")
            for i in range(len(timeline))
        ],
        currentvalue=dict(prefix="Time: ")
    )]
)

print("Opening visualization...")
fig.show()