import pytest
from app.models import models

def test_user_registration_and_login(client, db_session):
    # 1. Register a new resident user
    response = client.post("/api/v1/auth/register", json={
        "username": "resident_101",
        "password": "securepassword123",
        "role": "RESIDENT",
        "villa_number": "101",
        "villa_block": "Block A",
        "owner_name": "Rajesh Kumar"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "resident_101"
    assert data["role"] == "RESIDENT"

    # 2. Login to receive JWT token
    login_response = client.post("/api/v1/auth/login", json={
        "username": "resident_101",
        "password": "securepassword123",
        "role": "RESIDENT"
    })
    assert login_response.status_code == 200
    token_data = login_response.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
