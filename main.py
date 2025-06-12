# main.py
import argparse
import uvicorn
import asyncio
from fastapi import FastAPI, Request
from gcc.controller import GlobalController
from lca.agent import LocalAgent
from utils.models import Workflow, MicroDAG

def run_gcc(args):
    app = FastAPI()
    gcc = GlobalController()

    @app.post("/register_lca")
    async def register(request: Request):
        data = await request.json()
        return gcc.register_lca(data['cluster_id'], data['lca_url'], data['state'])

    @app.post("/submit_workflow")
    async def submit_workflow(workflow: Workflow):
        # Run dispatch in the background so the API call returns immediately
        asyncio.create_task(gcc.dispatch_workflow(workflow))
        return {"status": "workflow accepted and being processed"}

    uvicorn.run(app, host=args.host, port=args.port)

def run_lca(args):
    app = FastAPI()
    lca = LocalAgent(cluster_id=args.cluster_id, gcc_url=args.gcc_url)

    @app.post("/schedule_subgraph")
    async def schedule_subgraph(dag: MicroDAG):
        return await lca.schedule_subgraph(dag)

    @app.on_event("startup")
    async def startup_event():
        # Start the LCA's background tasks
        asyncio.create_task(lca.run())

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Cerebrum Components")
    subparsers = parser.add_subparsers(dest="component", required=True)

    # GCC Parser
    parser_gcc = subparsers.add_parser("gcc", help="Run the Global Cerebrum Controller")
    parser_gcc.add_argument("--host", type=str, default="127.0.0.1")
    parser_gcc.add_argument("--port", type=int, default=8000)
    parser_gcc.set_defaults(func=run_gcc)

    # LCA Parser
    parser_lca = subparsers.add_parser("lca", help="Run a Local Cerebrum Agent")
    parser_lca.add_argument("--cluster-id", type=str, required=True, help="Unique ID for the cluster")
    parser_lca.add_argument("--gcc-url", type=str, required=True, help="URL of the central GCC")
    parser_lca.add_argument("--host", type=str, default="127.0.0.1")
    parser_lca.add_argument("--port", type=int, default=8001)
    parser_lca.set_defaults(func=run_lca)

    args = parser.parse_args()
    args.func(args)