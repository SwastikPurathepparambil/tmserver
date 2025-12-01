import os
import pytest
from fastapi.testclient import TestClient
from tmserver.api import app

os.environ.setdefault("DATABASE_NAME", "taylorMake_test")

@pytest.fixture
def client():
    with TestClient(app) as Client:
        yield Client

def test_if_healthy(client: TestClient):
    check = client.get("/health")
    assert check.status_code == 200
    assert check.json() == {"status": "healthy"}