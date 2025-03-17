from fastapi import FastAPI, HTTPException
from langgraph.graph import StateGraph
from pydantic import BaseModel
from nodes import analyze_node, plan_node, verify_node, select_node
import uuid

app = FastAPI()


# Define the AgentState model
class AgentState(BaseModel):
    problem: str
    config: dict = {}
    solutions: list = []
    errors: list = []
    iteration: int = 0


# Store workflows and their states in memory
workflows = {}
workflow_states = {}  # Now stores AgentState instances


class InitRequest(BaseModel):
    problem: str


@app.post("/init")
async def init_workflow(request: InitRequest):
    # Define the workflow
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
        lambda state: (
            "analyze" if state.iteration < 3 else "end"
        ),  # Use state.iteration (not state["iteration"])
    )
    workflow.set_entry_point("analyze")

    # Compile the workflow
    compiled_workflow = workflow.compile()

    # Initialize the workflow state
    state = AgentState(problem=request.problem)
    workflow_id = str(uuid.uuid4())
    workflows[workflow_id] = compiled_workflow
    workflow_states[workflow_id] = state  # Store the AgentState instance

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

    return {"workflow_id": workflow_id, "state": result.dict()}
