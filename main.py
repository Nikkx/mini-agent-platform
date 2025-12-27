from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import models
import schemas
from database import engine, get_db
from auth import get_current_tenant
from utils import check_rate_limit, mock_llm_call  # <--- New Import!

# Create tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# ---------------------------------------------------------
# TOOL ENDPOINTS
# ---------------------------------------------------------

@app.post("/tools/", response_model=schemas.ToolResponse)
def create_tool(tool: schemas.ToolCreate, db: Session = Depends(get_db), tenant_id: str = Depends(get_current_tenant)):
    db_tool = models.Tool(name=tool.name, description=tool.description, tenant_id=tenant_id)
    db.add(db_tool)
    db.commit()
    db.refresh(db_tool)
    return db_tool

@app.get("/tools/", response_model=List[schemas.ToolResponse])
def read_tools(db: Session = Depends(get_db), tenant_id: str = Depends(get_current_tenant)):
    return db.query(models.Tool).filter(models.Tool.tenant_id == tenant_id).all()

@app.put("/tools/{tool_id}", response_model=schemas.ToolResponse)
def update_tool(tool_id: int, tool_update: schemas.ToolCreate, db: Session = Depends(get_db), tenant_id: str = Depends(get_current_tenant)):
    db_tool = db.query(models.Tool).filter(models.Tool.id == tool_id, models.Tool.tenant_id == tenant_id).first()
    if not db_tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    
    db_tool.name = tool_update.name
    db_tool.description = tool_update.description
    db.commit()
    db.refresh(db_tool)
    return db_tool

@app.delete("/tools/{tool_id}")
def delete_tool(tool_id: int, db: Session = Depends(get_db), tenant_id: str = Depends(get_current_tenant)):
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
def read_agents(db: Session = Depends(get_db), tenant_id: str = Depends(get_current_tenant)):
    return db.query(models.Agent).filter(models.Agent.tenant_id == tenant_id).all()

@app.get("/agents/{agent_id}", response_model=schemas.AgentResponse)
def read_single_agent(agent_id: int, db: Session = Depends(get_db), tenant_id: str = Depends(get_current_tenant)):
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id, models.Agent.tenant_id == tenant_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent

@app.put("/agents/{agent_id}", response_model=schemas.AgentResponse)
def update_agent(agent_id: int, agent_update: schemas.AgentCreate, db: Session = Depends(get_db), 
                 tenant_id: str = Depends(get_current_tenant)):
    db_agent = db.query(models.Agent).filter(models.Agent.id == agent_id, models.Agent.tenant_id == tenant_id).first()
    if not db_agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    db_agent.name = agent_update.name
    db_agent.role = agent_update.role
    db_agent.description = agent_update.description
    
    if agent_update.tool_ids is not None:
        tools = db.query(models.Tool).filter(models.Tool.id.in_(agent_update.tool_ids), models.Tool.tenant_id == tenant_id).all()
        if len(tools) != len(agent_update.tool_ids):
             raise HTTPException(status_code=400, detail="One or more tools not found")
        db_agent.tools = tools

    db.commit()
    db.refresh(db_agent)
    return db_agent

@app.delete("/agents/{agent_id}")
def delete_agent(agent_id: int, db: Session = Depends(get_db), tenant_id: str = Depends(get_current_tenant)):
    db_agent = db.query(models.Agent).filter(models.Agent.id == agent_id, models.Agent.tenant_id == tenant_id).first()
    if not db_agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    db.delete(db_agent)
    db.commit()
    return {"detail": "Agent deleted"}

# ---------------------------------------------------------
# RUN & HISTORY ENDPOINTS
# ---------------------------------------------------------

@app.post("/agents/{agent_id}/run")
def run_agent(agent_id: int, execution_request: schemas.ExecutionRequest, 
              db: Session = Depends(get_db), tenant_id: str = Depends(get_current_tenant)):
    # Use helper from utils.py
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
    return db.query(models.AgentExecution).filter(models.AgentExecution.tenant_id == tenant_id).offset(skip).limit(limit).all()
