# utils/models.py
from pydantic import BaseModel
from typing import List, Dict, Any

class Task(BaseModel):
    id: str
    image: str
    cpu_req: float  # in millicores
    mem_req: int    # in MiB

class Workflow(BaseModel):
    id: str
    tasks: List[Task]
    # Adjacency list representation of the DAG: { "task_id": ["dep1", "dep2"] }
    dependencies: Dict[str, List[str]]
    # Data volume between tasks: { "task_id_from-task_id_to": 128 } (in MB)
    data_volumes: Dict[str, int]

class NodeInfo(BaseModel):
    name: str
    cpu_avail: float
    mem_avail: int
    labels: Dict[str, str]
    # Placeholder for predicted future state
    predicted_cpu_avail: float = 0.0

class ClusterState(BaseModel):
    cluster_id: str
    nodes: List[NodeInfo]

# Models for internal use after HWD
class MicroDAG(Workflow):
    cluster_id: str = None # Assigned by GCC

class MacroDAG(BaseModel):
    nodes: Dict[str, MicroDAG] # node_id -> MicroDAG
    dependencies: Dict[str, List[str]]
    inter_cluster_volumes: Dict[str, int]