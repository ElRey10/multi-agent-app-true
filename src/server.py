import json
from typing import Literal
from fastapi import FastAPI, HTTPException
from langgraph.graph import StateGraph
from pydantic import BaseModel
from nodes import analyze_node, plan_node, verify_node, select_node, nodelessLLM
import uuid
import os
import signal
import fastapi
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development only
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],
)


# Define the AgentState model
class AgentState(BaseModel):
    problem: str
    problem_type: str = "general"
    config: dict = {}
    solutions: list = []
    error_details: list = []  # Structured errors
    confidence_score: float = 1.0
    iteration: int = 0
    error_history: list = []  # Track score trends
    domain_weights: dict = {}  # Domain-specific multipliers
    action: Literal["pending", "continue", "escalate", "complete"] = "pending"


# Store workflows and their states in memory
workflows = {}
workflow_states = {}  # Now stores AgentState instances


class InitRequest(BaseModel):
    problem: str


# def shutdown():
#     os.kill(os.getpid(), signal.SIGTERM)
#     return fastapi.Response(status_code=200, content="Server shutting down...")


# app.add_api_route("/shutdown", shutdown, methods=["GET"])


# Update the /init endpoint
@app.post("/init")
async def init_workflow(request: dict):
    body_dict = json.loads(request["body"])
    init_request = InitRequest(problem=body_dict["problem"])

    # Initialize the workflow state
    state = AgentState(
        problem=init_request.problem,
        config={"max_iterations": 5},  # Defaults
    )

    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("analyze", analyze_node)
    workflow.add_node("plan", plan_node)
    workflow.add_node("verify", verify_node)
    workflow.add_node("select", select_node)

    # Define edges
    workflow.add_edge("analyze", "plan")
    workflow.add_edge("plan", "verify")
    workflow.add_edge("verify", "select")
    workflow.add_conditional_edges(
        "select",
        lambda state: state.action,
    )
    workflow.set_entry_point("analyze")

    # Compile the workflow
    compiled_workflow = workflow.compile()

    workflow_id = str(uuid.uuid4())
    workflows[workflow_id] = compiled_workflow
    workflow_states[workflow_id] = state
    print("workflow_id", workflow_id)
    print("state", state)
    return {"workflow_id": workflow_id, "state": state.dict()}


@app.post("/step/{workflow_id}")
async def step_workflow(workflow_id: str):
    if workflow_id not in workflows:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Retrieve the compiled workflow and current state
    compiled_workflow = workflows[workflow_id]
    current_state = workflow_states[workflow_id]  # This is an AgentState instance

    # Execute the workflow with the current state
    result = compiled_workflow.invoke(current_state)

    # Update the state
    workflow_states[workflow_id] = result
    print("result", result)
    return {"workflow_id": workflow_id, "state": result}


@app.post("/basic-llm")
async def basic_llm(prompt: dict):
    body_dict = json.loads(prompt["body"])

    # Get the value of 'prompt'
    prompt_value = body_dict["prompt"]
    return nodelessLLM(prompt_value)
