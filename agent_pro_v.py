import math, random

def dist(ax, ay, bx, by):
    return ((ax-bx)**2 + (ay-by)**2) ** 0.5

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
            cost += all_tasks[q]["remaining"] * self.max_speed
            x, y = all_tasks[q]["x"], all_tasks[q]["y"]
        
        cost += dist(x, y, all_tasks[taskid]["x"], all_tasks[taskid]["y"])
        return cost
    
    def step(self, t, dt, self_state, tasks_visible, inbox):
        pass