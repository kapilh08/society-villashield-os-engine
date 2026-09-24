import pytest
from app.models import models
from app.auth import create_access_token

def test_visitor_registration_and_resident_approval(client, db_session):
    # 1. Create resident & guard users in DB
    resident = models.User(
        username="resident_102",
        hashed_password="hashed_pass",
        role=models.UserRole.RESIDENT,
        villa_number="102",
        villa_block="Block B",
        owner_name="Sita Verma"
    )
    guard = models.User(
        username="guard_main",
        hashed_password="hashed_pass",
        role=models.UserRole.GUARD
    )
    db_session.add(resident)
    db_session.add(guard)
    db_session.commit()
    db_session.refresh(resident)
    db_session.refresh(guard)

    guard_token = create_access_token({"sub": guard.username, "role": "GUARD"})
    guard_headers = {"Authorization": f"Bearer {guard_token}"}

    resident_token = create_access_token({"sub": resident.username, "role": "RESIDENT"})
    resident_headers = {"Authorization": f"Bearer {resident_token}"}

    # 2. Guard registers arriving visitor at gate
    reg_response = client.post("/api/v1/visitors/register", json={
        "villa_id": resident.id,
        "visitor_name": "Delivery Guy (Amazon)",
        "phone_number": "+91 9999988888",
        "vehicle_number": "KA-01-AB-1234",
        "purpose": "Delivery",
        "gate_name": "Main Gate"
    }, headers=guard_headers)
    assert reg_response.status_code == 201 or reg_response.status_code == 200
    log_data = reg_response.json()
    assert log_data["visitor_name"] == "Delivery Guy (Amazon)"
    assert log_data["status"] == "PENDING"
    assert log_data["gate_name"] == "Main Gate"
    log_id = log_data["id"]

    # 3. Resident approves the entry request via PATCH endpoint
    action_response = client.patch(f"/api/v1/visitors/{log_id}/action", json={
        "status": "APPROVED"
    }, headers=resident_headers)
    assert action_response.status_code == 200
    updated_data = action_response.json()
    assert updated_data["status"] == "APPROVED"
