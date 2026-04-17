import gymnasium as gym
from gymnasium import spaces
import numpy as np
from typing import Optional, Dict, Any, List
from src.core.interfaces.repository import IRepository
from src.orchestration.jo_vdpr.rewards import RewardCalculator

class JOVDPREnv(gym.Env):
    LATENCY_MATRIX = np.array([
        [ 0,  2,  5,  8, 200], # Node 4: International DC (e.g. US) có trễ cao
        [ 2,  0,  2,  5, 198],
        [ 5,  2,  0,  2, 195],
        [ 8,  5,  2,  0, 192],
        [200, 198, 195, 192, 0],
    ], dtype=np.float32)

    def __init__(self, 
                 repository: IRepository, 
                 reward_calculator: Optional[RewardCalculator] = None,
                 num_nodes=5, 
                 episode_length=100):
        super(JOVDPREnv, self).__init__()
        self.num_nodes = num_nodes
        self.repo = repository
        self.reward_calculator = reward_calculator or RewardCalculator()
        self.EPISODE_LENGTH = episode_length

        self.node_msd_limits = np.array([3, 6, 3, 3, 3], dtype=np.float32)
        self.max_cpu = 100.0
        self.max_ram = 100.0

        obs_size = self.num_nodes * 3 + 3 + 5 # 3 features per node + 3 req + 5 traffic_class OH
        self.observation_space = spaces.Box(
            low=0.0, high=1.0, shape=(obs_size,), dtype=np.float32
        )
        self.action_space = spaces.MultiDiscrete([self.num_nodes, self.num_nodes])

        self.current_time_step = 0
        self._raw_state = np.zeros(self.num_nodes * 3, dtype=np.float32)
        self._current_req = {'cpu': 0.0, 'ram': 0.0, 'msd': 1, 'service_type': 'Data'}

    def _get_obs(self):
        obs = np.zeros(self.num_nodes * 3 + 3 + 5, dtype=np.float32)
        for i in range(self.num_nodes):
            obs[i*3]     = self._raw_state[i*3]     / self.max_cpu
            obs[i*3 + 1] = self._raw_state[i*3 + 1] / self.max_ram
            obs[i*3 + 2] = self._raw_state[i*3 + 2] / self.node_msd_limits[i]
        
        obs[self.num_nodes * 3]     = self._current_req['cpu'] / self.max_cpu
        obs[self.num_nodes * 3 + 1] = self._current_req['ram'] / self.max_ram
        obs[self.num_nodes * 3 + 2] = self._current_req['msd'] / 6.0
        
        # Traffic Class One-Hot Encoded
        svc = self._current_req.get('service_type', 'Data')
        svc_map = {'Video': 0, 'VoIP': 1, 'Data': 2, 'IoT': 3, 'Attack': 4}
        idx = svc_map.get(svc, 2)
        obs[self.num_nodes * 3 + 3 + idx] = 1.0
        
        return np.clip(obs, 0.0, 1.0)

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.current_time_step = 0
        self._raw_state = np.zeros(self.num_nodes * 3, dtype=np.float32)
        self._current_req = {'cpu': 0.0, 'ram': 0.0, 'msd': 1, 'service_type': 'Data'}
        return self._get_obs(), {}

    def step(self, action):
        node_v1, node_v2 = int(action[0]), int(action[1])
        row = self.repo.get_next_entry(self.current_time_step)
        
        cpu_req = row['cpu']
        ram_req = row['ram']
        msd_req = row['msd']
        svc_type = row.get('service_type', 'Data')
        self._current_req = {'cpu': cpu_req, 'ram': ram_req, 'msd': msd_req, 'service_type': svc_type}
        is_elephant = (msd_req >= 4 or row['ddos'] == 1)

        # Decay logic
        for i in range(self.num_nodes):
            self._raw_state[i*3]     = max(0.0, self._raw_state[i*3]     - np.random.uniform(2.0, 8.0))
            self._raw_state[i*3 + 1] = max(0.0, self._raw_state[i*3 + 1] - np.random.uniform(1.0, 4.0))
            self._raw_state[i*3 + 2] = max(0.0, self._raw_state[i*3 + 2] - 1.0)

        # Constraints check
        errors = []
        is_valid = True
        
        cpu_v1 = self._raw_state[node_v1 * 3]
        cpu_v2 = self._raw_state[node_v2 * 3]
        msd_v1 = self._raw_state[node_v1 * 3 + 2]
        msd_v2 = self._raw_state[node_v2 * 3 + 2]

        if cpu_v1 + cpu_req > self.max_cpu or cpu_v2 + cpu_req > self.max_cpu:
            is_valid = False
            errors.append("CPU overflow")

        if msd_v1 + msd_req > self.node_msd_limits[node_v1]:
            is_valid = False
            errors.append(f"MSD violation node {node_v1}")

        if msd_v2 + msd_req > self.node_msd_limits[node_v2]:
            is_valid = False
            errors.append(f"MSD violation node {node_v2}")

        latency = self.LATENCY_MATRIX[node_v1][node_v2]
        
        reward = self.reward_calculator.calculate(
            is_valid=is_valid,
            errors=errors,
            is_elephant=is_elephant,
            latency=latency,
            cpu_req=cpu_req,
            max_cpu=self.max_cpu,
            node_v1=node_v1,
            node_v2=node_v2,
            service_type=svc_type
        )

        if is_valid:
            self._raw_state[node_v1 * 3]     += cpu_req
            self._raw_state[node_v1 * 3 + 1] += ram_req
            self._raw_state[node_v1 * 3 + 2] += msd_req
            self._raw_state[node_v2 * 3]     += cpu_req
            self._raw_state[node_v2 * 3 + 1] += ram_req
            self._raw_state[node_v2 * 3 + 2] += msd_req

        self.current_time_step += 1
        done = (self.current_time_step >= self.EPISODE_LENGTH)
        
        info = {'is_elephant': is_elephant, 'error_log': " | ".join(errors)}
        return self._get_obs(), float(reward), done, False, info
