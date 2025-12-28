from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# --- Tool Schemas ---
class ToolBase(BaseModel):
    name: str
    description: str

class ToolCreate(ToolBase):
    pass

class ToolResponse(ToolBase):
    id: int
    
    class Config:
        from_attributes = True

class ToolUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

# --- Agent Schemas ---
class AgentBase(BaseModel):
    name: str
    role: str
    description: str

class AgentCreate(AgentBase):
    tool_ids: List[int] = []

class AgentResponse(AgentBase):
    id: int
    tools: List[ToolResponse] = []

    class Config:
        from_attributes = True

class AgentUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    description: Optional[str] = None
    tool_ids: Optional[List[int]] = None

# --- Execution Schema ---
class ExecutionRequest(BaseModel):
    prompt: str
    model: Optional[str] = "gpt-4o"

class ExecutionResponse(BaseModel):
    id: int
    agent_id: int
    prompt: str
    model: str
    response: str
    timestamp: datetime

    class Config:
        from_attributes = True
