from modusagent import MigrationState, init_workflow, output_code
from utils import (
    MigrationAction,
    handle_errors,
    get_human_feedback,
    load_state,
    needs_human_approval,
    save_state,
    validate_migration,
)
from IPython.display import Image, display
import json

state_file = "data/workflow_state.json"

initial_state = load_state(state_file)

skip_clone = True if initial_state else False

if not initial_state:
    workflow, initial_state = init_workflow(
        repo_url_v1="https://github.com/trimble-oss/modus-web-components.git",
        repo_url_v2="https://{token}@github.com/Trimble-Construction/modus-wc-2.0.git",
        target_repo="https://github.com/ChaitanyaKNaidu/GitHub-Issues-Extraction.git",
        skip_repo_clone=False,
    )
else:
    workflow, _ = init_workflow(
        repo_url_v1="https://github.com/trimble-oss/modus-web-components.git",
        repo_url_v2="https://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@github.com/Trimble-Construction/modus-wc-2.0.git",
        target_repo="https://github.com/ChaitanyaKNaidu/GitHub-Issues-Extraction.git",
        skip_repo_clone=True,
    )

state = initial_state

if skip_clone:
    # Directly run the output_code node using the current state.
    print("Skipping repo clone; directly running output_code with existing training data.")
    #state = output_code(state)
    result = workflow.invoke(state)


    try:
        display(Image(workflow.get_graph().draw_mermaid_png()))
    except Exception:
        # This requires some extra dependencies and is optional
        pass
else:
    while state.action != MigrationAction.COMPLETE:
        print("Processing workflow step...")
        try:
            result = workflow.invoke(state)
            
            if not isinstance(result, (dict, MigrationState)):
                raise ValueError(f"Unexpected result type: {type(result)}")
            if isinstance(result, dict):
                state = MigrationState(**{**state.dict(), **result})
            else:
                state = result
            if state.verification_errors:
                state = handle_errors(state)
            if needs_human_approval(state):
                state = get_human_feedback(state)
            save_state(state, state_file)
        except Exception as e:
            print(f"Workflow error: {e}")
            state = state.copy(update={"action": MigrationAction.ESCALATE})
            save_state(state, state_file)
            break

if state.action == MigrationAction.COMPLETE:
        print("Migration successful!")
        print("Modified files:\n", json.dumps(state.modified_code, indent=2))
else:
    print(f"Migration halted with status: {state.action}")
