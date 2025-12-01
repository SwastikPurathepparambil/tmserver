import os
import pytest
from fastapi.testclient import TestClient
from tmserver.api import app
import tmserver.api as api_module
from tmserver.db import db 
os.environ.setdefault("DATABASE_NAME", "taylorMake_test")
os.environ.setdefault("MONGO_URI", "mongodb://localhost:8000") 
@pytest.fixture
def client():
    with TestClient(app) as Client:
        yield
    

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

def test_get_current_user_requires_auth(client: TestClient):
    check = client.get("/auth/me")
    assert check.status_code == 404
    assert check.json()["detail"] == "Not Found"

def test_get_current_user_after_login(client: TestClient, mock_google_token):
    client.post("/auth/google", json={"token": "some_token"})
    check = client.get("/auth/me")
    assert check.status_code == 200
    text = resp.json()
    assert text["email"] == "test@icloud.com"
    assert "created_at" in text
    assert "last_login_at" in text

def test_create_resume(client: TestClient):
    check = client.post("/resumes", json={
        "target_role": "SWE",
        "content": {"summary": "this is my test content"}
    })
    assert check.status_code == 401


def test_get_one_resume(client: TestClient, mock_google_token):
    client.post("/auth/google", json={"token": "some_token"})
    check = client.post("/resumes", json={
        "target_role": "SWE",
        "content": {"summary": "SOme SWE Job for google"}
    })
    resume_id = check.json()["id"]
    finalcheck = client.get(f"/resumes/{resume_id}")
    assert finalcheck.status_code == 200
    assert finalcheck.json()["id"] == resume_id


def test_resume_not_valid(client: TestClient, mock_google_token):
    client.post("/auth/google", json={"token": "fake-token"})
    check = client.get("/resumes/notvalidobjectsorry")
    assert check.status_code == 400

