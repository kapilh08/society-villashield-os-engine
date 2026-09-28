import pytest
from app.models import models

def test_society_event_creation_and_competition_setup(client, db_session):
    # 1. Register and login as ADMIN
    admin_res = client.post("/api/v1/auth/register", json={
        "username": "event_admin",
        "password": "adminpassword123",
        "role": "ADMIN"
    })
    assert admin_res.status_code == 201

    login_res = client.post("/api/v1/auth/login", json={
        "username": "event_admin",
        "password": "adminpassword123",
        "role": "ADMIN"
    })
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create Event: "Diwali Fest 2026"
    event_res = client.post("/api/v1/events/create", json={
        "title": "Diwali Fest 2026",
        "description": "Annual Society Grand Event",
        "event_date": "2026-11-01T18:00:00",
        "venue": "Club House Lawn"
    }, headers=headers)
    assert event_res.status_code == 201
    
    evt = db_session.query(models.Event).filter(models.Event.title == "Diwali Fest 2026").first()
    assert evt is not None
    assert evt.venue == "Club House Lawn"

    # 3. Add Competitions: "Badminton Singles" and "Kids Drawing"
    comp1_res = client.post(f"/api/v1/events/{evt.id}/competitions", json={
        "title": "Badminton Singles",
        "category": "OPEN",
        "coordinator_name": "Rajesh Kumar",
        "coordinator_phone": "+91 9876543210"
    }, headers=headers)
    assert comp1_res.status_code == 201
    comp1_id = comp1_res.json()["id"]

    comp2_res = client.post(f"/api/v1/events/{evt.id}/competitions", json={
        "title": "Kids Drawing Competition",
        "category": "KIDS",
        "coordinator_name": "Priya Sharma",
        "coordinator_phone": "+91 9123456789"
    }, headers=headers)
    assert comp2_res.status_code == 201
    comp2_id = comp2_res.json()["id"]

    # 4. Register Participants natively
    p1 = client.post("/api/v1/events/register-participant", json={
        "competition_id": comp1_id,
        "participant_name": "Aarav Gupta",
        "villa_number": "101",
        "category": "MALE",
        "phone_number": "+91 9998887771"
    }, headers=headers)
    assert p1.status_code == 201

    p2 = client.post("/api/v1/events/register-participant", json={
        "competition_id": comp1_id,
        "participant_name": "Rohan Verma",
        "villa_number": "102",
        "category": "MALE",
        "phone_number": "+91 9998887772"
    }, headers=headers)
    assert p2.status_code == 201

    p3 = client.post("/api/v1/events/register-participant", json={
        "competition_id": comp1_id,
        "participant_name": "Vikram Singh",
        "villa_number": "103",
        "category": "MALE",
        "phone_number": "+91 9998887773"
    }, headers=headers)
    assert p3.status_code == 201

    p1_id = p1.json()["id"]
    p2_id = p2.json()["id"]
    p3_id = p3.json()["id"]

    # 5. Query Category Filter
    filter_res = client.get(f"/api/v1/events/competitions/{comp1_id}/participants?category=MALE")
    assert filter_res.status_code == 200
    assert len(filter_res.json()) == 3

    # 6. Declare Winners (1st = p1 Aarav Villa 101, 2nd = p2 Rohan Villa 102, 3rd = p3 Vikram Villa 103)
    winner_res = client.post(f"/api/v1/events/competitions/{comp1_id}/winners", json={
        "winner_id": p1_id,
        "runner_up_1_id": p2_id,
        "runner_up_2_id": p3_id
    }, headers=headers)
    assert winner_res.status_code == 200
    assert winner_res.json()["winners"][0]["rank"] == "WINNER"
    assert winner_res.json()["winners"][0]["points"] == 10

    # 7. Check Live Leaderboard Aggregation
    lb_res = client.get(f"/api/v1/events/{evt.id}/leaderboard")
    assert lb_res.status_code == 200
    lb_data = lb_res.json()
    assert len(lb_data) == 3
    # First place should have 10 points
    assert lb_data[0]["points"] == 10
    assert lb_data[0]["villa_number"] == "101"

def test_registration_cutoff_enforcement(client, db_session):
    import datetime
    # 1. Register resident user
    client.post("/api/v1/auth/register", json={
        "username": "cutoff_resident",
        "password": "respassword123",
        "role": "RESIDENT"
    })
    login_res = client.post("/api/v1/auth/login", json={
        "username": "cutoff_resident",
        "password": "respassword123",
        "role": "RESIDENT"
    })
    res_token = login_res.json()["access_token"]
    res_headers = {"Authorization": f"Bearer {res_token}"}

    # 2. Create Event starting in 30 minutes (within 1-hour cutoff window)
    upcoming_time = datetime.datetime.utcnow() + datetime.timedelta(minutes=30)
    event = models.Event(
        title="Imminent Sports Event",
        description="Event starting very soon",
        event_date=upcoming_time,
        venue="Main Field"
    )
    db_session.add(event)
    db_session.commit()

    comp = models.EventCompetition(
        event_id=event.id,
        title="100m Sprint",
        category="OPEN"
    )
    db_session.add(comp)
    db_session.commit()

    # 3. Attempt resident registration (should fail with HTTP 400 cutoff error)
    reg_res = client.post("/api/v1/events/register-participant", json={
        "competition_id": comp.id,
        "participant_name": "Late Resident",
        "villa_number": "105"
    }, headers=res_headers)

    assert reg_res.status_code == 400
    assert "Registration closed" in reg_res.json()["detail"]
