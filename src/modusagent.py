import json
import re
from typing import Dict, List
from langgraph.graph import StateGraph
from cache import outputllm
from pydantic import BaseModel
import os
from git import Repo, GitCommandError
from pathlib import Path
from cache import cached_llm_invoke
import shutil
import stat
from utils import (
    MigrationAction,
    MigrationState,
    parse_constraints,
    get_all_files_from_structure,
    read_file,
    parse_plan,
    parse_rules,
    parse_migration_rules,
    apply_migration_rules,
    extract_component_details,
    save_state,
)


# Initialize Workflow
def init_workflow(repo_url_v1, repo_url_v2, target_repo, skip_repo_clone):
    print("init_workflow called")
    workflow = StateGraph(MigrationState)

    # Add Nodes
    workflow.add_node("ingest_repos", ingest_repos)
    workflow.add_node("analyze_structure", analyze_structure)
    workflow.add_node("identify_constraints", identify_constraints)
    workflow.add_node("generate_plan", generate_plan)
    workflow.add_node("verify_changes", verify_changes)
    workflow.add_node("test_with_code", test_with_code)
    workflow.add_node("output_code", output_code)

    # Define Edges
    workflow.add_edge("ingest_repos", "analyze_structure")
    workflow.add_edge("analyze_structure", "identify_constraints")
    workflow.add_edge("identify_constraints", "generate_plan")
    workflow.add_edge("generate_plan", "verify_changes")
    workflow.add_edge("verify_changes", "test_with_code")
    workflow.add_edge("test_with_code", "output_code")

    workflow.set_entry_point("ingest_repos")
    if skip_repo_clone:
        repo_structure = {"v1": {}, "v2": {}, "target": {}}
    else:
        repo_structure = {
            "v1": get_repo_structure(repo_url_v1),
            "v2": get_repo_structure(repo_url_v2),
            "target": get_repo_structure(target_repo),
        }
    initial_state = MigrationState(
        repo_structure=repo_structure,
    )
    return workflow.compile(), initial_state


def handle_remove_error(func, path, exc_info):
    print("handle_remove_error called")
    os.chmod(path, stat.S_IWRITE)
    func(path)


def get_repo_structure(repo_url):
    print("get_repo_structure called")
    repo_name = os.path.basename(repo_url)
    repo_path = Path("/tmp") / repo_name  # Absolute path

    if repo_path.exists():
        print("Repository already exists. Pulling latest changes...")
        # Optionally pull changes here.
    else:
        try:
            print(f"Cloning repository from {repo_url} to {repo_path}")
            Repo.clone_from(repo_url, repo_path)
        except GitCommandError as e:
            print(f"Error cloning repository {repo_url}: {e}")
            raise e

    structure = {}
    for root, dirs, files in os.walk(repo_path):
        rel_path = os.path.relpath(root, repo_path)
        structure[rel_path] = {
            "files": files,
            "components": identify_components(os.path.join(root)),
        }
    return {"root": str(repo_path), "structure": structure}


def identify_components(directory):
    print("identify_components called")
    components = []
    try:
        for f in os.listdir(directory):
            if f.endswith(".tsx"):
                file_path = os.path.join(directory, f)
                with open(file_path, "r", encoding="utf-8") as file:
                    content = file.read()
                    if "@Component" in content:
                        print(f"Found component: {f}")
                        # Strip formatting characters if any (e.g., markdown formatting)
                        components.append(f.strip())
    except Exception as e:
        print(f"Error reading directory {directory}: {e}")
    return components


# Define Nodes
def ingest_repos(state: MigrationState) -> MigrationState:
    print("ingest_repos called")
    return state


def analyze_structure(state: MigrationState) -> MigrationState:
    print("analyze_structure called")

    # Extract component details
    v1_components = extract_component_details(state.repo_structure["v1"], version="v1")
    v2_components = extract_component_details(state.repo_structure["v2"], version="v2")

    # Immediate validation
    if not v1_components:
        raise ValueError("No Modus 1.0 components found!")
    if not v2_components:
        raise ValueError("No Modus 2.0 components found!")

    print("\nDEBUG: Extracted v1_components:", v1_components)
    print("\nDEBUG: Extracted v2_components:", v2_components)

    # Generate component mapping using LLM
    analysis_prompt = f"""
    Analyze these component specifications to create precise migration rules:

    Modus 1.0 Components:
    {json.dumps(v1_components, indent=2)}

    Modus 2.0 Components:
    {json.dumps(v2_components, indent=2)}
    
    Generate migration rules with:
    1. Exact component tag replacements
    2. Attribute/property mappings for COMMON PROPS ONLY
    3. Required attributes for 2.0 components
    4. Mapping standard HTML tags to Modus 2.0 components (if applicable)
    5. Use the component docs as the main context

    DO IT FOR ALL THE COMPONENTS FOUND IN 1.0 AND 2.0.
    Example Format:
    {{"modus-button": {{"new_tag": "modus-wc-button", "props": {{"buttonStyle": "variant"}}}}}}
    STRICTLY STICK TO THE FORMAT ABOVE.
    """

    try:
        response = cached_llm_invoke(analysis_prompt)
        mapping = parse_migration_rules(response.content)
    except Exception as e:
        print(f"Analysis error: {e}")
        mapping = {"migrations": {}, "examples": {}}

    # ✅ Return updated state with all necessary fields
    return MigrationState(
        repo_structure=state.repo_structure,
        v1_components=v1_components,
        v2_components=v2_components,
        component_map=mapping.get("migrations", {}),
    )


def identify_constraints(state: MigrationState) -> Dict:
    print("identify_constraints called")
    constraint_prompt = f"""
    Based on the following component mapping:
    {json.dumps(state.component_map, indent=2)}

    Identify migration constraints for moving from Modus 1.0 to 2.0.
    Focus on:
      - Breaking API changes,
      - Styling or structural differences,
      - Compatibility issues.
      
    Output the constraints as a JSON object in the following format:
    {{
      "constraints": [
        {{
          "type": "breaking",
          "description": "Component X requires code adjustments in 2.0.",
          "components": ["ComponentX"]
        }}
      ]
    }}
    """
    # Immediate validation
    if not state.v1_components:
        raise ValueError("No Modus 1.0 components found!")
    if not state.v2_components:
        raise ValueError("No Modus 2.0 components found!")
    constraints = cached_llm_invoke(constraint_prompt)
    cleaned_content = constraints.content.strip("```json\n").strip("```").strip()
    try:
        parsed = json.loads(cleaned_content)
    except json.JSONDecodeError:
        parsed = {"constraints": []}
    return {"constraints": parsed.get("constraints", [])}


def generate_plan(state: MigrationState) -> Dict:
    print("generate_plan called")
    plan_prompt = f"""
    Target Project Structure:
    {json.dumps(state.repo_structure['target'], indent=2)}

    Migration Constraints:
    {json.dumps(state.constraints, indent=2)}

    Component Mapping:
    {json.dumps(state.component_map, indent=2)}

    Using the above information and the documentation provided, generate a detailed, step-by-step migration plan for updating Modus 1.0 code to Modus 2.0. This should include:
      1. Replacing outdated component tags with their new equivalents.
      2. Mapping and transforming properties (only for properties present in 1.0).
      3. Applying any required structural or event updates.
      4. Mapping standard HTML tags (e.g., <textarea>) to their Modus 2.0 equivalents (e.g., <modus-wc-textarea>), if applicable.

    **Important:** Do NOT include any instructions for installing dependencies or environment setup.

    Provide your plan as a JSON object in the following format:
    {{
      "migration_plan": [
        "Step 1: Detailed description of the first migration step.",
        "Step 2: Detailed description of the next migration step.",
        ...
      ]
    }}
    """
    plan = cached_llm_invoke(plan_prompt)
    plan_content = plan.content if hasattr(plan, "content") else str(plan)
    print("Plan content received:", plan_content)
    parsed_plan = parse_plan(plan_content)
    print("Parsed Plan:", parsed_plan)
    return {"migration_plan": parsed_plan}


def verify_changes(state: MigrationState) -> Dict:
    print("verify_changes called")
    # Provide few-shot examples for verification training.
    verification_examples = """
    Example 1:
    Original: <modus-button buttonStyle="primary">Click</modus-button>
    Expected: <modus-wc-button variant="primary" aria-label="Click">Click</modus-wc-button>

    Example 2:
    Original: <textarea></textarea>
    Expected: <modus-wc-textarea></modus-wc-textarea>
    """
    verification_prompt = f"""
    Based on these migration requirements:
    {json.dumps(state.migration_plan, indent=2)}
    
    And these constraints:
    {json.dumps(state.constraints, indent=2)}
    
    And the following verification examples:
    {verification_examples}
    
    Generate detailed verification rules as a JSON list in the following format:

    [
      {{
         "rule": "Description of rule",
         "status": "pending",
         "details": [
            "Detail 1",
            "Detail 2"
         ]
      }},
      ...
    ]

    Ensure your output is ONLY a JSON list of rule objects.
    
    """
    rules_output = cached_llm_invoke(verification_prompt)
    print("Verification Rules Output:", rules_output.content)
    parsed_rules = parse_rules(rules_output.content)
    if not isinstance(parsed_rules, list):
        parsed_rules = [parsed_rules]
    print("Verification Rules:", parsed_rules)
    return {"verification_rules": parsed_rules}


def test_with_code(state: MigrationState) -> MigrationState:
    print("test_with_code called")
    modus_1_code = """
    <modus-button buttonStyle="primary">Click</modus-button>
    <textarea></textarea>
    """
    expected_output = """
    <modus-wc-button variant="primary" aria-label="Click">Click</modus-wc-button>
    <modus-wc-textarea></modus-wc-textarea>
    """
    # Test the migration rules on the provided code
    prompt = f"""
    Test the migration rules on the following Modus 1.0 code:
    {modus_1_code}
    Give the expected Modus 2.0 code as output only.
    """
    test_output = cached_llm_invoke(prompt)
    cleaned_content = test_output.content.strip("```").strip()
    print("Test Output:", cleaned_content)
    if cleaned_content == expected_output:
        print("Test passed successfully!")
    else:
        print("Test failed.")
    return state


def output_code(state: MigrationState) -> MigrationState:
    print("output_code called - Migrating files...")
    
    # Retrieve target repository information
    target_repo = state.repo_structure.get("target", {})
    target_root = target_repo.get("root", None)
    if not target_root or not os.path.isdir(target_root):
        print(f"Error: target_root is invalid: {target_root}")
        return state

    target_structure = target_repo.get("structure", {})
    # Get only files with allowed extensions (e.g., .html, .tsx)
    all_files = get_all_files_from_structure(
        target_structure, target_root, extensions=[".html", ".tsx"]
    )
    total_files = len(all_files)
    print(f"Found {total_files} valid files for migration.")

    for idx, file_path in enumerate(all_files):
        print(f"Processing file {idx + 1}/{total_files}: {file_path}")
        try:
            original = read_file(file_path)
            # Apply your automated migration transformation (if applicable)
            migrated = apply_migration_rules(original, state)
            print("Automated migration attempt (first 500 chars):")
            print(migrated[:500])

            # Build a detailed prompt with explicit few-shot example for the alert component.
            prompt = f"""
Understand the Modus Components of Modus 1.0 Components and Modus 2.0 Components: 

Modus 1.0 Components:
----------------------------
{json.dumps(state.v1_components, indent=2)}

Modus 2.0 Components:
----------------------------
{json.dumps(state.v2_components, indent=2)}

Follow the Migration Plan given below and apply it to the original code:

Migration Plan:
----------------------------
{json.dumps(state.migration_plan, indent=2)}

**Example Transformation:**
Convert the following Modus 1.0 alert:
    <modus-alert message="Info alert with action button" button-text="Action"></modus-alert>
into the following Modus 2.0 alert:
    <modus-wc-alert alert-description="You have 3 new messages." alert-title="New message!" dismissable="false" role="status" variant="info">
      <modus-wc-button aria-label="View messages" color="secondary" slot="button">View Messages</modus-wc-button>
    </modus-wc-alert>

Now, using the above context and example, transform the file below.

Original Code:
----------------------------
{original}

After Migration verify it with the verification rules:

Verification Rules:
----------------------------
{json.dumps(state.verification_rules, indent=2)}

Verify and update the code accordingly then return the final migrated code.
IMPORTANT: Ensure that the migration is accurate and dont change any logic or functionality and Just Give the Migrated Code alone.
            """

            response = outputllm(prompt)
            final = response.content.replace("```html", "").replace("```", "").strip()
            
            print("Final migrated code (first 500 chars):")
            print(final)

            state.modified_code[str(file_path)] = final

            # Write the final migrated code back to disk.
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(final)
            print(f"File {file_path} migrated successfully.")
        except Exception as e:
            print(f"Failed to migrate {file_path}: {e}")
            state.modified_code[str(file_path)] = original

    # Debug: Print before/after transformation for the last processed file.
    if total_files > 0:
        print(f"Before transformation (last file, first 500 chars):\n{original[:500]}")
        print(
            f"After transformation (last file, first 500 chars):\n{state.modified_code[str(file_path)]}"
        )

    state.action = MigrationAction.COMPLETE
    print("Migration completed successfully!", state.modified_code)
    return state
