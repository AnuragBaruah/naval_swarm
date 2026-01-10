import argparse, importlib.util, json, math, os, random
from copy import deepcopy
import pygame


def load_team(team_path):
    spec = importlib.util.spec_from_file_location("team_mod", team_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, "Agent"):
        raise RuntimeError("Team file must define class Agent")
    return mod.Agent

def json_size_bytes(obj) -> int:
    return len(json.dumps(obj, separators=(",",":")).encode("utf-8"))

def dist(a, b):
    return math.hypot(a[0]-b[0], a[1]-b[1])

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

'''Pygame Visualization'''
def world_to_screen(x, y, area, screen_w, screen_h):
    xmin, xmax, ymin, ymax = area
    sx = int((x - xmin) / (xmax - xmin) * screen_w)
    sy = int(screen_h - (y - ymin) / (ymax - ymin) * screen_h)
    return sx, sy

class PygameVisualizer:
    def __init__(self, scn):
        pygame.init()
        self.screen = pygame.display.set_mode((1920, 1080), pygame.FULLSCREEN)
        self.W, self.H = self.screen.get_size()
        self.leaders_required = int(scn.get("roles", {}).get("leaders_required", 0))
        print(self.leaders_required)
        pygame.display.set_caption("Swarm Simulation")
        self.bg = pygame.image.load("images/backgound.png").convert()
        self.skull_img = pygame.image.load("images/dead.png").convert_alpha()
        self.skull_img = pygame.transform.smoothscale(self.skull_img, (40, 40))
        self.crown_img = pygame.image.load("images/crown.png").convert_alpha()
        self.crown_img = pygame.transform.scale_by(self.crown_img, 0.1)
        self.bg = pygame.transform.scale(self.bg, (self.W, self.H))
        self.area = scn["area"]
        self.service_radius = scn.get("service_radius", 10.0)
        self.clock = pygame.time.Clock()
        self.paused = False
        self.running = True
        self.font = pygame.font.SysFont("timesnewroman", 20)
        self.font2 = pygame.font.SysFont("timesnewroman", 80, bold=True)
        self.agent_colors = [
            (10, 60, 120),    # Sapphire Blue
            (205, 127, 50),   # Statuary Bronze
            (75, 54, 33),     # Espresso Brown
            (138, 51, 36),    # Burnt Umber
            (25, 25, 112),    # Midnight Blue
            (53, 94, 59),     # Deep Emerald
            (75, 0, 130),     # Royal Plum
            (0, 80, 90),      # Dark Teal
            (85, 107, 47),    # Olive Green
            (89, 41, 65),     # Dark Mulberry
        ]
        self.trail_colors = [
            (156, 186, 214),  # Very Light Sapphire Blue
            (238, 210, 180),  # Very Light Statuary Bronze
            (189, 178, 165),  # Very Light Espresso Brown
            (214, 170, 164),  # Very Light Burnt Umber
            (166, 166, 204),  # Very Light Midnight Blue
            (178, 202, 182),  # Very Light Deep Emerald
            (186, 166, 214),  # Very Light Royal Plum
            (163, 209, 214),  # Very Light Dark Teal
            (194, 206, 176),  # Very Light Olive Green
            (196, 170, 184),  # Very Light Dark Mulberry
        ]
        self.last_angle = {}
        self.trails = {}  # agent_id → list[(x,y)]

    # Handles close window, pause simulation
    def handle_events(self):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                self.running = False

            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    self.running = False
                if e.key == pygame.K_SPACE:
                    self.paused = not self.paused

    # Task
    def draw_task(self, task, time_t):
        # not started yet task
        if time_t < task["t0"]:
            return
        # completed -> disappear
        if task["done"]:
            return
        # dead → grey
        if time_t > task["deadline"]:
            circle_color = (160, 160, 160)   # grey
            text_color = (160, 160, 160)
            cap_color = (160, 160, 160)
        else:
            # active
            circle_color = (180, 0, 0)       # red
            text_color = (0, 0, 0)
            cap_color = (0, 0, 0)
        x, y = world_to_screen(task["x"], task["y"], self.area, self.W, self.H)
        r = int(self.service_radius * self.W / (self.area[1]-self.area[0]))
        pygame.draw.circle(self.screen, circle_color, (x,y), r*2, 2)
        # draw task id text
        text = self.font.render(str(task["id"]), True, text_color)
        rect = text.get_rect(center=(x, y))
        self.screen.blit(text, rect)
        # draw capability label (if any)
        if task.get("cap") is not None:
            cap_text = self.font.render(str(task["cap"]), False, cap_color)
            cap_rect = cap_text.get_rect(center=(x, y - r*2 - 10))
            self.screen.blit(cap_text, cap_rect)

    # Agent
    def draw_agent(self, agent, vx, vy, is_leader=False):
        if not agent["alive"]:
            x, y = world_to_screen(agent["x"], agent["y"], self.area, self.W, self.H)
            rect = self.skull_img.get_rect(center=(x, y))
            self.screen.blit(self.skull_img, rect)
            return
        x, y = world_to_screen(agent["x"], agent["y"], self.area, self.W, self.H)
        agent_color = self.agent_colors[agent["id"] % len(self.agent_colors)]
        trail_color = self.trail_colors[agent["id"] % len(self.trail_colors)]

        # trail:
        self.trails.setdefault(agent["id"], []).append((x,y))
        if len(self.trails[agent["id"]]) > 1:       #Draws the agent’s movement trail as connected line segments
            pygame.draw.lines(self.screen, trail_color, False, self.trails[agent["id"]], 2)      #pygame.draw.lines(surface, color, closed, point_list, width)

        # Arrow:
        k=1.5
        eps = 1e-6
        if abs(vx) > eps or abs(vy) > eps:
            angle = math.atan2(-vy, vx)
            self.last_angle[agent["id"]] = angle
        else:
            angle = self.last_angle.get(agent["id"], 0.0)
        L_body = 12 * k     # rectangle length      
        # Direction vectors
        dx = math.cos(angle)
        dy = math.sin(angle)
        px = -dy   # perpendicular
        py = dx
        # Triangle (head):
        S = 18 * k                        # side length (increase to make bigger)
        H = S * math.sqrt(3) / 2       # height of equilateral triangle
        base_x = x + dx * (L_body / 2)  ## base center at front of body
        base_y = y + dy * (L_body / 2)
        tip = (base_x + dx * H, base_y + dy * H)    ## triangle points
        p1  = (base_x + px * (S/2), base_y + py * (S/2))
        p2  = (base_x - px * (S/2), base_y - py * (S/2))
        pygame.draw.polygon(self.screen, agent_color, [tip, p1, p2])
        
        # id display
        # centroid of triangle
        cx = (tip[0] + p1[0] + p2[0]) / 3
        cy = (tip[1] + p1[1] + p2[1]) / 3
        text = self.font.render(str(agent["id"]), True, (255,255,255))
        rect = text.get_rect(center=(cx,cy))
        self.screen.blit(text, rect)

        # leader
        if is_leader and self.leaders_required >= 1:
            rect = self.crown_img.get_rect(center=(x, y-20))
            self.screen.blit(self.crown_img, rect)

    # Renders one animation frame
    def render(self, agents, tasks, desired, time_t, leader_id = None):
        self.screen.fill((20,60,160))
        self.screen.blit(self.bg, (0, 0))
        for task in tasks:
            self.draw_task(task, time_t)
        for i,a in enumerate(agents):
            vx, vy = desired[i]
            self.draw_agent(a, vx, vy, a["id"] == leader_id)
        if self.paused:
            txt = self.font2.render("PAUSED", True, (0, 0, 0))
            rect = txt.get_rect(center=(self.W // 2, 100))
            self.screen.blit(txt, rect)
        pygame.display.flip()       #Makes the drawn frame visible.
        self.clock.tick(30)


def run(scn, agent_cls, log_path, trace_path=None):
    random.seed(scn["seed"])
    dt = scn.get("dt", 1.0)
    T = scn["sim_time"]
    speed = scn["agent_speed"]
    service_radius = scn.get("service_radius", 10.0)
    kbps = scn["comm"]["kbps"]
    loss = scn["comm"]["loss"]
    byte_budget_per_s = kbps * 125.0  # 1 kbps = 125 bytes/s

    roles_cfg = scn.get("roles", {"leaders_required": 0})
    leaders_required = int(roles_cfg.get("leaders_required", 0))
    fail_at = roles_cfg.get("fail_at", None)
    fail_mode = roles_cfg.get("fail_mode", "remove")

    # Agents initial positions on a ring
    agents = []
    ax0 = (scn["area"][0]+scn["area"][1])/2
    ay0 = (scn["area"][2]+scn["area"][3])/2
    r = 0.35 * min(scn["area"][1]-scn["area"][0], scn["area"][3]-scn["area"][2])

    for i in range(scn["num_agents"]):
        ang = (2*math.pi*i)/scn["num_agents"]
        x = ax0 + r*math.cos(ang)
        y = ay0 + r*math.sin(ang)
        agents.append({"id": i, "x": x, "y": y, "battery": 1.0, "bytes_used": 0.0, "dist": 0.0, "alive": True})

    # Capabilities (optional)
    agent_caps = scn.get("agent_caps", None)
    # Claimed ownership per task_id (from messages)
    claim_owner = {}
    claim_version = 0
    last_claim_version = 0

    # Tasks
    tasks = deepcopy(scn["tasks"])
    for t in tasks:
        t["remaining"] = t["service"]
        t["done"] = False
        t["started_at"] = None
        t["completed_at"] = None
        # t["cap"] may be None or a string like "thermal","lift1","sea3"
        t["cap"] = t.get("cap", None)

    # Instantiate team agents
    Agent = agent_cls
    agent_objs = [Agent(i, scn["area"], speed, scn["seed"]+i) for i in range(scn["num_agents"])]

    inbox = [[] for _ in range(scn["num_agents"])]
    convergence_tick = None
    last_change_tick = 0  # when the task set last changed (appear/disappear/done)

    # Leader tracking via role messages: {"type":"role","role":"leader","term": int}
    current_leader = None
    current_term = -1
    failed_agent = None
    leader_elected_after_fail = None

    # For convergence: ownership proxy
    assignment_hist = []
    def visible_tasks(time_t):
        return [task for task in tasks if (task["t0"]<=time_t and not task["done"] and time_t<=task["deadline"])]

    def current_assignment(time_t):
        mapping = {}
        for task in visible_tasks(time_t):
            tid = task["id"]
            owner = claim_owner.get(tid, None)
            if owner is not None and 0 <= owner < len(agents) and agents[owner]["alive"]:
                mapping[tid] = owner
        return mapping

    time_t = 0.0
    tick = 0
    bytes_sent_this_second = [0.0 for _ in agents]

    # For logs
    total_bytes = 0.0
    total_dist = 0.0
    trace = [] if trace_path else None

    '''For pygame Visualization'''
    viz = PygameVisualizer(scn)

    while time_t < T:
        '''For pygame Visualization'''
        viz.handle_events()
        if not viz.running:
            break
        if viz.paused:
            viz.render(agents, tasks, desired, time_t, current_leader)
            viz.clock.tick(30)
            continue

        # Check failure injection
        if fail_at is not None and failed_agent is None and time_t >= fail_at:
            # by default, fail current leader if known, else agent 0
            candidate = current_leader if current_leader is not None else 0
            failed_agent = candidate
            if 0 <= failed_agent < len(agents):
                agents[failed_agent]["alive"] = False

        # Visible tasks
        visible = [ {k:task[k] for k in ("id","x","y","t0","deadline","service","value","remaining","cap")}
                    for task in visible_tasks(time_t) ]

        # Agents decide
        outboxes = [[] for _ in agents]
        desired = []
        for i,a in enumerate(agents):
            if not a["alive"]:
                desired.append((0.0,0.0))
                outboxes[i] = []
                continue
            state = {"x": a["x"], "y": a["y"], "battery": a["battery"], "speed": speed}
            act, out = agent_objs[i].step(time_t, dt, state, visible, inbox[i])
            if not isinstance(out, list): out = []
            outboxes[i] = out
            vx = float(act.get("vx", 0.0)); vy = float(act.get("vy", 0.0))
            vnorm = math.hypot(vx, vy)
            if vnorm > speed and vnorm>0:
                scale = speed / vnorm
                vx *= scale; vy *= scale
            desired.append((vx, vy))

        # Radio: broadcast with loss + per-second cap
        delivered = [[] for _ in agents]
        for i, msgs in enumerate(outboxes):
            if not agents[i]["alive"]:
                continue
            for m in msgs:
                sz = json_size_bytes(m)
                if bytes_sent_this_second[i] + sz > byte_budget_per_s:
                    continue
                bytes_sent_this_second[i] += sz
                if random.random() < loss:
                    continue
                for j in range(len(agents)):
                    if agents[j]["alive"]:
                        delivered[j].append({"from": i, "msg": m})
                agents[i]["bytes_used"] += sz
                total_bytes += sz
                # Track claimed ownership if provided
                if isinstance(m, dict) and m.get("type")=="claim":
                    tid = m.get("task_id", None)
                    # print("claim_owner is = ", claim_owner)
                    # print(f"agent = {i} claimed ownership of task {tid}")
                    if tid is not None:
                        tid = int(tid)
                        new_owner = int(m.get("agent", i))
                        prev_owner = claim_owner.get(tid, None)
                        if prev_owner != new_owner:
                            claim_owner[tid] = new_owner
                            claim_version += 1
                            # print("claim_version =", claim_version)
                            # print("claim_owner is = ", claim_owner)
                # Leader tracking
                if isinstance(m, dict) and m.get("type")=="role" and m.get("role")=="leader":
                    term = int(m.get("term", 0))
                    agent_id = int(m.get("agent", i))
                    # accept higher term or first leader if none
                    if term > current_term or current_leader is None:
                        # if we are after a failure and new leader different, record election time if not set
                        if failed_agent is not None and agent_id != failed_agent and leader_elected_after_fail is None:
                            leader_elected_after_fail = time_t - fail_at
                        current_term = term
                        current_leader = agent_id

        # Move
        for i,a in enumerate(agents):
            if not a["alive"]:
                continue
            oldx, oldy = a["x"], a["y"]
            a["x"] = clamp(a["x"] + desired[i][0]*dt, scn["area"][0], scn["area"][1])
            a["y"] = clamp(a["y"] + desired[i][1]*dt, scn["area"][2], scn["area"][3])
            d = math.hypot(a["x"]-oldx, a["y"]-oldy)
            a["dist"] += d
            total_dist += d

        '''For pygame Visualization'''
        viz.render(agents, tasks, desired, time_t, current_leader)

        # Service tasks (capability-aware)
        for task in tasks:
            if task["done"] or not (task["t0"]<=time_t<=task["deadline"]):
                continue
            in_count = 0
            for idx,a in enumerate(agents):
                if not a["alive"]:
                    continue
                if dist((a["x"],a["y"]), (task["x"],task["y"])) <= service_radius:
                    # capability check
                    if task["cap"] is None:
                        ok = True
                    else:
                        if agent_caps is None: 
                            ok = False
                        else:
                            ok = task["cap"] in agent_caps[idx]
                    if ok:
                        in_count += 1
            if in_count>0:
                if task["started_at"] is None: task["started_at"] = time_t
                task["remaining"] = max(0.0, task["remaining"] - dt)
                if task["remaining"] <= 0.0:
                    task["done"] = True
                    task["completed_at"] = time_t

        # Convergence check (relative to last task-set/claim change)
        current_visible_ids = {t["id"] for t in visible_tasks(time_t)}
        # reset window on visible task-set changes
        if len(assignment_hist)==0:
            assignment_hist.append(current_assignment(time_t))
        else:
            prev_visible_ids = {t["id"] for t in visible_tasks(time_t-dt)}
            if current_visible_ids != prev_visible_ids:
                assignment_hist = []
                last_change_tick = tick
            assignment_hist.append(current_assignment(time_t))

        # reset window on claim ownership changes
        if claim_version != last_claim_version:
            assignment_hist = [current_assignment(time_t)]
            last_change_tick = tick
            last_claim_version = claim_version

        window = int(60.0/dt)
        if len(assignment_hist) >= window and convergence_tick is None:
            stable = 0; total = 0
            last_map = assignment_hist[-1]
            # print("last_map is = ", last_map)
            for tid in last_map.keys():
                total += 1
                same = all((tid in m and m[tid]==last_map[tid]) for m in assignment_hist[-window:])
                if same: stable += 1
            # print("total is = ", total)
            if total>0 and stable/total>=0.95:
                convergence_tick = tick - last_change_tick  # ticks since last change

        if trace is not None:
            trace.append({
                "t": round(time_t, 3),
                "leader": {"id": current_leader, "term": current_term},
                "agents": [
                    {
                        "id": a["id"],
                        "alive": a["alive"],
                        "x": round(a["x"], 3),
                        "y": round(a["y"], 3),
                        "bytes": int(a["bytes_used"]),
                        "dist": round(a["dist"], 3)
                    } for a in agents
                ],
                "tasks": [
                    {
                        "id": task["id"],
                        "remaining": round(task["remaining"], 3),
                        "done": task["done"]
                    } for task in tasks
                ],
                "inbox_counts": [len(box) for box in inbox]
            })

        # step
        tick += 1
        time_t += dt
        if int(time_t) != int(time_t-dt):
            bytes_sent_this_second = [0.0 for _ in agents]
        inbox = delivered

    # Score
    total_value = sum(t["value"] for t in tasks)
    value_done = sum(t["value"] for t in tasks if t["done"])
    value_ratio = 0.0 if total_value==0 else value_done/total_value

    norm_distance = total_dist / (len(agents)*speed*T + 1e-9)
    norm_bytes = total_bytes / (len(agents)* (kbps*125.0) * T + 1e-9)

    score = 0.6*value_ratio - 0.2*norm_distance - 0.2*norm_bytes

    # Convergence
    conv_sec = None if convergence_tick is None else convergence_tick * dt
    penalty = 0.0
    if conv_sec is None or conv_sec>60.0:
        penalty += 0.05
        # print("conv_sec =", conv_sec)

    # Leader election gate if required
    leader_election_s = leader_elected_after_fail
    if leaders_required>0 and fail_at is not None:
        if leader_election_s is None or leader_election_s>10.0:
            penalty += 0.05

    score -= penalty

    # Capability stats
    cap_tasks_total = sum(1 for t in tasks if t.get("cap") is not None)
    cap_tasks_done = sum(1 for t in tasks if t.get("cap") is not None and t["done"])

    summary = {
        "scenario": scn["name"],
        "value_ratio": round(value_ratio,4),
        "norm_distance": round(norm_distance,4),
        "norm_bytes": round(norm_bytes,4),
        "score": round(score,4),
        "convergence_s": None if conv_sec is None else round(conv_sec,2),
        "leader_election_s": None if leader_election_s is None else round(leader_election_s,2),
        "penalty": round(penalty,3),
        "cap_tasks_done": cap_tasks_done,
        "cap_tasks_total": cap_tasks_total,
        "total_dist_m": round(total_dist,2),
        "total_bytes": int(total_bytes)
    }

    if log_path:
        with open(log_path,"w") as f: json.dump({"summary": summary}, f, separators=(",",":"))
    if trace_path and trace is not None:
        with open(trace_path,"w") as f: json.dump({"trace": trace}, f, separators=(",",":"))
    print(json.dumps(summary, indent=2))
    
    '''For pygame Visualization'''
    pygame.event.clear()
    pygame.display.quit()
    pygame.quit()
    
    return summary

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--team", required=True)
    ap.add_argument("--log", default=None, help="Write summary JSON to this path")
    ap.add_argument("--trace", default=None, help="Write per-tick trace JSON for debugging/plots")
    args = ap.parse_args()
    with open(args.scenario,"r") as f:
        scn = json.load(f)
    Agent = load_team(args.team)
    run(scn, Agent, args.log, trace_path=args.trace)

if __name__=="__main__":
    main()
