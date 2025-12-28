from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
import models
import schemas
from database import engine, get_db
from auth import get_current_tenant
from utils import check_rate_limit, mock_llm_call

# Create tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# ---------------------------------------------------------
# TOOL ENDPOINTS
# ---------------------------------------------------------

@app.post("/tools/", response_model=schemas.ToolResponse)
def create_tool(tool: schemas.ToolCreate, db: Session = Depends(get_db), tenant_id: str = Depends(get_current_tenant)):
    """
    Create a new tool for the authenticated tenant.

    Parameters:
    - tool: `ToolCreate` schema containing the name and description.
    - db: Database session (injected via dependency).
    - tenant_id: ID of the tenant making the request (injected via API key).

    Returns:
    The created `Tool` model instance.
    """
    db_tool = models.Tool(name=tool.name, description=tool.description, tenant_id=tenant_id)
    db.add(db_tool)
    db.commit()
    db.refresh(db_tool)
    return db_tool

@app.get("/tools/", response_model=List[schemas.ToolResponse])
def read_tools(
    name: Optional[str] = None,
    agent_name: Optional[str] = None,
    db: Session = Depends(get_db), 
    tenant_id: str = Depends(get_current_tenant)):
    """
    Retrieve a list of tools belonging to the current tenant.
    
    Optional Filters:
    - **name**: Filter by tool name (partial match).
    - **agent_name**: Filter by the name of the agent using the tool (exact match).
    """
    query = db.query(models.Tool).filter(models.Tool.tenant_id == tenant_id)
    if name:
        query = query.filter(models.Tool.name.contains(name))
    if agent_name:
        query = query.join(models.Tool.agents).filter(models.Agent.name == agent_name)
    return query.all()

@app.put("/tools/{tool_id}", response_model=schemas.ToolResponse)
def update_tool(
    tool_id: int, 
    tool_update: schemas.ToolUpdate,
    db: Session = Depends(get_db), 
    tenant_id: str = Depends(get_current_tenant)
):
    """
    Update an existing tool for the authenticated tenant.

    Parameters:
    - tool_id: ID of the tool to update.
    - tool_update: `ToolUpdate` schema with optional fields to modify (e.g., `name`, `description`).
    - db: Database session (injected via dependency).
    - tenant_id: ID of the tenant making the request.

    Returns:
    The updated `Tool` model instance.

    Raises:
    - HTTPException(status_code=404): If the tool does not exist for the tenant.
    """
    db_tool = db.query(models.Tool).filter(models.Tool.id == tool_id, models.Tool.tenant_id == tenant_id).first()
    if not db_tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    
    if tool_update.name is not None:
        db_tool.name = tool_update.name
    if tool_update.description is not None:
        db_tool.description = tool_update.description
        
    db.commit()
    db.refresh(db_tool)
    return db_tool

@app.delete("/tools/{tool_id}")
def delete_tool(tool_id: int, db: Session = Depends(get_db), tenant_id: str = Depends(get_current_tenant)):
    """
    Delete a tool belonging to the authenticated tenant.

    Parameters:
    - tool_id: ID of the tool to delete.
    - db: Database session (injected via dependency).
    - tenant_id: ID of the tenant making the request.

    Returns:
    A dict with a deletion confirmation message.

    Raises:
    - HTTPException(status_code=404): If the tool is not found.
    """
    db_tool = db.query(models.Tool).filter(models.Tool.id == tool_id, models.Tool.tenant_id == tenant_id).first()
    if not db_tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    
    db.delete(db_tool)
    db.commit()
    return {"detail": "Tool deleted"}

# ---------------------------------------------------------
# AGENT ENDPOINTS
# ---------------------------------------------------------

@app.post("/agents/", response_model=schemas.AgentResponse)
def create_agent(agent: schemas.AgentCreate, db: Session = Depends(get_db), tenant_id: str = Depends(get_current_tenant)):
    """
    Create a new agent for the authenticated tenant, optionally attaching tools.

    Parameters:
    - agent: `AgentCreate` schema with agent attributes and optional `tool_ids`.
    - db: Database session (injected via dependency).
    - tenant_id: ID of the tenant making the request.

    Returns:
    The created `Agent` model instance.

    Raises:
    - HTTPException(status_code=400): If any of the provided `tool_ids` do not exist for the tenant.
    """
    tools = []
    if agent.tool_ids:
        tools = db.query(models.Tool).filter(models.Tool.id.in_(agent.tool_ids), models.Tool.tenant_id == tenant_id).all()
        if len(tools) != len(agent.tool_ids):
            raise HTTPException(status_code=400, detail="One or more tools not found")

    db_agent = models.Agent(
        name=agent.name, role=agent.role, description=agent.description, 
        tenant_id=tenant_id, tools=tools
    )
    db.add(db_agent)
    db.commit()
    db.refresh(db_agent)
    return db_agent

@app.get("/agents/", response_model=List[schemas.AgentResponse])
def read_agents(
    name: Optional[str] = None,
    role: Optional[str] = None,
    tool_name: Optional[str] = None,
    db: Session = Depends(get_db), 
    tenant_id: str = Depends(get_current_tenant)):
    """
    Retrieve a list of agents belonging to the current tenant.
    
    Optional Filters:
    - **name**: Filter by agent name (partial match).
    - **role**: Filter by agent role (partial match).
    - **tool_name**: Filter by the name of a tool the agent possesses (exact match).
    """
    query = db.query(models.Agent).filter(models.Agent.tenant_id == tenant_id)
    
    if name:
        query = query.filter(models.Agent.name.contains(name))

    if role:
        query = query.filter(models.Agent.role.contains(role))

    if tool_name:
        query = query.join(models.Agent.tools).filter(models.Tool.name == tool_name)
    
    return query.all()

@app.get("/agents/{agent_id}", response_model=schemas.AgentResponse)
def read_single_agent(agent_id: int, db: Session = Depends(get_db), tenant_id: str = Depends(get_current_tenant)):
    """
    Retrieve a single agent by ID for the authenticated tenant.

    Parameters:
    - agent_id: ID of the agent to retrieve.
    - db: Database session (injected via dependency).
    - tenant_id: ID of the tenant making the request.

    Returns:
    The `Agent` model instance.

    Raises:
    - HTTPException(status_code=404): If the agent is not found.
    """
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id, models.Agent.tenant_id == tenant_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent

@app.put("/agents/{agent_id}", response_model=schemas.AgentResponse)
def update_agent(
    agent_id: int, 
    agent_update: schemas.AgentUpdate,
    db: Session = Depends(get_db), 
    tenant_id: str = Depends(get_current_tenant)
):
    """
    Update an existing agent's attributes and tool assignments for the tenant.

    Parameters:
    - agent_id: ID of the agent to update.
    - agent_update: `AgentUpdate` schema with optional fields to modify (e.g., `name`, `role`, `description`, `tool_ids`).
    - db: Database session (injected via dependency).
    - tenant_id: ID of the tenant making the request.

    Returns:
    The updated `Agent` model instance.

    Raises:
    - HTTPException(status_code=404): If the agent does not exist.
    - HTTPException(status_code=400): If any provided `tool_ids` are invalid for the tenant.
    """
    db_agent = db.query(models.Agent).filter(models.Agent.id == agent_id, models.Agent.tenant_id == tenant_id).first()
    if not db_agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    if agent_update.name is not None:
        db_agent.name = agent_update.name
    if agent_update.role is not None:
        db_agent.role = agent_update.role
    if agent_update.description is not None:
        db_agent.description = agent_update.description
    
    if agent_update.tool_ids is not None:
        tools = db.query(models.Tool).filter(
            models.Tool.id.in_(agent_update.tool_ids),
            models.Tool.tenant_id == tenant_id
        ).all()
        
        # Verify we found all the tools requested
        if len(tools) != len(agent_update.tool_ids):
             raise HTTPException(status_code=400, detail="One or more tools not found")
             
        db_agent.tools = tools

    db.commit()
    db.refresh(db_agent)
    return db_agent

@app.delete("/agents/{agent_id}")
def delete_agent(agent_id: int, db: Session = Depends(get_db), tenant_id: str = Depends(get_current_tenant)):
    """
    Delete an agent belonging to the authenticated tenant.

    Parameters:
    - agent_id: ID of the agent to delete.
    - db: Database session (injected via dependency).
    - tenant_id: ID of the tenant making the request.

    Returns:
    A dict confirming deletion.

    Raises:
    - HTTPException(status_code=404): If the agent is not found.
    """
    db_agent = db.query(models.Agent).filter(models.Agent.id == agent_id, models.Agent.tenant_id == tenant_id).first()
    if not db_agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    db.delete(db_agent)
    db.commit()
    return {"detail": "Agent deleted"}

# ---------------------------------------------------------
# RUN & HISTORY ENDPOINTS
# ---------------------------------------------------------

SUPPORTED_MODELS = ["gpt-4o", "gemini-3"]

@app.post("/agents/{agent_id}/run")
def run_agent(
    agent_id: int, 
    execution_request: schemas.ExecutionRequest, 
    db: Session = Depends(get_db), 
    tenant_id: str = Depends(get_current_tenant)
):
    """
    Run an agent on a specific task.
    Validates that the requested model is supported.

    Parameters:
    - agent_id: ID of the agent to execute.
    - execution_request: `ExecutionRequest` schema containing prompt and model.
    - db: Database session (injected via dependency).
    - tenant_id: ID of the tenant making the request.

    Returns:
    A dict containing the agent name, the final prompt sent to the model, and the model response.

    Raises:
    - HTTPException(status_code=404): If the agent does not exist for the tenant.
    - HTTPException(status_code=429): If the tenant exceeds rate limits (raised by `check_rate_limit`).
    - HTTPException(status_code=400): If the requested model is not supported.
    """
    if execution_request.model not in SUPPORTED_MODELS:
        raise HTTPException(
            status_code=400, 
            detail=f"Model '{execution_request.model}' is not supported. Allowed models: {SUPPORTED_MODELS}"
        )

    check_rate_limit(tenant_id)

    agent = db.query(models.Agent).filter(models.Agent.id == agent_id, models.Agent.tenant_id == tenant_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    tool_list = ", ".join([t.name for t in agent.tools])
    final_prompt = (
        f"System: You are {agent.name}, a {agent.role}. {agent.description}. "
        f"You have access to these tools: [{tool_list}].\n"
        f"User Task: {execution_request.prompt}"
    )

    response_text = mock_llm_call(final_prompt, execution_request.model)

    execution = models.AgentExecution(
        tenant_id=tenant_id, agent_id=agent.id, prompt=final_prompt,
        model=execution_request.model, response=response_text
    )
    db.add(execution)
    db.commit()

    return {"agent": agent.name, "final_prompt": final_prompt, "response": response_text}

@app.get("/executions/", response_model=List[schemas.ExecutionResponse])
def read_history(skip: int = 0, limit: int = 10, db: Session = Depends(get_db), tenant_id: str = Depends(get_current_tenant)):
    """
    Return a paginated list of agent execution history for the tenant.

    Parameters:
    - skip: Number of records to skip (offset).
    - limit: Maximum number of records to return.
    - db: Database session (injected via dependency).
    - tenant_id: ID of the tenant making the request.

    Returns:
    A list of `AgentExecution` records matching the tenant.
    """
    return db.query(models.AgentExecution).filter(models.AgentExecution.tenant_id == tenant_id).offset(skip).limit(limit).all()
