from .chaos import scenario as chaos
from .ddos_mbb import scenario as ddos_mbb
from .elephant_heavytail import scenario as elephant_heavytail
from .normal_load import scenario as normal_load
from .topology_physics import scenario as topology_physics


ALL_SCENARIOS = [
    normal_load,
    elephant_heavytail,
    topology_physics,
    ddos_mbb,
    chaos,
]

