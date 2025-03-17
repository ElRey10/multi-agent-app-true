from diskcache import Cache
from hashlib import sha256
from langchain_openai import AzureChatOpenAI
from dotenv import load_dotenv
import os
load_dotenv()

# Initialize cache
cache = Cache("./llm_cache")

llm = AzureChatOpenAI(
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    azure_deployment=os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"],
    openai_api_version=os.environ["AZURE_OPENAI_API_VERSION"],
    openai_api_key=os.environ["AZURE_OPENAI_API_KEY"],
)

output_llm = AzureChatOpenAI(
    azure_endpoint=os.environ["AZURE_OPENAI_OUTPUT_MODEL_ENDPOINT"],
    azure_deployment=os.environ["AZURE_OPENAI_OUTPUT_MODEL_DEPLOYMENT_NAME"],
    openai_api_version=os.environ["AZURE_OPENAI_OUTPUT_MODEL_API_VERSION"],
    openai_api_key=os.environ["AZURE_OPENAI_OUTPUT_MODEL_API_KEY"],
)

def cached_llm_invoke(prompt: str):
    # Generate a unique key for the prompt
    prompt_hash = sha256(prompt.encode()).hexdigest()

    # Check if the response is already cached
    if prompt_hash in cache:
        print("Using cached response")
        return cache[prompt_hash]

    # Call the LLM if the response is not cached
    print("Calling LLM API")
    response = llm.invoke(prompt)
    cache[prompt_hash] = response
    return response

def outputllm(prompt: str):
    print("Calling output LLM API")

    response = output_llm.invoke(prompt)
    return response