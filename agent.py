import math, random

def dist(ax, ay, bx, by):
    return ((ax-bx)**2 + (ay-by)**2) ** 0.5

class template_Agent:
    def __init__(self, agent_id, world_bounds, speed, seed):
        self.id = agent_id
        self.bounds = world_bounds
        self.speed = speed
        random.seed(seed)
        self.target = None
        self.last_broadcast = -999

    def step(self, t, dt, self_state, tasks_visible, inbox):
        # Listen to broadcasts to avoid duplicate selection.
        claimed = set()

        print("*********")
        print("time\n", t)
        print("*********")
        print("tasks_visible\n", tasks_visible)
        print("*********")
        print("inbox\n", inbox)
        print("*********")
        print("self_state\n", self_state)
        print("*********")
        
        for m in inbox:
            msg = m["msg"]
            if isinstance(msg, dict) and msg.get("type")=="claim":
                claimed.add(msg["task_id"])

        # pick nearest task that's not claimed
        if (self.target is None) or (self.target not in [ti["id"] for ti in tasks_visible]) or (self.target in claimed):
            best = None; best_d = 1e9
            for ti in tasks_visible:
                if ti["id"] in claimed: 
                    continue
                d = dist(self_state["x"], self_state["y"], ti["x"], ti["y"])
                if d < best_d:
                    best_d = d; best = ti["id"]
            self.target = best

        outbox = []
        if self.target is not None and (t - self.last_broadcast >= 5.0):
            outbox.append({"type":"claim","agent":self.id,"task_id": self.target})
            self.last_broadcast = t

        vx = vy = 0.0
        if self.target is not None:
            for ti in tasks_visible:
                if ti["id"]==self.target:
                    dx = ti["x"] - self_state["x"]
                    dy = ti["y"] - self_state["y"]
                    L = (dx*dx + dy*dy) ** 0.5 + 1e-9
                    vx = (dx / L) * self.speed
                    vy = (dy / L) * self.speed
                    break

        return {"vx": vx, "vy": vy}, outbox

class Agent:
    def __init__(self, agent_id, world_bounds, speed, seed):
        # fixed seed initialisation for predictable randomness (in case ever use randomness)
        random.seed(seed)

        # initialisation (compulsory)
        self.id = agent_id
        self.world_bounds = world_bounds
        self.max_speed = speed

        # initialisation (general)
        self.claim = None
        self.queue = []
        self.already_claimed = []
        self.cost_of_claim = math.inf

        # command switches
        self.reclaim = False
        self.exchange = False
        self.m1 = True
        self.current_leader = 0
        self.leader_not_observed = 0

    def compute_cost(self, all_tasks, taskid):
        cost = 0
        x, y = self.x, self.y
        for q in self.queue:
            cost += dist(x, y, all_tasks[q]["x"], all_tasks[q]["y"])
            cost += all_tasks[q]["remaining"]
            x, y = all_tasks[q]["x"], all_tasks[q]["y"]
        
        cost += dist(x, y, all_tasks[taskid]["x"], all_tasks[taskid]["y"])
        
        return cost

    def step(self, t, dt, self_state, tasks_visible, inbox):
        # get self coordinates
        self.x, self.y = self_state["x"], self_state["y"]

        # get tasks_visible : [{'id': 1, 'x': 1146.0738385082163, 'y': 450.55809196144605, 't0': 2, 'deadline': 5, 'service': 2, 'value': 10, 'remaining': 2, 'cap': None}]
        active_tasks_ids = [task["id"] for task in tasks_visible] 
        all_tasks = dict(zip(active_tasks_ids, tasks_visible))     # getting a "id to task" mapping for ease of access
        
        # read message : {'claim' : task_id, 'cost' : cost}
        # inbox : [{'from': 0, 'msg': {...}}, {'from': 1, 'msg': {...}}]
        sender_list = []
        _min_cost = math.inf
        _winner_agent_id = -1
        _leader_detected = False
        
        # INBOX LOOP    
        _re = 0
        for M in inbox:
            agent_id = M["from"]
            sender_list.append(agent_id)
            msg = M["msg"]

            # leader handling
            if "role" in msg:
                _leader_detected = True
            
            # claims betting
            if self.claim is not None and "claim" in msg:
                agent_claim, agent_cost = msg["claim"], msg["cost"]
                if agent_claim == self.claim:
                    if agent_cost < _min_cost:
                        _min_cost = agent_cost
                        _winner_agent_id = agent_id
                    elif agent_cost == _min_cost and agent_id > _winner_agent_id:
                        _winner_agent_id = agent_id
            
            # handle reclaims to see if reclaim agent is better
            if "reclaim" in msg and self.id != agent_id:
                agent_claim, agent_cost = msg["reclaim"], msg["cost"]
                for taskid in self.queue:
                    if agent_claim == taskid and agent_cost < self.compute_cost(all_tasks, agent_claim):
                        _re += 1
                        # when reclaim is winning; agent must give a "forfeit and take" command
                        self.entering_agent = agent_id
                        self.exchange_task = agent_claim
                        self.exchange = True

            # exchange reclaims
            if "xclaim" in msg:
                if self.id == agent_id:
                    self.queue.remove(msg["xclaim"])
                    self.exchange = False
                elif msg["enter"] == self.id:
                    self.queue.append(msg["xclaim"])
                    self.reclaim = False

            # already claimed list
            if "claim" in msg and msg["claim"] not in self.already_claimed:
                self.already_claimed.append(msg["claim"])

        if _re == 0: self.exchange = False

        # leader handling
        if not _leader_detected:
            self.leader_not_observed += 1
            if self.leader_not_observed == 8:
                self.current_leader += 1
                self.leader_not_observed = 0
        else:
            self.leader_not_observed = 0



        # update queue
        # agent wins claims betting
        if _winner_agent_id == self.id:
            self.queue.append(self.claim)
            self.reclaim = False
        
        # agent's original message did not get broadcasted but agent could win
        elif self.claim is not None and self.id not in sender_list and self.cost_of_claim < _min_cost:
            self.reclaim = True

        # agent lost claims betting
        else:
            self.claim = None                
        
        # remove from queue if the task is no longer visible (either done or deadline crossed)
        self.queue[:] = [taskid for taskid in self.queue if taskid in active_tasks_ids]


        # get available tasks
        self.already_claimed[:] = [taskid for taskid in self.already_claimed if taskid in active_tasks_ids]
        available_tasks_ids = [
            taskid for taskid in active_tasks_ids if taskid not in self.already_claimed
        ]

        if self.reclaim and self.claim in available_tasks_ids:
            self.queue.append(self.claim)
            self.reclaim = False
            self.already_claimed.append(self.claim)
            self.claim = None
        
        # update claim
        claim = None
        cost_of_claim = math.inf
        for taskid in available_tasks_ids:
            cost = self.compute_cost(all_tasks, taskid)
            if cost < cost_of_claim:
                claim = taskid
                cost_of_claim = cost
        
        # accept this claim if NO reclaim requirement is there
        if not (self.reclaim and self.cost_of_claim < cost_of_claim):
            self.claim = claim
            self.cost_of_claim = cost_of_claim
            
        
        # compute velocity
        vx = vy = 0
        for taskid in self.queue:
            target_x, target_y = all_tasks[taskid]["x"], all_tasks[taskid]["y"]
            delta_x, delta_y = target_x - self.x, target_y - self.y
            distance = math.sqrt(delta_x * delta_x + delta_y * delta_y)
            eps = max(self.max_speed * dt, 1e-6)
            if distance < eps:
                break
            else:
                vx = delta_x / distance * self.max_speed
                vy = delta_y / distance * self.max_speed
            # ******
            break
        
        # *********************************
        # generate message (outbox)
        msg = {}
        
        # message: claim - cost
        if self.claim is not None:
            if self.reclaim:
                msg["reclaim"], msg["cost"] = self.claim, self.cost_of_claim
            else:
                msg["claim"], msg["cost"] = self.claim, self.cost_of_claim
        
        # exchange - "forfeit and take" message
        if self.exchange:
            msg["xclaim"] = self.exchange_task
            msg["enter"] = self.entering_agent

        # leader message
        if self.m1 and self.id == self.current_leader:
            self.m1 = False
            msg["type"] = "role"
            msg["role"] = "leader"
            msg["term"] = self.current_leader
            print(f"Hello I am agent {self.id}, I am declaring myself as leader at time t = {t}")
        
        elif not self.m1 and self.id == self.current_leader:
            msg["role"] = True

        # send message only if msg is polulated
        if msg != {}:
            self.outbox = [msg]
        else:
            self.outbox = []

        # return data
        return {"vx": vx, "vy": vy}, self.outbox
