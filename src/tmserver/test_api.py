import os
import pytest
from fastapi.testclient import TestClient
from tmserver.api import app
import tmserver.api as api_module
from tmserver.db import db 
os.environ.setdefault("DATABASE_NAME", "taylorMake_test")

@pytest.fixture
def client():
    with TestClient(app) as Client:
        yield Client

def test_if_healthy(client: TestClient):
    check = client.get("/health")
    assert check.status_code == 200
    assert check.json() == {"status": "healthy"}


@pytest.fixture
def my_google_token(monkeypatch):
    async def fake_verify_google_token(token: str):
        return {
            "google_sub": "myGoogleSub1010",
            "email": "test@icloud.com"
        }
    monkeypatch.setattr(api_module, "verify_google_token", fake_verify_google_token)

    return fake_verify_google_token

def test_google_login_creates_user_and_sets_cookie(client: TestClient, my_google_token):
    check = client.post("/auth/google", json={"token": "some_tok"})
    assert check.status_code == 200
    test = check.json()
    assert "user" in text
    assert text["user"]["email"] == "test@icloud.com"
    assert "id" in body["user"]
    assert "access_token" in check.cookies
    assert check.cookies.get("access_token") is not None