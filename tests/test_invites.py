import pytest
from app.models import models
from app.auth import create_access_token

def test_preapproved_invite_creation_and_otp_verification(client, db_session):
    # 1. Create resident user
    resident = models.User(
        username="resident_103",
        hashed_password="hashed_pass",
        role=models.UserRole.RESIDENT,
        villa_number="103",
        villa_block="Block A",
        owner_name="Anil Kapoor"
    )
    db_session.add(resident)
    db_session.commit()
    db_session.refresh(resident)

    # 2. Resident generates pre-approved guest invite
    token = create_access_token({"sub": resident.username, "role": "RESIDENT"})
    headers = {"Authorization": f"Bearer {token}"}

    create_res = client.post("/api/v1/invites/create", json={
        "guest_name": "Vikram Seth (Party Guest)",
        "phone_number": "+91 9876543210",
        "duration_hours": 12
    }, headers=headers)

    assert create_res.status_code == 201
    invite_data = create_res.json()
    assert invite_data["guest_name"] == "Vikram Seth (Party Guest)"
    assert invite_data["status"] == "PENDING"
    otp_code = invite_data["otp_code"]
    assert len(otp_code) >= 4

    # 3. Guard verifies OTP pass code at gate
    verify_res = client.post("/api/v1/invites/verify-otp", json={
        "otp_code": otp_code,
        "gate_name": "North Gate"
    })

    assert verify_res.status_code == 200
    log_data = verify_res.json()
    assert "Vikram Seth" in log_data["visitor_name"]
    assert log_data["status"] == "APPROVED"
    assert log_data["gate_name"] == "North Gate"

    # 4. Attempting to reuse the same OTP code should fail
    reuse_res = client.post("/api/v1/invites/verify-otp", json={
        "otp_code": otp_code,
        "gate_name": "North Gate"
    })
    assert reuse_res.status_code == 400
