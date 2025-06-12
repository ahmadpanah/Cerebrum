# gcc/controller.py
import networkx as nx
import community as community_louvain
import httpx
from typing import Dict, List
from utils.models import Workflow, MicroDAG, MacroDAG

class GlobalController:
    def __init__(self):
        # In-memory store of registered LCAs and their state
        # { "cluster_id": "http://lca_host:port" }
        self.federation_state: Dict[str, str] = {}
        # { "cluster_id": ClusterState }
        self.cluster_telemetry: Dict[str, Dict] = {}

    def register_lca(self, cluster_id: str, lca_url: str, state: Dict):
        print(f"[GCC] Registering LCA for cluster '{cluster_id}' at {lca_url}")
        self.federation_state[cluster_id] = lca_url
        self.cluster_telemetry[cluster_id] = state
        return {"status": "registered"}

    def _perform_hwd(self, workflow: Workflow) -> (MacroDAG, Dict[str, MicroDAG]):
        """Implements Algorithm 1: Hierarchical Workflow Decomposition."""
        print(f"[GCC] Performing HWD for workflow '{workflow.id}'")
        G = nx.Graph()
        task_map = {task.id: task for task in workflow.tasks}

        # 1. Construct weighted undirected graph
        for edge, volume in workflow.data_volumes.items():
            u, v = edge.split('-')
            G.add_edge(u, v, weight=volume)
        
        # Add tasks that might be isolated
        for task in workflow.tasks:
            if task.id not in G:
                G.add_node(task.id)

        # 2. Apply Louvain community detection
        partition = community_louvain.best_partition(G, weight='weight')
        
        # Group tasks by community ID
        communities: Dict[int, List[str]] = {}
        for task_id, comm_id in partition.items():
            communities.setdefault(comm_id, []).append(task_id)

        # 3. Create Micro-DAGs
        micro_dags: Dict[str, MicroDAG] = {}
        for comm_id, tasks in communities.items():
            micro_dag_id = f"{workflow.id}-sub-{comm_id}"
            
            # Create subgraph from original DAG
            sub_deps = {t: [d for d in workflow.dependencies.get(t, []) if d in tasks] for t in tasks}
            sub_vols = {e: v for e, v in workflow.data_volumes.items() if all(p in tasks for p in e.split('-'))}
            
            micro_dags[micro_dag_id] = MicroDAG(
                id=micro_dag_id,
                tasks=[task_map[t] for t in tasks],
                dependencies=sub_deps,
                data_volumes=sub_vols
            )
        
        # 4. Construct Macro-DAG (simplified for this example)
        # In a full implementation, you'd build the macro-dependency graph
        print(f"[GCC] HWD resulted in {len(micro_dags)} sub-graphs.")
        # We will return the dictionary of micro_dags and schedule them individually
        return micro_dags

    def _perform_macro_scheduling(self, micro_dags: Dict[str, MicroDAG]) -> Dict[str, MicroDAG]:
        """Assigns each Micro-DAG to a cluster. Simple heuristic implementation."""
        print("[GCC] Performing Macro-Scheduling...")
        scheduled_dags = {}

        # Simple greedy strategy: assign to the first cluster that has enough resources
        # A real implementation would be much more complex (e.g., bin packing, cost models)
        for dag_id, dag in micro_dags.items():
            # Estimate aggregate resource needs
            total_cpu = sum(t.cpu_req for t in dag.tasks)
            total_mem = sum(t.mem_req for t in dag.tasks)
            
            assigned_cluster = None
            for cluster_id, state in self.cluster_telemetry.items():
                cluster_cpu_avail = sum(n['cpu_avail'] for n in state['nodes'])
                cluster_mem_avail = sum(n['mem_avail'] for n in state['nodes'])
                
                if cluster_cpu_avail > total_cpu and cluster_mem_avail > total_mem:
                    dag.cluster_id = cluster_id
                    scheduled_dags[dag_id] = dag
                    assigned_cluster = cluster_id
                    break # Assign to the first fit
            
            if not assigned_cluster:
                print(f"[GCC] WARNING: No suitable cluster found for {dag_id}!")
            else:
                 print(f"[GCC] Assigned Micro-DAG '{dag_id}' to Cluster '{assigned_cluster}'")

        return scheduled_dags

    async def dispatch_workflow(self, workflow: Workflow):
        """Full pipeline: HWD -> Macro-Schedule -> Dispatch."""
        # 1. Decompose
        micro_dags = self._perform_hwd(workflow)
        
        # 2. Schedule sub-graphs to clusters
        scheduled_dags = self._perform_macro_scheduling(micro_dags)

        # 3. Dispatch to LCAs asynchronously
        async with httpx.AsyncClient() as client:
            for dag_id, dag in scheduled_dags.items():
                lca_url = self.federation_state.get(dag.cluster_id)
                if lca_url:
                    print(f"[GCC] Dispatching '{dag_id}' to {lca_url}")
                    try:
                        await client.post(f"{lca_url}/schedule_subgraph", json=dag.dict())
                    except httpx.RequestError as e:
                        print(f"[GCC] ERROR: Could not dispatch to LCA at {lca_url}. Reason: {e}")