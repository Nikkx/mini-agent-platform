import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import sessionmaker

import models  
from main import app
from database import Base, get_db
import schemas

# Setup specific Test Database (In-Memory SQLite)
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False},
    poolclass=StaticPool  # keep the in-memory db data alive across requests in the same test
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

# ---------------------------------------------------------
# TESTS
# ---------------------------------------------------------

auth_headers = {"x-api-key": "sk-key-123"}

def test_read_main():
    response = client.get("/docs")
    assert response.status_code == 200

def test_create_tool():
    response = client.post(
        "/tools/",
        json={"name": "Test Tool", "description": "A tool for testing"},
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Tool"
    assert "id" in data

def test_create_agent():
    # Create a tool
    tool_res = client.post(
        "/tools/",
        json={"name": "Search", "description": "Searching tool"},
        headers=auth_headers
    )
    tool_id = tool_res.json()["id"]

    # Create the agent with that tool
    response = client.post(
        "/agents/",
        json={
            "name": "Test Agent",
            "role": "Tester",
            "description": "Tests things",
            "tool_ids": [tool_id]
        },
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Agent"
    assert len(data["tools"]) == 1
    assert data["tools"][0]["name"] == "Search"

def test_run_agent():
    # Create tool and agent
    tool_res = client.post(
        "/tools/", 
        json={"name": "Calc", "description": "Calculator"}, 
        headers=auth_headers
    )
    tool_id = tool_res.json()["id"]

    agent_res = client.post(
        "/agents/",
        json={"name": "Math Bot", "role": "Math", "description": "Does math", "tool_ids": [tool_id]},
        headers=auth_headers
    )
    agent_id = agent_res.json()["id"]

    # Run the agent
    response = client.post(
        f"/agents/{agent_id}/run",
        json={"prompt": "Calculate 2+2", "model": "gpt-4o"},
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "System: You are Math Bot" in data["final_prompt"]

def test_auth_failure():
    # Test Missing Header
    # FastAPI automatically catches this and returns 422 (Unprocessable Entity)
    response = client.get("/tools/")
    assert response.status_code == 422

    # Test Invalid Key
    # Our custom logic catches this and returns 401 (Unauthorized)
    response = client.get("/tools/", headers={"x-api-key": "wrong-key"})
    assert response.status_code == 401
