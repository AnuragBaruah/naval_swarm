import math, random

# import for debug purposes
import atexit
import sys
from pathlib import Path
import json

# global variable
value_scale = 2

# # global variable
# i. set False: if agent doesn't know its own capabilities as well as others:
# ii. set True: if agent knows its own capabilities and others
pre_set_capability_mode = False

# If capability knowledge is preloaded, locate the scenario file defining agent capabilities
if  pre_set_capability_mode:
    _base = Path(__file__).resolve().parent
    _candidates = [
        _base / "scenarios" / "S7.json",
        _base.parent / "scenarios" / "S7.json",
    ]
    capability_filename_path = None
    for path in _candidates:
        if path.exists():
            capability_filename_path = path
            break

# distance between 2 points
def dist(ax, ay, bx, by):
    return ((ax-bx)**2 + (ay-by)**2) ** 0.5

class Agent:
    # region - init fnction
    def __init__(self, agent_id, world_bounds, speed, seed):
        # fixed seed initialisation for predictable randomness (in case ever use randomness)
        random.seed(seed)

        # initialisation (compulsory)
        self.id = agent_id
        self.max_speed = speed      # self.world_bounds = world_bounds

        # initialisation (general)
        self.claim = None
        self.release_task = None
        self.queue = []
        self.unavailable_tasks = []
        self.capabilities = []
        self.non_capabilities = []
        self.task_doing_counter = 0
        self.exp_done_msg_required = False
        self.outbox = []
        self.max_queue_limit_for_exploration = 3
        # for safeguard (tasks)
        self.prev_rem_times = None
        self.already_safeguarded_tasks = []

        # command switches
        self.leader_exists = False
        self.is_leader = False
        self.leader_term = 0
        self.lead_notify = False
        self.warning_task = None
        self.ownership = None

        # DEBUG FEATURES
        self.prev_queue = self.queue.copy()
        self.prev_cap = self.capabilities.copy()
        self.prev_no_cap = self.non_capabilities.copy()
        
        # general debug mode
        self.debug_mode = False

        # debug file creation
        if self.debug_mode:
            self.debug_file = open(f"DEBUG\\agent_{self.id}.log", "w", buffering = 1)
            atexit.register(self.close_debug_file)

        # Preload agent capabilities and non-capabilities from scenario file when capability knowledge is fixed
        if pre_set_capability_mode and capability_filename_path:
            with open(capability_filename_path, 'r') as file:
                data = json.load(file)["agent_caps"]
            for i in range(len(data)):
                if i == self.id:
                    self.capabilities.extend(data[i])
                else:
                    self.non_capabilities.extend(data[i])

        # endregion

    # Detect and log changes in task queue, capabilities, and non-capabilities to the debug file
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
    
    # compute_distance_cost_2
    def compute_distance_cost_2(self, all_tasks, taskid):
        cost = 0
        x, y = self.x, self.y
        for q in self.queue:
            if q == taskid:
                break
            if q in all_tasks:
                cost += dist(x, y, all_tasks[q]["x"], all_tasks[q]["y"])
                cost += all_tasks[q]["remaining"] * self.max_speed
                x, y = all_tasks[q]["x"], all_tasks[q]["y"]
        
        cost += dist(x, y, all_tasks[taskid]["x"], all_tasks[taskid]["y"])
        return cost

    # compute_distance_cost
    def compute_distance_cost(self, all_tasks, taskid):
        cost = 0
        x, y = self.x, self.y
        for q in self.queue:
            if q in all_tasks:
                cost += dist(x, y, all_tasks[q]["x"], all_tasks[q]["y"])
                cost += all_tasks[q]["remaining"] * self.max_speed
                x, y = all_tasks[q]["x"], all_tasks[q]["y"]
        
        cost += dist(x, y, all_tasks[taskid]["x"], all_tasks[taskid]["y"])
        return cost
    
    # the important "STEP" function
    def step(self, t, dt, self_state, tasks_visible, inbox):
        # get self coordinates
        self.x, self.y = self_state["x"], self_state["y"]

        # get tasks_visible : [{'id': 1, 'x': 1146.0738385082163, 'y': 450.55809196144605, 't0': 2, 'deadline': 5, 'service': 2, 'value': 10, 'remaining': 2, 'cap': None}]
        active_tasks_ids = [task["id"] for task in tasks_visible] 
        all_tasks_from_id = dict(zip(active_tasks_ids, tasks_visible))     # getting a "id to task" mapping for ease of access

        # region INBOX handling - handle all (except one) inbox related tasks
        '''INBOX handling - handle all (except one) inbox related tasks'''
        _winner_id = None
        _winner_cost = math.inf
        _best_lead = math.inf
        self.leader_exists = False
        for M in inbox:
            sender_id = M["from"]
            msg = M["msg"]

            # ownership handling
            if "task_id" in msg and sender_id == self.id:
                # pass
                self.ownership = None

            # release task handing | what happens when agent (self or other) releases KCA task
            if "release" in msg:
                _released_task_id = msg["release"]
                self.unavailable_tasks.remove(_released_task_id)
                # this agent sent the message
                if sender_id == self.id:
                    self.queue.remove(_released_task_id)
                    self.release_task = None

            # if "warning" is sent -> forfeit task | if agent itself sent warning; then turn off flag
            if "warning" in msg:
                _w = msg["warning"]
                if sender_id == self.id:
                    self.warning_task = None
                elif _w in self.queue:
                    self.queue.remove(_w)

            # if msg contains keyword "claim"
            if "claim" in msg:
                claimed_task = msg["claim"]
                claimed_cost = msg["cost"]

                # move claimed task to unavailable tasks
                if claimed_task not in self.unavailable_tasks: self.unavailable_tasks.append(claimed_task)
                
                # Bidding
                if (claimed_task == self.claim and      
                    (claimed_cost < _winner_cost or (claimed_cost == _winner_cost and sender_id < _winner_id))):
                    _winner_id = sender_id
                    _winner_cost = claimed_cost
                
                # if someone claims task already in agent's queue | late claim or due to safeguard
                elif claimed_task in self.queue:
                    # check if claimed cost is better than your cost -> forfeit task
                    if claimed_cost < self.compute_distance_cost(all_tasks_from_id, claimed_task):
                        self.queue.remove(claimed_task)
                    # else -> send warning signal to notify other agents to remove from queue
                    else:
                        self.warning_task = claimed_task
            
            # if message contains the keyword "role" : existence of leader
            if "role" in msg:
                self.leader_exists = True
                # if "special" format message was successfully sent then switch off flag to send special message
                if "type" in msg and sender_id == self.id:
                    self.lead_notify = False

            # if message contains the keyword "me_lead" : initiate leader bidding
            if "me_lead" in msg and sender_id < _best_lead:
                _best_lead = sender_id
        
        # endregion

        reclaim_possibility = False # for task bidding packet loss handling
        # check if agent won bidding
        if _winner_id == self.id:
            self.queue.append(self.claim)
            self.ownership = self.claim
        # agent claimed, did not win but still cost is less than winner_cost -> packet loss happened and reclaim and makes sense
        # agent's message was never recieved
        elif self.claim is not None and self.outbox[0]["cost"] < _winner_cost:
            reclaim_possibility = True

        # check leader bidding
        if _best_lead != math.inf:
            self.leader_exists = True
            self.leader_term += 1
            if _best_lead == self.id:
                self.is_leader = True
                self.lead_notify = True
            else:
                self.is_leader = False
                self.lead_notify = False

        # MAKING AVAILABLE TASKS LIST
        self.unavailable_tasks = [t for t in self.unavailable_tasks if t in active_tasks_ids]
        available_task_ids = [t for t in active_tasks_ids if t not in self.unavailable_tasks]

        # delete inactive tasks from queue
        self.queue = [t for t in self.queue if t in active_tasks_ids]

        # region safeguard against undone tasks
        if len(self.queue) == 0:
            _u = [t for t in self.unavailable_tasks if t not in self.already_safeguarded_tasks]
            for taskid in _u:
                _task = all_tasks_from_id[taskid]        
                if _task["remaining"] == _task["service"] or _task["remaining"] == self.prev_rem_times[taskid]:
                    _dist = dist(self.x, self.y, _task["x"], _task["y"])
                    if _task["deadline"] - (t + _task["service"] + _dist / self.max_speed) < 4*dt:
                        self.unavailable_tasks.remove(taskid)
                        available_task_ids.append(taskid)
                        self.already_safeguarded_tasks.append(taskid)
        # endregion
        

        # region claim and/or explore//
        '''claim and/or exploration'''
        current_claim = None
        current_claim_distance_cost = math.inf
        _claim_cap_type = None # "KCA" and "KCC"
        exploration_tasks = {} # {taskid : distance}
        
        for taskid in available_task_ids:
            # task capability requirement
            _task_req_cap = all_tasks_from_id[taskid]["cap"]
            
            # task requires some capability but agent is unsure if it has capability or not -> UC
            if (_task_req_cap is not None and _task_req_cap not in self.capabilities and _task_req_cap not in self.non_capabilities):
                # simple distance for exploration possibility
                _dist = dist(self.x, self.y, all_tasks_from_id[taskid]["x"], all_tasks_from_id[taskid]["y"])
                # if the agent can do the task based on deadline:
                if (t + _dist / self.max_speed + all_tasks_from_id[taskid]["service"] < all_tasks_from_id[taskid]["deadline"]):
                    # calls for exploration
                    _cost = _dist - all_tasks_from_id[taskid]["value"] * value_scale
                    exploration_tasks[taskid] = _cost
            
            # handling the KC cases 

            # distance cost
            _dist = self.compute_distance_cost(all_tasks_from_id, taskid)
            _cost = _dist - all_tasks_from_id[taskid]["value"] * value_scale
            # can agent physically complete this task before deadline?
            if not (t + _dist / self.max_speed + all_tasks_from_id[taskid]["service"] < all_tasks_from_id[taskid]["deadline"]):
                continue
            
            # no required capability for this task -> KCA 
            if _task_req_cap is None:
                # no competing task yet -> update 1st competing task
                if _claim_cap_type is None:
                    current_claim_distance_cost = _cost
                    current_claim = taskid
                    _claim_cap_type = "KCA"
                
                # if competing task is KCA
                elif (
                    _claim_cap_type == "KCA" and (
                        _cost < current_claim_distance_cost or # comparison based on distance
                        (
                            _cost == current_claim_distance_cost and 
                            all_tasks_from_id[taskid]["deadline"] < all_tasks_from_id[current_claim]["deadline"] # comparison based on deadline if distance is same
                        )
                    )
                ):
                    current_claim_distance_cost = _cost
                    current_claim = taskid

            # agent has required capability for this task -> KCC
            elif _task_req_cap in self.capabilities:
                # no competing task yet -> update 1st competing task
                if _claim_cap_type is None:
                    current_claim_distance_cost = _cost
                    current_claim = taskid
                    _claim_cap_type = "KCC"
                
                # if competing task is KCC
                elif (
                    _claim_cap_type == "KCC" and (
                        _cost < current_claim_distance_cost or # comparison based on distance
                        (
                            _cost == current_claim_distance_cost and 
                            all_tasks_from_id[taskid]["deadline"] < all_tasks_from_id[current_claim]["deadline"] # comparison based on deadline if distance is same
                        )
                    )
                ):
                    current_claim_distance_cost = _cost
                    current_claim = taskid
                
                # if competing task is KCA (KCC always wins for now)
                else:
                    current_claim_distance_cost = _cost
                    current_claim = taskid
                    _claim_cap_type = "KCC"

            # agent does NOT have required capability for this task -> KR
            elif _task_req_cap in self.non_capabilities:
                # push task into "unavailable_tasks"
                self.unavailable_tasks.append(taskid)

        # endregion

        # region INBOX handling only for removing unnecessary exploration tasks
        '''INBOX handling only for removing unnecessary exploration tasks'''
        for M in inbox:
            msg = M["msg"]
            # if msg contains keyword "claim"
            if "claim" in msg:
                claimed_task = msg["claim"]
                claimed_cost = msg["cost"]
                # filter out claimed and "FAR" exploration tasks
                if claimed_task in exploration_tasks and claimed_cost <= exploration_tasks[claimed_task]:
                    del exploration_tasks[claimed_task]

            # if msg contains the keyword "exp_done" -> remove task from queue or remove task from exploration
            if "exp_done" in msg:
                exp_done_taskid = msg["exp_done"]
                # other agent sent the message
                if sender_id != self.id:
                    if exp_done_taskid in self.queue: self.queue.remove(exp_done_taskid)
                    if exp_done_taskid in exploration_tasks: del exploration_tasks[exp_done_taskid]
                # if this agent sent the message and it is recieved, then set messaging flag to false, so that we stop sending the message in later frames
                else:
                    self.ownership = exp_done_taskid
                    self.exp_done_msg_required = False
                    # if exp_done_taskid in exploration_tasks: del exploration_tasks[exp_done_taskid]
                    # if exp_done_taskid in self.queue: self.queue.remove(exp_done_taskid)
        
        # endregion

        # region Target task
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

        # case 1: E1 does not exist but Q1 exist -> target Q1 only
        if task_e1 is None and task_q1 is not None:
            target_task = task_q1
        
        # case 2: E1 exists
        elif task_e1 is not None:
            # sub case: but Q1 does not exist -> target E1 only
            if task_q1 is None:
                target_task = task_e1
                # also add to queue at starting point and add to unavailable_tasks
                self.queue.insert(0, task_e1)
                self.unavailable_tasks.append(task_e1)
            
            # major sub-case: both Q1 and E1 exists
            else:
                # get distance values
                _dq = dist(self.x, self.y, all_tasks_from_id[task_q1]["x"], all_tasks_from_id[task_q1]["y"]) - all_tasks_from_id[task_q1]["value"] * value_scale
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
                    else:
                        target_task = task_q1
                        
                
                # Q1 is KCC
                elif _q1_cap in self.capabilities:
                    _x = dist(
                        all_tasks_from_id[task_q1]["x"],
                        all_tasks_from_id[task_q1]["y"],
                        all_tasks_from_id[task_e1]["x"],
                        all_tasks_from_id[task_e1]["y"]
                    )
                    dd = dist(self.x, self.y, all_tasks_from_id[task_e1]["x"], all_tasks_from_id[task_e1]["y"])
                    _ts_e = all_tasks_from_id[task_e1]["service"]
                    _ts_q = all_tasks_from_id[task_q1]["service"]
                    _ded_q = all_tasks_from_id[task_q1]["deadline"]
                    if (t + (dd + _x) / self.max_speed + _ts_q + _ts_e) <= _ded_q:
                        target_task = task_e1
                        # also add to queue at starting point and add to unavailable_tasks
                        self.queue.insert(0, task_e1)
                        self.unavailable_tasks.append(task_e1)
                    else:
                        target_task = task_q1
                
                # Q1 is UC
                else:
                    # compare cost only
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
                
        # endregion
        
        # region VELOCITIES update
        '''solve for velocities'''
        # initialise velocity values
        vx = vy = 0
        
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
                    # if agent has spent dt time doing the task and task is happening (remianing_time is reducing) -> include required_cap in self.capabilities
                    if _cap is not None and _current_task["remaining"] < _current_task["service"] and _cap not in self.capabilities:
                        self.capabilities.append(_cap)
                        self.exp_done_msg_required = True # this flag will make agent send exp_done message
                    # task is not happening
                    elif _cap is not None and _current_task["remaining"] == _current_task["service"] and _cap not in self.capabilities:
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

        # ownership MESSAGE
        if self.ownership is not None:
            send_msg["type"] = "claim"
            send_msg["task_id"] = self.ownership

        # claim - cost MESSAGE
        if reclaim_possibility:
            _c = self.outbox[0]["cost"]
            if _c < current_claim_distance_cost:
                current_claim_distance_cost = _c
        else:
            self.claim = current_claim
        if self.claim is not None:
            send_msg["claim"] = self.claim
            send_msg["cost"] = current_claim_distance_cost

        # exp_done MESSAGE
        if self.exp_done_msg_required:
            send_msg["exp_done"] = target_task 

        # KCA task release MESSAGE
        if self.release_task is not None:
            send_msg["release"] = self.release_task

        # warning MESSAGE
        if self.warning_task is not None:
            send_msg["warning"] = self.warning_task

        # leader related messages
        # if no leader exists -> participate in leader bidding 
        if not self.leader_exists:
            send_msg["me_lead"] = True
        # leader exists | if agent is leader:  
        elif self.is_leader:
            # send simple existantial message to let everyone know agent is alive
            send_msg["role"] = "leader"
            # agent needs to notify to evaluator -> send specific format message
            if self.lead_notify and self.ownership is None:
                send_msg["type"] = "role"
                send_msg["term"] = self.leader_term
         
        # endregion

        # send message only if "send_msg" is populated
        if send_msg != {}:
            self.outbox = [send_msg]
        else:
            self.outbox = []

        #  DEBUG
        if self.debug_mode:
            self.debug(t)

        # safeguard update
        self.prev_rem_times = {t : all_tasks_from_id[t]["remaining"] for t in active_tasks_ids}
        
        return {"vx": vx, "vy": vy}, self.outbox

        
        