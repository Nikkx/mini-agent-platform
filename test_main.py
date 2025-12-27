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

def test_filter_tools():
    t1 = client.post("/tools/", json={"name": "Hammer", "description": "A hammer"}, headers=auth_headers).json()
    t2 = client.post("/tools/", json={"name": "Drill", "description": "A drill"}, headers=auth_headers).json()
    
    client.post(
        "/agents/",
        json={"name": "Builder", "role": "Worker", "description": "Builds", "tool_ids": [t1["id"]]},
        headers=auth_headers
    )

    res_name = client.get("/tools/?name=Ham", headers=auth_headers)
    assert len(res_name.json()) == 1
    assert res_name.json()[0]["name"] == "Hammer"

    res_agent = client.get("/tools/?agent_name=Builder", headers=auth_headers)
    data = res_agent.json()
    assert len(data) == 1
    assert data[0]["name"] == "Hammer"

def test_filter_agents():
    t_spy = client.post("/tools/", json={"name": "Walther PPK", "description": "Gun"}, headers=auth_headers).json()
    t_tech = client.post("/tools/", json={"name": "Laptop", "description": "Macbook"}, headers=auth_headers).json()

    client.post("/agents/", json={"name": "James Bond", "role": "Spy", "description": "007", "tool_ids": [t_spy["id"]]}, headers=auth_headers)
    client.post("/agents/", json={"name": "Q", "role": "Quartermaster", "description": "Tech support", "tool_ids": [t_tech["id"]]}, headers=auth_headers)

    res = client.get("/agents/?name=Bond", headers=auth_headers)
    assert len(res.json()) == 1
    assert res.json()[0]["name"] == "James Bond"

    res = client.get("/agents/?role=Quarter", headers=auth_headers)
    assert len(res.json()) == 1
    assert res.json()[0]["name"] == "Q"

    res = client.get("/agents/?tool_name=Walther PPK", headers=auth_headers)
    assert len(res.json()) == 1
    assert res.json()[0]["name"] == "James Bond"

def test_run_agent_invalid_model():
    t_res = client.post("/tools/", json={"name": "X", "description": "X"}, headers=auth_headers).json()
    a_res = client.post("/agents/", json={"name": "Test", "role": "X", "description": "X", "tool_ids": [t_res["id"]]}, headers=auth_headers).json()
    agent_id = a_res["id"]

    response = client.post(
        f"/agents/{agent_id}/run",
        json={"prompt": "Hello", "model": "invalid-model-name"},
        headers=auth_headers
    )

    assert response.status_code == 400
    assert "not supported" in response.json()["detail"]