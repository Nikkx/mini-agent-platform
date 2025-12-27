from fastapi import Header, HTTPException

API_KEYS = {
    "sk-key-123": "tenant-1",
    "sk-key-456": "tenant-2",
    "sk-key-admin": "admin-tenant"
}

def get_current_tenant(x_api_key: str = Header(...)):
    if x_api_key not in API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return API_KEYS[x_api_key]
