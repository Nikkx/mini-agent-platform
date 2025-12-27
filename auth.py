from fastapi import Header, HTTPException

API_KEYS = {
    "sk-key-123": "tenant-1",
    "sk-key-456": "tenant-2",
    "sk-key-admin": "admin-tenant"
}

def get_current_tenant(x_api_key: str = Header(...)):
    """
    Resolve the tenant ID associated with the provided API key header.

    Parameters:
    - x_api_key: API key provided in the `X-API-Key` header.

    Returns:
    The tenant ID string mapped to the API key.

    Raises:
    - HTTPException(status_code=401): If the API key is unrecognized.
    """
    if x_api_key not in API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return API_KEYS[x_api_key]
