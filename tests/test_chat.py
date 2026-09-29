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
