from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
import os
import json


from services.scoring import ErrorScorer
from services.threshold import ThresholdCalculator


# from server import AgentState
from dotenv import load_dotenv

load_dotenv()


scorer = ErrorScorer()
thresholder = ThresholdCalculator()


# Define ProblemConfig
class ProblemConfig(BaseModel):
    constraints: list[str]
    algorithms: list[str]
    max_iterations: int


# Initialize AzureChatOpenAI
llm = AzureChatOpenAI(
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    azure_deployment=os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"],
    openai_api_version=os.environ["AZURE_OPENAI_API_VERSION"],
    openai_api_key=os.environ["AZURE_OPENAI_API_KEY"],
)


# Node 1: Problem Analyzer
def analyze_node(state):  # State is an AgentState instance
    response = llm.invoke(
        [
            HumanMessage(
                content=f"""
        Analyze this problem for constraints and required algorithms:
        {state.problem}  
        
        Output JSON with:
        - constraints: list of key requirements
        - algorithms: list from [ToT, BoN, RS]
        - max_iterations: integer

        Send JSON Only
        """
            )
        ]
    )
    print("response2", response)
    cleaned_content = response.content.strip("```json\n").strip("```").strip()

    try:
        config = ProblemConfig.parse_raw(cleaned_content)
        # Print out the parsed content
        print(config.constraints)
        print(config.algorithms)
        print(config.max_iterations)
    except Exception as e:
        print(f"Error parsing JSON: {e}")
    return {"config": config.dict()}


# Node 2: Planner
def plan_node(state):
    algo = state.config["algorithms"][state.iteration % len(state.config["algorithms"])]
    response = llm.invoke(
        [
            HumanMessage(
                content=f"""
        Generate solution using {algo} for:
        {state.problem}
        Constraints: {state.config['constraints']}
        """
            )
        ]
    )
    return {"solutions": state.solutions + [response.content]}


# Node 3: Verifier
def verify_node(state):
    verification_prompt = f"""
    Analyze solution for MULTI-DIMENSIONAL errors (JSON output):
    Problem: {state.problem[:1000]}
    Solution: {state.solutions[-1][:2000]}
    Constraints: {state.config['constraints'][:5]}
    
    Output schema:
    {{
        "errors": [{{"type": "time_conflict", "severity": "critical", "description": "..."}}],
        "confidence": 0.85,
        "domain_classification": "scheduling|logistics|engineering|other"
    }}
    Send JSON Only
    """

    try:
        response = llm.invoke([HumanMessage(content=verification_prompt)])
        print("response3", response)
        cleaned_content = response.content.strip("```json\n").strip("```").strip()
        result = json.loads(cleaned_content)

        return {
            "error_details": result["errors"],
            "confidence_score": result["confidence"],
            "problem_type": result["domain_classification"],
        }

    except Exception as e:
        return {
            "error_details": [{"type": "system_error", "severity": "critical"}],
            "confidence_score": 0.0,
        }


# Node 4: Algorithm Selector
def select_node(state):
    # Calculate metrics
    current_score = scorer.calculate(state)
    threshold = thresholder.dynamic_threshold(state)
    trend = thresholder._calculate_trend(state.error_history + [current_score])

    decision_matrix = {
        "continue_conditions": [
            current_score < threshold,
            trend < 0.1,  # Negative trend
            state.iteration < state.config.get("max_iterations", 5),
        ],
        "escalate_conditions": [
            any(e["severity"] == "critical" for e in state.error_details),
            current_score < 0.3,
        ],
    }

    if all(decision_matrix["continue_conditions"]):
        return {
            "action": "continue",
            "iteration": state.iteration + 1,
            "error_history": state.error_history + [current_score],
        }
    elif any(decision_matrix["escalate_conditions"]):
        return {"action": "escalate", "required": ["senior_approval"]}
    else:
        return {"action": "complete", "final_score": current_score}


def nodelessLLM(prompt: str):
    if prompt == "":
        return {"response": "Please provide a prompt"}
    response = llm.invoke([HumanMessage(content=prompt)])
    print("response", response)
    return {"response": response.content}
