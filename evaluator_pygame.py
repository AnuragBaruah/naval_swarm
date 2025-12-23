import argparse, importlib.util, json, math, os, random
from copy import deepcopy
import pygame


#- - - - - - - - - - - - - - - - - - - - - PART 1: INITIALIZATION PHASE - - - - - - - - - - - - - - - - - - - - - - - - - - -#
#Loading Agent
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
        self.screen = pygame.display.set_mode((0,0), pygame.FULLSCREEN)
        self.W, self.H = self.screen.get_size()
        pygame.display.set_caption("Swarm Simulation")
        self.area = scn["area"]
        self.service_radius = scn.get("service_radius", 10.0)
        self.clock = pygame.time.Clock()
        self.paused = False
        self.running = True
        self.font = pygame.font.SysFont(None, 20)
        self.colors = [
            (255, 233, 0),   # Electric Yellow
            (57, 255, 20),   # Neon Lime
            (255, 145, 0),   # Safety Orange
            (255, 0, 144),   # Bright Magenta
            (0, 255, 255),   # Cyan
            (105, 240, 174), # Mint Green
            (224, 64, 251),  # Electric Lavender
            (255, 82, 82),   # Coral Red
            (255, 215, 0),   # Goldenrod
            (224, 224, 224)  # Platinum
        ]        
        self.trails = {}  # agent_id → list[(x,y)]

    # Handles close window, pause simulation
    def handle_events(self):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                self.running = False
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                self.running = False

    # axis
    def draw_axes(self):
        # world origin
        x0, y0 = world_to_screen(0, 0, self.area, self.W, self.H)
        # X axis (horizontal)
        pygame.draw.line(
            self.screen,
            (0, 0, 0),
            (0, y0),
            (self.W, y0),
            2
        )
        # Y axis (vertical)
        pygame.draw.line(
            self.screen,
            (0, 0, 0),
            (x0, 0),
            (x0, self.H),
            2
        )

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
            color = (160, 160, 160)   # grey
        else:
            # active
            color = (180, 0, 0)       # red
        x, y = world_to_screen(task["x"], task["y"], self.area, self.W, self.H)
        r = int(self.service_radius * self.W / (self.area[1]-self.area[0]))
        pygame.draw.circle(self.screen, color, (x,y), r, 2)
        # draw task id text
        text = self.font.render(str(task["id"]), True, (255,255,255))
        rect = text.get_rect(center=(x, y))
        self.screen.blit(text, rect)

    # Agent
    def draw_agent(self, agent, vx, vy):
        if not agent["alive"]:
            return
        x, y = world_to_screen(agent["x"], agent["y"], self.area, self.W, self.H)
        color = self.colors[agent["id"] % len(self.colors)]

        # trail:
        self.trails.setdefault(agent["id"], []).append((x,y))
        if len(self.trails[agent["id"]]) > 1:       #Draws the agent’s movement trail as connected line segments
            pygame.draw.lines(self.screen, color, False, self.trails[agent["id"]], 2)      #pygame.draw.lines(surface, color, closed, point_list, width)

        # Arrow:
        angle = math.atan2(-vy, vx)
        L_body = 12      # rectangle length
        W_body = 3       # rectangle width
        # Direction vectors
        dx = math.cos(angle)
        dy = math.sin(angle)
        px = -dy   # perpendicular
        py = dx
        # Rectangle (shaft):
        body_front = (x + dx * (L_body/2), y + dy * (L_body/2))
        body_back  = (x - dx * (L_body/2), y - dy * (L_body/2))
        r1 = (body_back[0] + px*(W_body/2), body_back[1] + py*(W_body/2))
        r2 = (body_back[0] - px*(W_body/2), body_back[1] - py*(W_body/2))
        r3 = (body_front[0] - px*(W_body/2), body_front[1] - py*(W_body/2))
        r4 = (body_front[0] + px*(W_body/2), body_front[1] + py*(W_body/2))
        pygame.draw.polygon(self.screen, color, [r1, r2, r3, r4])
        # Triangle (head):
        S = 18                         # side length (increase to make bigger)
        H = S * math.sqrt(3) / 2       # height of equilateral triangle
        base_x = x + dx * (L_body / 2)  ## base center at front of body
        base_y = y + dy * (L_body / 2)
        tip = (base_x + dx * H, base_y + dy * H)    ## triangle points
        p1  = (base_x + px * (S/2), base_y + py * (S/2))
        p2  = (base_x - px * (S/2), base_y - py * (S/2))
        pygame.draw.polygon(self.screen, color, [tip, p1, p2])
        # id display
        # centroid of triangle
        cx = (tip[0] + p1[0] + p2[0]) / 3
        cy = (tip[1] + p1[1] + p2[1]) / 3
        text = self.font.render(str(agent["id"]), True, (0,0,0))
        rect = text.get_rect(center=(cx,cy))
        self.screen.blit(text, rect)

    # Renders one animation frame
    def render(self, agents, tasks, desired, time_t):
        self.screen.fill((20,60,160))
        self.draw_axes()
        for task in tasks:
            self.draw_task(task, time_t)
        for i,a in enumerate(agents):
            vx, vy = desired[i]
            self.draw_agent(a, vx, vy)
        pygame.display.flip()       #Makes the drawn frame visible.
        self.clock.tick(30)


#Loading Scenario Configuration
def run(scn, agent_cls, log_path, trace_path=None):

    ## Setting some variables for values from scn (scenario) files - - - - - - - - - - - - - - - - - - - -
    random.seed(scn["seed"])    
    dt = scn.get("dt", 1.0)     #Time step: 1 sec default
    T = scn["sim_time"]         #Total time (in sec)
    speed = scn["agent_speed"]  #Max movement speed (in m/sec)
    service_radius = scn.get("service_radius", 10.0)   #Task service distance 
    kbps = scn["comm"]["kbps"]  #Bandwidth (in Kb/sec)
    loss = scn["comm"]["loss"]  #Packet loss (0.1 = 10%)
    byte_budget_per_s = kbps * 125.0  # 1 kbps = 125 bytes/s

    #for S6 and S7 
    roles_cfg = scn.get("roles", {"leaders_required": 0})
    leaders_required = int(roles_cfg.get("leaders_required", 0))
    fail_at = roles_cfg.get("fail_at", None)
    fail_mode = roles_cfg.get("fail_mode", "remove")


    ## Agents initial positions on a ring - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
    #The simulation area is a rectangle. Agents do not start randomly. They start evenly spaced on a circle inside the area.
    agents = []     #Create an empty list to store all agents
    ax0 = (scn["area"][0]+scn["area"][1])/2     #Center point x of the map
    ay0 = (scn["area"][2]+scn["area"][3])/2     #Center point y of the map
    r = 0.35 * min(scn["area"][1]-scn["area"][0], scn["area"][3]-scn["area"][2])    #r=0.35*min(width, height)

    #This loop creates each agent, places it evenly on a circle, and initializes its state
    for i in range(scn["num_agents"]):  #i is the agent id
        ang = (2*math.pi*i)/scn["num_agents"]   #Compute the angle of this agent on the circle
        x = ax0 + r*math.cos(ang)       #Compute the agent’s horizontal position
        y = ay0 + r*math.sin(ang)       #Compute the agent’s vertical position
        agents.append({"id": i, "x": x, "y": y, "battery": 1.0, "bytes_used": 0.0, "dist": 0.0, "alive": True})


    ## for S7 - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    #Capabilities (optional)
    agent_caps = scn.get("agent_caps", None)

    #Tasks
    tasks = deepcopy(scn["tasks"])
    for t in tasks:
        t["remaining"] = t["service"]
        t["done"] = False
        t["started_at"] = None
        t["completed_at"] = None
        # t["cap"] may be None or a string like "thermal","lift1","sea3"
        t["cap"] = t.get("cap", None)


    ## Creates the actual agent objects and supporting DS needed to run the simulation - - - - - - - - - - - - - - - - - - - -
    Agent = agent_cls       #Rename the agent class for convenience.
    agent_objs = [Agent(i, scn["area"], speed, scn["seed"]+i) for i in range(scn["num_agents"])]    #Create one agent object per agent

    inbox = [[] for _ in range(scn["num_agents"])]  #msgs for each agent
    convergence_tick = None         #when convergence occurs

    #For S6:
    #Leader tracking via role messages: {"type":"role","role":"leader","term": int}
    current_leader = None
    current_term = -1
    failed_agent = None     #failure tracking
    leader_elected_after_fail = None


    ## For convergence: ownership proxy - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    #This code estimates which agent is handling each active task by choosing the nearest alive agent, so the simulator can detect convergence
    assignment_hist = []        #Each entry is a snapshot of “which agent seems closest to which task” at that moment
    
    #Given the current time, estimate who is responsible for each task
    def current_assignment(time_t):
        mapping = {}
        for task in tasks:      #Look at every task in the scenario
            if task["done"] or task["t0"]>time_t or time_t>task["deadline"]:
                continue
            #For this task, compute distance from every alive agent
            dists = [(j, dist((agents[j]["x"],agents[j]["y"]), (task["x"],task["y"]))) for j in range(len(agents)) if agents[j]["alive"]]
            if not dists:       #If no agents are alive, skip this task
                continue
            jmin = min(dists, key=lambda x:x[1])[0]     #Find the agent closest to this task
            mapping[task["id"]] = jmin
        return mapping


    #- - - - - - - - - - - - - - - - - - PART 2: THE MAIN SIMULATION LOOP - - - - - - - - - - - - - - - - - - -#
    time_t = 0.0    #simulation time
    tick = 0        #To Count how many simulation steps have occurred
    bytes_sent_this_second = [0.0 for _ in agents]      #Tracks how many bytes each agent has sent in this second

    # For logs
    total_bytes = 0.0       #Start counting how much data all agents send in total
    total_dist = 0.0        #Start counting how far all agents move
    trace = [] if trace_path else None      #Decide whether to record detailed step-by-step logs

    '''For pygame Visualization'''
    viz = PygameVisualizer(scn)

    ## The main simulation loop:
    while time_t < T:
        '''For pygame Visualization'''
        viz.handle_events()
        if not viz.running:
            break
        if viz.paused:
            viz.clock.tick(30)
            continue

        #1. Check failure injection - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        if fail_at is not None and failed_agent is None and time_t >= fail_at:      #Trigger failure once, at or after the specified time
            candidate = current_leader if current_leader is not None else 0         #by default, fail current leader if known, else agent 0
            failed_agent = candidate        #record which agent has failed
            if 0 <= failed_agent < len(agents):
                agents[failed_agent]["alive"] = False       #mark that agent as dead


        #2. Filter Visible tasks - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        #visible is a list of active tasks and exposes only the information agents are allowed to see
        visible = [ {k:task[k] for k in ("id","x","y","t0","deadline","service","value","remaining","cap")}
                    for task in tasks if (task["t0"]<=time_t and not task["done"] and time_t<=task["deadline"]) ]


        #3. Agents decide - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        #Each alive agent is asked: “What do you want to do now?”
        #The agent replies with: A movement direction, Messages to broadcast

        outboxes = [[] for _ in agents]     #This is where messages agents want to send are stored
        desired = []        #Prepare a list to store each agent’s desired movement
        
        for i,a in enumerate(agents):       #i is agent's id, a is agent's current state
            #skip thinking for dead agents
            if not a["alive"]:
                desired.append((0.0,0.0))
                outboxes[i] = []
                continue
            #give the agent class, the state of the agent
            state = {"x": a["x"], "y": a["y"], "battery": a["battery"], "speed": speed}
            act, out = agent_objs[i].step(time_t, dt, state, visible, inbox[i])
            #Ensure messages are valid and save them
            if not isinstance(out, list): out = []
            outboxes[i] = out
            #4. Velocity clamping
            vx = float(act.get("vx", 0.0)); vy = float(act.get("vy", 0.0))
            vnorm = math.hypot(vx, vy)
            if vnorm > speed and vnorm>0:
                scale = speed / vnorm
                vx *= scale; vy *= scale
            desired.append((vx, vy))

        
        #5. Radio: broadcast with loss + per-second cap - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        delivered = [[] for _ in agents]
        for i, msgs in enumerate(outboxes):     #For each agent, look at the messages it wants to send
            if not agents[i]["alive"]:          #Dead agents cannot send messages
                continue
            for m in msgs:      #Process each message separately
                sz = json_size_bytes(m)     #Calculate how big the message is in bytes
                if bytes_sent_this_second[i] + sz > byte_budget_per_s:      #If sending this message would exceed the agent’s bandwidth for this second, drop it
                    continue
                bytes_sent_this_second[i] += sz     #Count this message toward the agent’s bandwidth usage
                if random.random() < loss:          #Randomly drop messages
                    continue
                #if msg survives, send it to all alive agents. include sender id. this is broadcast, not point to point.
                for j in range(len(agents)):        
                    if agents[j]["alive"]:
                        delivered[j].append({"from": i, "msg": m})
                #updating global variables
                agents[i]["bytes_used"] += sz
                total_bytes += sz

                #6. Leader tracking (S6 only) - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
                if isinstance(m, dict) and m.get("type")=="role" and m.get("role")=="leader":       #Check if this message is a leader announcement
                    term = int(m.get("term", 0))        #Read the election term number
                    agent_id = int(m.get("agent", i))   #Read the agent id
                    # accept higher term or first leader if none
                    if term > current_term or current_leader is None:
                        # if we are after a failure and new leader different, record election time if not set
                        if failed_agent is not None and agent_id != failed_agent and leader_elected_after_fail is None:
                            leader_elected_after_fail = time_t - fail_at
                        current_term = term
                        current_leader = agent_id


        #7. This block actually moves the agents in the world and measures how far they travel - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        for i,a in enumerate(agents):
            if not a["alive"]:
                continue
            oldx, oldy = a["x"], a["y"]
            a["x"] = clamp(a["x"] + desired[i][0]*dt, scn["area"][0], scn["area"][1])
            a["y"] = clamp(a["y"] + desired[i][1]*dt, scn["area"][2], scn["area"][3])
            d = math.hypot(a["x"]-oldx, a["y"]-oldy)
            a["dist"] += d      #Track distance per agent       
            total_dist += d     #Track distance across all agents

        '''For pygame Visualization'''
        viz.render(agents, tasks, desired, time_t)


        #8. Service tasks (capability-aware) - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        #This block handles task execution. It decides when tasks get worked on, by whom, and when they finish.
        for task in tasks:
            if task["done"] or not (task["t0"]<=time_t<=task["deadline"]):      #Skip inactive tasks
                continue
            in_count = 0        #Start counting how many agents can work on this task
            #Check each agent
            for idx,a in enumerate(agents):
                if not a["alive"]:
                    continue
                if dist((a["x"],a["y"]), (task["x"],task["y"])) <= service_radius:      #Agent must be close enough to the task
                    # capability check (S7 only):
                    if task["cap"] is None:
                        ok = True
                    else:
                        if agent_caps is None: 
                            ok = False
                        else:
                            ok = task["cap"] in agent_caps[idx]
                    if ok:
                        in_count += 1
            #If at least one agent works, Task receives service this time step
            if in_count>0:
                if task["started_at"] is None: task["started_at"] = time_t      #Record when the task was first worked on
                task["remaining"] = max(0.0, task["remaining"] - dt)            #Reduce remaining service time
                if task["remaining"] <= 0.0:        #Task is completed
                    task["done"] = True
                    task["completed_at"] = time_t


        #9. Convergence check - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        #Have agents stopped changing which agent is effectively handling each task?
        assignment_hist.append(current_assignment(time_t))
        window = int(60.0/dt)
        if len(assignment_hist) >= window and convergence_tick is None:
            stable = 0; total = 0
            last_map = assignment_hist[-1]
            for tid in last_map.keys():
                total += 1
                same = all((tid in m and m[tid]==last_map[tid]) for m in assignment_hist[-window:])
                if same: stable += 1
            if total>0 and stable/total>=0.95:
                convergence_tick = tick


        #10. Record Trace - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
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


        #11. step - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        tick += 1
        time_t += dt
        if int(time_t) != int(time_t-dt):
            bytes_sent_this_second = [0.0 for _ in agents]
        inbox = delivered


    #- - - - - - PART 3: SCORING PHASE - - - - - -#
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