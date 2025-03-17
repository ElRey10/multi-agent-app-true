from openai import AzureOpenAI

client = AzureOpenAI(
    api_key="d1218947452f40b0a940674fb38fbcd6",
    api_version="2025-01-01-preview",
    azure_endpoint="https://modus-dev-open-ai.openai.azure.com/",
)

# Upload the training data file
try:
    with open("training_data.jsonl", "rb") as file:
        response = client.files.create(file=file, purpose="fine-tune")
    print(f"File uploaded successfully. File ID: {response.id}")
except Exception as e:
    print(f"Error uploading file: {e}")
