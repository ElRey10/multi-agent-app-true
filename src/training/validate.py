import json
def validate_jsonl(file_path: str):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line_number, line in enumerate(f, 1):
                try:
                    json.loads(line)
                except json.JSONDecodeError as e:
                    print(f"Invalid JSON on line {line_number}: {e}")
                    print(f"Line content: {line}")
                    return False
        print("File is valid JSONL.")
        return True
    except Exception as e:
        print(f"Error reading file: {e}")
        return False

validate_jsonl("training_data.jsonl")