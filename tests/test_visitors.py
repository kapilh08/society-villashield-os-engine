import pytest
from app.models import models

def test_visitor_registration_and_resident_approval(client, db_session):
    # 1. Create resident user in DB
    resident = models.User(
        username="resident_102",
        hashed_password="hashed_pass",
        role=models.UserRole.RESIDENT,
        villa_number="102",
        villa_block="Block B",
        owner_name="Sita Verma"
    )
    db_session.add(resident)
    db_session.commit()
    db_session.refresh(resident)

    # 2. Register arriving visitor at gate
    reg_response = client.post("/api/v1/visitors/register", json={
        "villa_id": resident.id,
        "visitor_name": "Delivery Guy (Amazon)",
        "phone_number": "+91 9999988888",
        "vehicle_number": "KA-01-AB-1234",
        "purpose": "Delivery",
        "gate_name": "Main Gate"
    })
    assert reg_response.status_code == 200
    log_data = reg_response.json()
    assert log_data["visitor_name"] == "Delivery Guy (Amazon)"
    assert log_data["status"] == "PENDING"
    assert log_data["gate_name"] == "Main Gate"
    log_id = log_data["id"]

    # 3. Resident approves the entry request
    action_response = client.post(f"/api/v1/visitors/{log_id}/action", json={
        "status": "APPROVED"
    })
    assert action_response.status_code == 200
    updated_data = action_response.json()
    assert updated_data["status"] == "APPROVED"
