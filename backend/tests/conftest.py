import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture(scope="session")
def client():
    """
    Shared FastAPI test client fixture.
    Runs all tests directly in-memory at lightning speed.
    """
    with TestClient(app) as c:
        yield c
