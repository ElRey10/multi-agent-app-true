import requests

# Initialize workflow
problem = "Schedule a 2-hour conference session with 15 speakers from 7 time zones, where: No speaker has back-to-back sessions At least 3 speakers per time zone must be in prime time (9AM-5PM local) Mandatory equipment: Projector (limited to 5 rooms)"
res = requests.post("http://localhost:8000/init", json={"problem": problem})

# Check if the response contains the expected keys
if res.status_code == 200:
    workflow_id = res.json().get("workflow_id")
    if workflow_id:
        print(f"Workflow initialized with ID: {workflow_id}")

        # Step through the workflow
        res = requests.post(f"http://localhost:8000/step/{workflow_id}")
        if res.status_code == 200:
            print("Workflow step result:", res.json())
        else:
            print("Failed to step workflow:", res.text)
    else:
        print("Error: 'workflow_id' not found in response:", res.json())
else:
    print("Failed to initialize workflow:", res.text)
