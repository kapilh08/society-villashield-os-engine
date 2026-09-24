import pytest
from app.models import models
from app.auth import get_password_hash

def test_staff_onboarding_and_pin_clocking(client, db_session):
    # 1. Onboard domestic staff member in DB
    pin_hash = get_password_hash("1234")
    staff = models.DomesticStaff(
        full_name="Lakshmi Devi (Maid)",
        role="Housekeeping",
        passcode_hash=pin_hash,
        is_active=True
    )
    db_session.add(staff)
    db_session.commit()

    # 2. Clock-in using 4-digit PIN
    clockin_res = client.post("/api/v1/staff/clock-io", json={"passcode": "1234"})
    assert clockin_res.status_code == 200
    data = clockin_res.json()
    assert data["action"] == "CHECK_IN"
    assert data["staff_name"] == "Lakshmi Devi (Maid)"

    # 3. Clock-out using the same 4-digit PIN
    clockout_res = client.post("/api/v1/staff/clock-io", json={"passcode": "1234"})
    assert clockout_res.status_code == 200
    data_out = clockout_res.json()
    assert data_out["action"] == "CHECK_OUT"
