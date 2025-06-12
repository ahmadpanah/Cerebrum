# Cerebrum: A Proactive, Learning-Based Scheduling Federation

This repository contains a Python implementation framework for the Cerebrum scheduling system, as described in the research paper. It provides a skeletal structure for the Global Cerebrum Controller (GCC) and the Local Cerebrum Agent (LCA), including API endpoints, Kubernetes integration points, and placeholders for the core algorithms.

## Architecture Overview

The implementation directly mirrors the paper's two-tiered architecture:

1.  **Global Cerebrum Controller (GCC)**: A central FastAPI server responsible for:
    *   Accepting new application DAGs via a REST API.
    *   Performing Hierarchical Workflow Decomposition (HWD) using `networkx`.
    *   Running a macro-scheduler to assign sub-graphs (micro-DAGs) to clusters.
    *   Dispatching these sub-graphs to the appropriate LCA.

2.  **Local Cerebrum Agent (LCA)**: A standalone agent deployed in each managed Kubernetes cluster. It is also a FastAPI server that:
    *   Registers itself with the GCC on startup.
    *   Continuously monitors its cluster's node status using the `kubernetes` Python client.
    *   Runs a (placeholder) proactive prediction engine to forecast resource usage.
    *   Receives sub-graphs from the GCC.
    *   Uses a (placeholder) RL-based micro-scheduler to place individual tasks on nodes.
    *   Acts on these decisions by creating Kubernetes Pods with specific node affinities.

## Technology Stack

*   **Web Framework**: `FastAPI` for creating asynchronous, high-performance APIs for both GCC and LCAs.
*   **Kubernetes Integration**: `kubernetes` official Python client for monitoring nodes and creating pods.
*   **Graph Theory**: `networkx` for modeling DAGs and performing community detection (Louvain algorithm for HWD).
*   **HTTP Communication**: `httpx` for asynchronous GCC-to-LCA communication.
*   **Data Serialization**: `Pydantic` (comes with FastAPI) for defining structured data models (workflows, nodes, etc.).
*   **ML/Prediction**: `scikit-learn`, `pandas`.
*   **RL**: A real implementation would use   `stable-baselines3` library .

## Deployment Considerations

### GCC Deployment
The GCC is a logically centralized component. It should be deployed as a highly-available service, for example:
*   A Kubernetes `Deployment` with 2+ replicas in a central management cluster or a public cloud region.
*   Exposed via a `LoadBalancer` service so LCAs can reach it over the network.
*   It does **not** need Kubernetes API access to the edge clusters directly; all communication is via the LCA APIs.

### LCA Deployment
Each LCA must be deployed *inside* the Kubernetes cluster it is intended to manage.
*   Deploy as a Kubernetes `Deployment` with 1 replica.
*   **Crucially**, it needs a `ServiceAccount` with RBAC permissions to:
    *   `GET`, `LIST`, `WATCH` nodes.
    *   `CREATE`, `GET`, `DELETE` pods.
*   It should be exposed via a `ClusterIP` service for internal communication, though its API could be exposed externally if needed.
*   The address of the central GCC must be provided to the LCA at startup (e.g., via an environment variable).

## How to Run (Simulation)

1.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

2.  **Start the Global Controller (GCC):**
    ```bash
    python main.py gcc --host 0.0.0.0 --port 8000
    ```

3.  **Start one or more Local Agents (LCA):**
    In separate terminals, start LCAs for different clusters.
    ```bash
    # LCA for 'edge-cluster-1'
    python main.py lca --cluster-id edge-cluster-1 --port 8001 --gcc-url http://localhost:8000

    # LCA for 'edge-cluster-2'
    python main.py lca --cluster-id edge-cluster-2 --port 8002 --gcc-url http://localhost:8000
    ```

4.  **Submit a Workflow:**
    Use a tool like `curl` or an HTTP client to post a workflow definition to the GCC.
    ```bash
    curl -X POST http://localhost:8000/submit_workflow -H "Content-Type: application/json" -d @sample_workflow.json
    ```