import time
from fastapi import HTTPException

# Simple in-memory storage for rate limiting
request_timestamps = {}

RATE_LIMIT = 5  # Max 5 requests
TIME_WINDOW = 60 # Per 60 seconds

def check_rate_limit(tenant_id: str):
    """
    Raises HTTP 429 if the tenant exceeds the rate limit.
    """
    now = time.time()
    # Get existing timestamps for this tenant
    timestamps = request_timestamps.get(tenant_id, [])
    
    # Filter out timestamps older than the window
    timestamps = [t for t in timestamps if now - t < TIME_WINDOW]
    
    if len(timestamps) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again later.")
    
    # Add current timestamp and save back
    timestamps.append(now)
    request_timestamps[tenant_id] = timestamps

def mock_llm_call(prompt: str, model: str) -> str:
    """
    Simulates an LLM response.
    """
    # Simulate processing time
    time.sleep(0.5) 
    
    responses = [
        "I have analyzed the data and found significant trends.",
        "Based on your request, I have executed the necessary tools.",
        "Here is the summary you requested based on the provided context.",
        "The calculation is complete. The result is within expected parameters."
    ]
    
    # Pick a response based on the length of the prompt
    index = len(prompt) % len(responses)
    return f"[{model} Response]: {responses[index]}"
