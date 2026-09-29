import pytest
from app.models import models

def test_chat_config_and_visitor_faqs(client, db_session):
    # 1. Fetch Chat configuration
    config_res = client.get("/api/v1/chat/config")
    assert config_res.status_code == 200
    assert config_res.json()["enabled_visitor"] is True
    assert config_res.json()["default_language"] == "EN"

    # 2. Fetch Visitor FAQs (triggers auto-seeding)
    faqs_res = client.get("/api/v1/chat/faqs?role=VISITOR")
    assert faqs_res.status_code == 200
    faqs = faqs_res.json()
    assert len(faqs) >= 3

    # Check English and Hindi text in first FAQ
    faq1 = faqs[0]
    assert "question_en" in faq1
    assert "question_hi" in faq1
    assert "answer_en" in faq1
    assert "answer_hi" in faq1

def test_property_inquiry_submission(client, db_session):
    # Submit Villa Rent Inquiry
    inquiry_res = client.post("/api/v1/chat/inquiry", json={
        "visitor_name": "Siddharth Malhotra",
        "phone_number": "+91 9876500000",
        "inquiry_type": "RENT",
        "bhk_preference": "3BHK",
        "notes": "Looking for immediate move-in with family"
    })

    assert inquiry_res.status_code == 201
    data = inquiry_res.json()
    assert data["status"] == "success"
    assert "inquiry_id" in data
    assert "submitted to Society Administration" in data["message"]

    # Verify database persistence & PENDING_REVIEW status
    inq_db = db_session.query(models.PropertyInquiry).filter(
        models.PropertyInquiry.id == data["inquiry_id"]
    ).first()
    assert inq_db is not None
    assert inq_db.visitor_name == "Siddharth Malhotra"
    assert inq_db.inquiry_type == "RENT"
    assert inq_db.status == "PENDING_REVIEW"

def test_admin_property_inquiries_roster_and_mark_posted(client, db_session):
    # 0. Submit property inquiry
    client.post("/api/v1/chat/inquiry", json={
        "visitor_name": "Siddharth Malhotra",
        "phone_number": "+91 9876500000",
        "inquiry_type": "RENT",
        "bhk_preference": "3BHK",
        "notes": "Looking for immediate move-in with family"
    })

    # 1. Fetch Admin inquiries roster
    res = client.get("/api/v1/chat/admin/inquiries")
    assert res.status_code == 200
    inquiries = res.json()
    assert len(inquiries) >= 1

    inq = inquiries[0]
    assert "whatsapp_link" in inq
    assert "Siddharth Malhotra" in inq["whatsapp_message"]

    # 2. Mark inquiry as posted to WhatsApp
    inq_id = inq["id"]
    post_res = client.post(f"/api/v1/chat/admin/inquiries/{inq_id}/mark-posted")
    assert post_res.status_code == 200

    # 3. Re-verify updated status in DB
    updated_inq = db_session.query(models.PropertyInquiry).filter(models.PropertyInquiry.id == inq_id).first()
    assert updated_inq.status == "POSTED_TO_WHATSAPP"

def test_guard_faqs_retrieval(client, db_session):
    # Fetch Guard FAQs (triggers auto-seeding for GUARD role)
    res = client.get("/api/v1/chat/faqs?role=GUARD")
    assert res.status_code == 200
    faqs = res.json()
    assert len(faqs) >= 3

    # Verify Guard-specific topics
    categories = [f["category"] for f in faqs]
    assert "RULES" in categories
    assert "CONTACTS" in categories
    assert any("gate entry" in f["question_en"].lower() for f in faqs)

def test_guard_emergency_sos_dispatch(client, db_session):
    # Trigger Guard Emergency SOS Distress Alert
    sos_res = client.post("/api/v1/chat/guard-sos", json={
        "gate_name": "Main Gate",
        "alert_type": "INTRUDER_ALERT",
        "guard_username": "guard1",
        "notes": "Unregistered person refusing entry at main barrier"
    })

    assert sos_res.status_code == 200
    data = sos_res.json()
    assert data["status"] == "success"
    assert "alert_id" in data
    assert "whatsapp_link" in data
    assert "INTRUDER ALERT" in data["whatsapp_message"]

    # Verify DB persistence
    alert_db = db_session.query(models.EmergencyAlert).filter(
        models.EmergencyAlert.id == data["alert_id"]
    ).first()
    assert alert_db is not None
    assert alert_db.gate_name == "Main Gate"
    assert alert_db.alert_type == "INTRUDER_ALERT"
    assert alert_db.status == "ACTIVE_DISTRESS"

def test_admin_emergency_alerts_roster(client, db_session):
    # 0. Trigger Guard SOS alert
    client.post("/api/v1/chat/guard-sos", json={
        "gate_name": "North Gate",
        "alert_type": "MEDICAL_EMERGENCY",
        "guard_username": "guard2",
        "notes": "Medical assistance needed at north entry"
    })

    # 1. Fetch Admin emergency alerts roster
    res = client.get("/api/v1/chat/admin/emergency-alerts")
    assert res.status_code == 200
    alerts = res.json()
    assert len(alerts) >= 1

    alert = alerts[0]
    assert alert["gate_name"] == "North Gate"
    assert alert["alert_type"] == "MEDICAL_EMERGENCY"
    assert "whatsapp_link" in alert

def test_resident_and_admin_faqs_retrieval(client, db_session):
    # Fetch Resident FAQs
    res_faqs = client.get("/api/v1/chat/faqs?role=RESIDENT")
    assert res_faqs.status_code == 200
    res_data = res_faqs.json()
    assert len(res_data) >= 3
    assert any("pre-approve" in f["question_en"].lower() for f in res_data)

    # Fetch Admin FAQs
    adm_faqs = client.get("/api/v1/chat/faqs?role=ADMIN")
    assert adm_faqs.status_code == 200
    adm_data = adm_faqs.json()
    assert len(adm_data) >= 2
    assert any("visitor analytics" in f["question_en"].lower() for f in adm_data)
