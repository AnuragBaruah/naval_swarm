import math, random

# import for debug purposes
import atexit

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
        self.max_queue_limit_for_exploration = 3

        # initialisation (general)
        self.claim = None
        self.release_task = None
        self.queue = []
        self.unavailable_tasks = []
        self.cost_of_claim = math.inf
        self.capabilities = []
        self.non_capabilities = []
        self.task_doing_counter = 0
        self.exp_done_msg_required = False

        # command switches
        self.reclaim = False
        self.exchange = False
        self.m1 = True
        self.current_leader = 0
        self.leader_not_observed = 0

        # region - DEBUG
        # DEBUG FEATURES
        self.prev_queue = self.queue.copy()
        self.prev_cap = self.capabilities.copy()
        self.prev_no_cap = self.non_capabilities.copy()
        
        # general debug mode (in case we want debug mode for all agents)
        self.debug_mode = True

        # # agent based debug mode (in case we want only debug file for particular)
        # if self.id in (<write agent ids here for which we want to get debugs>):
        #     self.debug_mode = True
        # else:
        #     self.debug_mode = False

        # debug file creation
        if self.debug_mode:
            self.debug_file = open(f"DEBUG\\agent_{self.id}.log", "w", buffering = 1)
            atexit.register(self.close_debug_file)

        # endregion

    def debug(self, timestamp):
        debug_message = ""
        if self.queue != self.prev_queue:
            debug_message += "QUEUE UPDATED "
            self.prev_queue = self.queue.copy()
        if self.capabilities != self.prev_cap:
            debug_message += "CAPS UPDATED "
            self.prev_cap = self.capabilities.copy()
        if self.non_capabilities != self.prev_no_cap:
            debug_message += "NON-CAP UPDATED "
            self.prev_no_cap = self.non_capabilities.copy()
        if debug_message != "":
            debug_message += f"\nTIMESTAMP = {timestamp}\nqueue = {self.prev_queue}\ncaps  = {self.prev_cap}\nno_cap= {self.prev_no_cap}\n*******************\n"
            self.debug_file.write(debug_message)
    
    def close_debug_file(self):
        self.debug_file.close()
    
    def compute_distance_cost(self, all_tasks, taskid):
        cost = 0
        x, y = self.x, self.y
        for q in self.queue:
            cost += dist(x, y, all_tasks[q]["x"], all_tasks[q]["y"])
            cost += all_tasks[q]["remaining"] * self.max_speed
            x, y = all_tasks[q]["x"], all_tasks[q]["y"]
        
        cost += dist(x, y, all_tasks[taskid]["x"], all_tasks[taskid]["y"])
        return cost
    
    def step(self, t, dt, self_state, tasks_visible, inbox):
        # get self coordinates
        self.x, self.y = self_state["x"], self_state["y"]

        # get tasks_visible : [{'id': 1, 'x': 1146.0738385082163, 'y': 450.55809196144605, 't0': 2, 'deadline': 5, 'service': 2, 'value': 10, 'remaining': 2, 'cap': None}]
        active_tasks_ids = [task["id"] for task in tasks_visible] 
        all_tasks_from_id = dict(zip(active_tasks_ids, tasks_visible))     # getting a "id to task" mapping for ease of access

        # region PRE - task INBOX handling
        '''Check INBOX'''
        # inbox data: [{'from': 0, 'msg': {...}}, {'from': 1, 'msg': {...}}]
        for M in inbox:
            sender_id = M["from"]
            msg = M["msg"]

            # release task handing | what happens when agent (self or other) releases KCA task
            if "release" in msg:
                _released_task_id = msg["release"]
                self.unavailable_tasks.remove(_released_task_id)
                # this agent sent the message
                if sender_id == self.id:
                    self.queue.remove(_released_task_id)
                    self.release_task = None

        # endregion

        # MAKING AVAILABLE TASKS LIST
        self.unavailable_tasks = [t for t in self.unavailable_tasks if t in active_tasks_ids]
        available_task_ids = [t for t in active_tasks_ids if t not in self.unavailable_tasks]

        # delete inactive tasks from queue
        self.queue = [t for t in self.queue if t in active_tasks_ids]
        

        # region parse tasks and get claim and exploration status
        '''claim and/or exploration'''
        self.claim = None
        current_claim_distance_cost = math.inf
        _claim_cap_type = None # "KCA" and "KCC"
        exploration_tasks = {} # {taskid : distance}
        
        for taskid in available_task_ids:
            # task capability requirement
            _task_req_cap = all_tasks_from_id[taskid]["cap"]

            # simple ditance for exploration possibility
            _dist = dist(self.x, self.y, all_tasks_from_id[taskid]["x"], all_tasks_from_id[taskid]["y"])
            
            # task requires some capability but agent is unsure if it has capability or not + the agent can do the task based on deadline -> UC
            if (_task_req_cap is not None and _task_req_cap not in self.capabilities and _task_req_cap not in self.non_capabilities and
                (t + _dist / self.max_speed + all_tasks_from_id[taskid]["service"] < all_tasks_from_id[taskid]["deadline"])):
                # calls for exploration
                exploration_tasks[taskid] = dist(self.x, self.y, all_tasks_from_id[taskid]["x"], all_tasks_from_id[taskid]["y"])
            
            # handling the KC cases 

            # distance cost
            _dist = self.compute_distance_cost(all_tasks_from_id, taskid)
            
            # can agent physically complete this task before deadline?
            if not (t + _dist / self.max_speed + all_tasks_from_id[taskid]["service"] < all_tasks_from_id[taskid]["deadline"]):
                continue
            
            # no required capability for this task -> KCA 
            if _task_req_cap is None:
                # no competing task yet -> update 1st competing task
                if _claim_cap_type is None:
                    current_claim_distance_cost = _dist
                    self.claim = taskid
                    _claim_cap_type = "KCA"
                
                # if competing task is KCA
                elif (
                    _claim_cap_type == "KCA" and (
                        _dist < current_claim_distance_cost or # comparison based on distance
                        (
                            _dist == current_claim_distance_cost and 
                            all_tasks_from_id[taskid]["deadline"] < all_tasks_from_id[self.claim]["deadline"] # comparison based on deadline if distance is same
                        )
                    )
                ):
                    current_claim_distance_cost = _dist
                    self.claim = taskid

                # # if competing task is KCC (KCC always wins for now)
                # elif _dist < current_claim_distance_cost and :
                #     current_claim_distance_cost = _dist
                #     self.claim = taskid
                #     _claim_cap_type = "KCA"

            # agent has required capability for this task -> KCC
            elif _task_req_cap in self.capabilities:
                # no competing task yet -> update 1st competing task
                if _claim_cap_type is None:
                    current_claim_distance_cost = _dist
                    self.claim = taskid
                    _claim_cap_type = "KCC"
                
                # if competing task is KCC
                elif (
                    _claim_cap_type == "KCC" and (
                        _dist < current_claim_distance_cost or # comparison based on distance
                        (
                            _dist == current_claim_distance_cost and 
                            all_tasks_from_id[taskid]["deadline"] < all_tasks_from_id[self.claim]["deadline"] # comparison based on deadline if distance is same
                        )
                    )
                ):
                    current_claim_distance_cost = _dist
                    self.claim = taskid
                
                # if competing task is KCA (KCC always wins for now)
                else:
                    current_claim_distance_cost = _dist
                    self.claim = taskid
                    _claim_cap_type = "KCC"

            # agent does NOT have required capability for this task -> KR
            elif _task_req_cap in self.non_capabilities:
                # push task into "unavailable_tasks"
                self.unavailable_tasks.append(taskid)

        # endregion

        # region INBOX handling
        '''Check INBOX'''
        # inbox data: [{'from': 0, 'msg': {...}}, {'from': 1, 'msg': {...}}]
        _winner_id = None
        _winner_cost = math.inf
        for M in inbox:
            sender_id = M["from"]
            msg = M["msg"]

            # if msg contains keyword "claim"
            if "claim" in msg:
                claimed_task = msg["claim"]
                claimed_cost = msg["cost"]

                # move claimed task to unavailable tasks
                self.unavailable_tasks.append(claimed_task)
                
                # filter out claimed and "FAR" exploration tasks
                if claimed_task in exploration_tasks and claimed_cost <= exploration_tasks[claimed_task]:
                    del exploration_tasks[claimed_task]
                
                # Bidding
                if (claimed_task == self.claim and 
                    (claimed_cost < _winner_cost or (claimed_cost == _winner_cost and sender_id < _winner_id))):
                    _winner_id = sender_id
                    _winner_cost = claimed_cost
            
            # if msg contains the keyword "exp_done" -> remove task from queue or remove task from exploration
            if "exp_done" in msg:
                exp_done_taskid = msg["exp_done"]
                # other agent sent the message
                if sender_id != self.id:
                    if exp_done_taskid in self.queue: self.queue.remove(exp_done_taskid)
                    elif exp_done_taskid in exploration_tasks: del exploration_tasks[exp_done_taskid]
                # if this agent sent the message and it is recieved, then set messaging flag to false, so that we stop sending the message in later frames
                else:
                    self.exp_done_msg_required = False
                    if exp_done_taskid in exploration_tasks: del exploration_tasks[exp_done_taskid]
        
        # endregion

        # check if agent won bidding
        if _winner_id == self.id:
            self.queue.append(self.claim)

        # region SOLVE FOR VELOCITIES
        '''solve for velocities'''
        # initialise velocity values
        vx = vy = 0
        target_task = None

        # get E1:
        task_e1 = None
        # no need of exploration if queue is greater than max_limit_before_exploration
        if len(self.queue) < self.max_queue_limit_for_exploration:
            _min_exp_cost = math.inf
            for taskid in exploration_tasks:
                _exp_cost = exploration_tasks[taskid]
                if _exp_cost < _min_exp_cost:
                    _min_exp_cost = _exp_cost
                    task_e1 = taskid
        
        # get Q1:
        task_q1 = self.queue[0] if len(self.queue) > 0 else None

        # case 1: E1 does not exist
        if task_e1 is None:
            # sub case: but Q1 exist -> target Q1 only
            if task_q1 is not None:
                target_task = task_q1
        
        # case 2: E1 exists
        else:
            # sub case: but Q1 does not exist -> target E1 only
            if task_q1 is None:
                target_task = task_e1
                # also add to queue at starting point and add to unavailable_tasks
                self.queue.insert(0, task_e1)
                self.unavailable_tasks.append(task_e1)
            
            # major sub-case: both Q1 and E1 exists
            else:
                # get distance values
                _dq = dist(self.x, self.y, all_tasks_from_id[task_q1]["x"], all_tasks_from_id[task_q1]["y"])
                _de = exploration_tasks[task_e1]

                # Q1 required capability
                _q1_cap = all_tasks_from_id[task_q1]["cap"]

                # Q1 is KCA
                if _q1_cap is None:
                    # compare distance
                    if _de < _dq:
                        target_task = task_e1
                        # also add to queue at starting point and add to unavailable_tasks
                        self.queue.insert(0, task_e1)
                        self.unavailable_tasks.append(task_e1)
                        # release task Q1 (KCA) from queue for other agents : prepare for message, release only when message is sent
                        self.release_task = task_q1
                        
                
                # Q1 is KCC
                elif _q1_cap in self.capabilities:
                    _x = dist(
                        all_tasks_from_id[task_q1]["x"],
                        all_tasks_from_id[task_q1]["y"],
                        all_tasks_from_id[task_e1]["x"],
                        all_tasks_from_id[task_e1]["y"]
                    )
                    _ts_e = all_tasks_from_id[task_e1]["service"]
                    _ts_q = all_tasks_from_id[task_q1]["service"]
                    _ded_q = all_tasks_from_id[task_q1]["deadline"]
                    if (t + (_de + _x) / self.max_speed + _ts_q + _ts_e) <= _ded_q:
                        target_task = task_e1
                        # also add to queue at starting point and add to unavailable_tasks
                        self.queue.insert(0, task_e1)
                        self.unavailable_tasks.append(task_e1)
                
                # Q1 is UC
                else:
                    # compare distance only
                    if _de < _dq:
                        target_task = task_e1
                        # also add to queue at starting point and add to unavailable_tasks
                        self.queue.insert(0, task_e1)
                        self.unavailable_tasks.append(task_e1)
                        # remove "bad" exploration option from queue
                        self.queue.remove(task_q1)
                        # self.unavailable_tasks.remove(task_q1)
                    else:
                        target_task = task_q1
                
        # now we have "target_task"
        
        # UPDATE VELOCITIES NOW
        
        # "target_task" is some finite task
        if target_task is not None:
            target_x, target_y = all_tasks_from_id[target_task]["x"], all_tasks_from_id[target_task]["y"]
            delta_x, delta_y = target_x - self.x, target_y - self.y
            distance = math.sqrt(delta_x * delta_x + delta_y * delta_y)
            eps = max(self.max_speed * dt, 1e-6)
            # at task location
            if distance <= eps:
                self.task_doing_counter += 1
                
                # update capabilities
                if self.task_doing_counter == 2:
                    _current_task = all_tasks_from_id[target_task]
                    _cap = _current_task["cap"]
                    # if agent has spent 2 dt doing the task and task is happening (remianing_time is reducing) -> include required_cap in self.capabilities
                    if _current_task["remaining"] < _current_task["service"] and _cap not in self.capabilities:
                        self.capabilities.append(_cap)
                        self.exp_done_msg_required = True # this flag will make agent send exp_done message
                    # task is not happening
                    elif _current_task["remaining"] == _current_task["service"] and _cap not in self.capabilities:
                        self.non_capabilities.append(_cap)
                        self.queue.remove(target_task)
            
            # not yet reached task location
            else:
                self.task_doing_counter = 0
                vx = delta_x / distance * self.max_speed
                vy = delta_y / distance * self.max_speed
        
        # in case no target_task is assigned
        else:
            self.task_doing_counter = 0

        # endregion

        
        # region OUTBOX handling
        '''OUTBOX handling'''
        # initialisation
        send_msg = {}

        # claim - cost MESSAGE
        if self.claim is not None:
            send_msg["claim"] = self.claim
            send_msg["cost"] = current_claim_distance_cost

        # exp_done MESSAGE
        if self.exp_done_msg_required:
            send_msg["exp_done"] = target_task

        # KCA task release MESSAGE
        if self.release_task is not None:
            send_msg["release"] = self.release_task
         
        # endregion

        # send message only if "send_msg" is polulated
        if send_msg != {}:
            self.outbox = [send_msg]
        else:
            self.outbox = []

        #  DEBUG
        if self.debug_mode:
            self.debug(t) 
        
        return {"vx": vx, "vy": vy}, self.outbox

        
        