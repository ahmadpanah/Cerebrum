# lca/agent.py
import asyncio
import httpx
from kubernetes import client, config
from typing import Dict, List
from utils.models import MicroDAG, NodeInfo, ClusterState

# --- Placeholder for the complex RL Micro-Scheduler ---
class MicroSchedulerRL:
    """
    This is a placeholder for the Deep Reinforcement Learning agent.
    A real implementation would use a library like stable-baselines3.
    """
    def __init__(self, cluster_state: ClusterState):
        self.cluster_state = cluster_state
        print("[LCA-RL] Micro-scheduler initialized.")

    def _build_state(self, task):
        """
        In a real RL model, the state would be a numerical vector/tensor
        representing the task's requirements and the current+predicted
        state of all nodes in the cluster.
        """
        # Simplified state: just the task requirements
        return [task.cpu_req, task.mem_req]

    def select_node(self, task) -> str:
        """
        The core RL action: select the best node for a task.
        This placeholder implements a simple heuristic (best fit).
        A real agent would use a learned policy (e.g., a neural network).
        """
        state = self._build_state(task)
        print(f"[LCA-RL] Selecting node for task '{task.id}' with state: {state}")

        best_node = None
        min_remaining_cpu = float('inf')

        for node in self.cluster_state.nodes:
            # Use predicted availability for proactive scheduling
            if node.predicted_cpu_avail >= task.cpu_req and node.mem_avail >= task.mem_req:
                # 'Best fit' heuristic: choose the node that will have the least CPU left
                remaining_cpu = node.predicted_cpu_avail - task.cpu_req
                if remaining_cpu < min_remaining_cpu:
                    min_remaining_cpu = remaining_cpu
                    best_node = node.name
        
        print(f"[LCA-RL] Decision: Place task '{task.id}' on node '{best_node}'")
        return best_node

# --- The main LCA class ---
class LocalAgent:
    def __init__(self, cluster_id: str, gcc_url: str):
        self.cluster_id = cluster_id
        self.gcc_url = gcc_url
        self.cluster_state = ClusterState(cluster_id=cluster_id, nodes=[])
        self.k8s_api = self._get_k8s_client()
        self.scheduler_queue = asyncio.Queue()

    def _get_k8s_client(self):
        """Initializes the Kubernetes client. Assumes it's running in-cluster."""
        try:
            config.load_incluster_config()
            print("[LCA] Loaded in-cluster Kubernetes config.")
        except config.ConfigException:
            config.load_kube_config()
            print("[LCA] Loaded local kubeconfig (for testing).")
        return client.CoreV1Api()

    async def _monitor_cluster(self):
        """Background task to periodically fetch cluster state."""
        while True:
            print(f"[LCA-{self.cluster_id}] Monitoring cluster state...")
            try:
                node_list = self.k8s_api.list_node()
                new_nodes = []
                for node in node_list.items:
                    # NOTE: This is a simplified view of available resources.
                    # A real system would subtract the requests of all running pods.
                    cpu_avail = float(node.status.allocatable['cpu'].replace('m', ''))
                    mem_avail = int(node.status.allocatable['memory'][:-2]) # Ki -> Mi
                    new_nodes.append(NodeInfo(
                        name=node.metadata.name,
                        cpu_avail=cpu_avail,
                        mem_avail=mem_avail,
                        labels=node.metadata.labels
                    ))
                self.cluster_state.nodes = new_nodes
            except Exception as e:
                print(f"[LCA-{self.cluster_id}] ERROR monitoring cluster: {e}")
            
            await asyncio.sleep(30) # Monitor every 30 seconds

    async def _run_prediction_engine(self):
        """Placeholder for the proactive prediction engine."""
        while True:
            # In a real system, this would use a trained model (e.g., LSTM)
            # on historical data from the monitor.
            # Here, we just simulate a prediction.
            print(f"[LCA-{self.cluster_id}] Running prediction engine...")
            for node in self.cluster_state.nodes:
                # Simulate prediction: assume future availability is 95% of current
                node.predicted_cpu_avail = node.cpu_avail * 0.95
            await asyncio.sleep(60) # Predict every minute

    async def _register_with_gcc(self):
        """Registers this LCA with the GCC on startup."""
        print(f"[LCA-{self.cluster_id}] Attempting to register with GCC at {self.gcc_url}")
        async with httpx.AsyncClient() as client:
            try:
                await client.post(
                    f"{self.gcc_url}/register_lca",
                    json={
                        "cluster_id": self.cluster_id,
                        "lca_url": f"http://localhost:my_port", # Replace with actual URL
                        "state": self.cluster_state.dict()
                    },
                    timeout=5.0
                )
                print(f"[LCA-{self.cluster_id}] Successfully registered with GCC.")
            except httpx.RequestError as e:
                print(f"[LCA-{self.cluster_id}] FAILED to register with GCC: {e}. Retrying...")
                await asyncio.sleep(10)
                await self._register_with_gcc()

    async def _actuator(self, task, node_name: str):
        """Creates a Kubernetes pod for the given task on the specified node."""
        if not node_name:
            print(f"[LCA-Actuator] Cannot create pod for task '{task.id}', no node selected.")
            return

        print(f"[LCA-Actuator] Creating pod for task '{task.id}' on node '{node_name}'...")
        pod_manifest = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {"name": f"cerebrum-task-{task.id.lower()}"},
            "spec": {
                "nodeName": node_name,
                "containers": [{
                    "name": "task-container",
                    "image": task.image,
                    "resources": {
                        "requests": {
                            "cpu": f"{task.cpu_req}m",
                            "memory": f"{task.mem_req}Mi"
                        }
                    }
                }],
                "restartPolicy": "Never"
            }
        }
        try:
            self.k8s_api.create_namespaced_pod(body=pod_manifest, namespace="default")
            print(f"[LCA-Actuator] Successfully created pod for task '{task.id}'.")
        except client.ApiException as e:
            print(f"[LCA-Actuator] ERROR creating pod: {e.body}")

    async def _process_subgraph(self):
        """Worker that processes micro-DAGs from the queue."""
        while True:
            dag: MicroDAG = await self.scheduler_queue.get()
            print(f"[LCA-{self.cluster_id}] Processing subgraph '{dag.id}'")
            
            # Create a scheduler instance with the LATEST cluster state
            micro_scheduler = MicroSchedulerRL(self.cluster_state)

            # NOTE: This is a simplified sequential execution. A real system
            # would use a topological sort and schedule tasks as their
            # dependencies are met.
            for task in dag.tasks:
                node_name = micro_scheduler.select_node(task)
                await self._actuator(task, node_name)
                # Simulate task execution time before scheduling the next one
                await asyncio.sleep(2) 
            
            self.scheduler_queue.task_done()
    
    async def schedule_subgraph(self, dag: MicroDAG):
        await self.scheduler_queue.put(dag)
        return {"status": "subgraph queued for scheduling"}

    async def run(self):
        """Starts all background tasks for the agent."""
        # Run startup registration
        await self._register_with_gcc()

        # Create background tasks
        asyncio.create_task(self._monitor_cluster())
        asyncio.create_task(self._run_prediction_engine())
        asyncio.create_task(self._process_subgraph())
        print(f"[LCA-{self.cluster_id}] Agent is running and all tasks started.")