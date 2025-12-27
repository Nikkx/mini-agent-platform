from sqlalchemy import Column, Integer, String, ForeignKey, Table, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

# Association table for Many-to-Many relationship between Agents and Tools
agent_tools_association = Table(
    'agent_tools', Base.metadata,
    Column('agent_id', Integer, ForeignKey('agents.id')),
    Column('tool_id', Integer, ForeignKey('tools.id'))
)

class Agent(Base):
    __tablename__ = "agents"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, index=True)
    name = Column(String, index=True)
    role = Column(String)
    description = Column(String)
    
    tools = relationship("Tool", secondary=agent_tools_association, back_populates="agents")

class Tool(Base):
    __tablename__ = "tools"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, index=True)
    name = Column(String, index=True)
    description = Column(String)
    
    agents = relationship("Agent", secondary=agent_tools_association, back_populates="tools")

class AgentExecution(Base):
    __tablename__ = "agent_executions"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, index=True)
    agent_id = Column(Integer, ForeignKey('agents.id'))
    prompt = Column(String)
    model = Column(String)
    response = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
