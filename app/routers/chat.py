import os
import urllib.parse
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from app.models import models
from app.schemas import schemas
from app.database import get_db

router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])

def seed_visitor_faqs(db: Session):
    existing = db.query(models.SocietyFAQ).filter(models.SocietyFAQ.role_target == "VISITOR").first()
    if not existing:
        faqs = [
            models.SocietyFAQ(
                role_target="VISITOR",
                category="RULES",
                question_en="What are the society rules & guidelines?",
                answer_en="🔑 *VillaShield Society Guidelines:*\n1. Quiet hours observed 10:00 PM - 06:00 AM.\n2. All visitor vehicles must be parked in designated visitor slots.\n3. Tenants/Renters MUST submit ID proof and family verification documents to the Society Secretary prior to move-in.",
                question_hi="सोसायटी के नियम और दिशानिर्देश क्या हैं?",
                answer_hi="🔑 *विलाशील्ड सोसायटी दिशानिर्देश:*\n1. रात 10:00 बजे से सुबह 06:00 बजे तक शांति बनाए रखें।\n2. सभी अतिथि वाहन केवल निर्धारित पार्किंग स्थल पर खड़े करें।\n3. किराएदारों को शिफ्टिंग से पहले सचिव को पहचान पत्र और पारिवारिक सत्यापन दस्तावेज जमा करना अनिवार्य है।"
            ),
            models.SocietyFAQ(
                role_target="VISITOR",
                category="FINANCE",
                question_en="What is the monthly maintenance amount?",
                answer_en="💵 *Monthly Maintenance Rates:*\n• 2BHK Villas: ₹2,500 / month\n• 3BHK Villas: ₹3,500 / month\n• Executive Villas: ₹5,000 / month\nDue on 5th of every month. Includes 24/7 Gate Guard Security, CCTV Monitoring, Clubhouse, and Landscaping.",
                question_hi="मासिक रखरखाव शुल्क कितना है?",
                answer_hi="💵 *मासिक रखरखाव दरें:*\n• 2BHK विला: ₹2,500 / माह\n• 3BHK विला: ₹3,500 / माह\n• एग्जीक्यूटिव विला: ₹5,000 / माह\nहर महीने की 5 तारीख तक देय। इसमें 24/7 गेट सुरक्षा, सीसीटीवी और क्लब हाउस शामिल है।"
            ),
            models.SocietyFAQ(
                role_target="VISITOR",
                category="CONTACTS",
                question_en="Who is the Society President & Secretary?",
                answer_en="👔 *Society Management Committee:*\n• 👤 President: Mr. Vikramaditya Sharma (+91 9876543210)\n• 👤 Secretary: Mrs. Ananya Deshmukh (+91 9123456789)\n• 👤 Treasurer: Mr. Ramesh Patel (+91 9988776655)",
                question_hi="सोसायटी अध्यक्ष और सचिव कौन हैं?",
                answer_hi="👔 *सोसायटी प्रबंध समिति:*\n• 👤 अध्यक्ष: श्री विक्रमादित्य शर्मा (+91 9876543210)\n• 👤 सचिव: श्रीमती अनन्या देशमुख (+91 9123456789)\n• 👤 कोषाध्यक्ष: श्री रमेश पटेल (+91 9988776655)"
            )
        ]
        db.add_all(faqs)
        db.commit()

@router.get("/config")
def get_chat_config():
    return {
        "enabled_visitor": os.getenv("CHAT_ENABLED_VISITOR", "true").lower() == "true",
        "enabled_guard": os.getenv("CHAT_ENABLED_GUARD", "true").lower() == "true",
        "enabled_resident": os.getenv("CHAT_ENABLED_RESIDENT", "true").lower() == "true",
        "enabled_admin": os.getenv("CHAT_ENABLED_ADMIN", "true").lower() == "true",
        "default_language": os.getenv("CHAT_DEFAULT_LANGUAGE", "EN")
    }

@router.get("/faqs")
def get_role_faqs(role: Optional[str] = "VISITOR", db: Session = Depends(get_db)):
    seed_visitor_faqs(db)
    role_upper = (role or "VISITOR").upper()
    faqs = db.query(models.SocietyFAQ).filter(
        models.SocietyFAQ.role_target == role_upper,
        models.SocietyFAQ.is_active == True
    ).all()
    return [
        {
            "id": f.id,
            "category": f.category,
            "question_en": f.question_en,
            "answer_en": f.answer_en,
            "question_hi": f.question_hi,
            "answer_hi": f.answer_hi
        } for f in faqs
    ]

@router.get("/inquiry")
def get_property_inquiries_info():
    return {
        "status": "info",
        "message": "VillaShield Property Inquiry Endpoint. Please submit property inquiry forms using HTTP POST or via the Chat Assistant UI on the homepage.",
        "usage": "POST /api/v1/chat/inquiry"
    }

@router.post("/inquiry", status_code=status.HTTP_201_CREATED)
def submit_property_inquiry(payload: schemas.PropertyInquiryCreate, db: Session = Depends(get_db)):
    inquiry = models.PropertyInquiry(
        visitor_name=payload.visitor_name,
        phone_number=payload.phone_number,
        inquiry_type=payload.inquiry_type or "RENT",
        bhk_preference=payload.bhk_preference or "3BHK",
        family_status="VERIFIED_FAMILY",
        status="PENDING_REVIEW",
        notes=payload.notes
    )
    db.add(inquiry)
    db.commit()
    db.refresh(inquiry)

    return {
        "status": "success",
        "inquiry_id": inquiry.id,
        "message": "Property inquiry recorded successfully and submitted to Society Administration for review."
    }

@router.get("/admin/inquiries")
def get_admin_property_inquiries(db: Session = Depends(get_db)):
    inquiries = db.query(models.PropertyInquiry).order_by(models.PropertyInquiry.created_at.desc()).all()
    results = []
    for inq in inquiries:
        wa_message = (
            f"🏡 *NEW VILLASHIELD PROPERTY INQUIRY*\n\n"
            f"👤 *Name:* {inq.visitor_name}\n"
            f"📞 *Phone:* {inq.phone_number}\n"
            f"📌 *Requirement:* Looking for {inq.inquiry_type} ({inq.bhk_preference})\n"
            f"👨‍👩‍👧 *Family Status:* Verified Family Occupancy\n"
            f"📝 *Notes:* {inq.notes or 'None'}\n\n"
            f"⚠️ *Notice:* Renter/Buyer must submit genuine family background verification documents to the Society Secretary prior to move-in."
        )
        encoded_text = urllib.parse.quote(wa_message)
        wa_link = f"https://wa.me/?text={encoded_text}"

        results.append({
            "id": inq.id,
            "visitor_name": inq.visitor_name,
            "phone_number": inq.phone_number,
            "inquiry_type": inq.inquiry_type,
            "bhk_preference": inq.bhk_preference,
            "family_status": inq.family_status,
            "status": inq.status,
            "notes": inq.notes,
            "created_at": inq.created_at.strftime("%Y-%m-%d %H:%M:%S") if inq.created_at else "",
            "whatsapp_message": wa_message,
            "whatsapp_link": wa_link
        })
    return results

@router.post("/admin/inquiries/{inquiry_id}/mark-posted")
def mark_inquiry_posted(inquiry_id: int, db: Session = Depends(get_db)):
    inq = db.query(models.PropertyInquiry).filter(models.PropertyInquiry.id == inquiry_id).first()
    if not inq:
        raise HTTPException(status_code=404, detail="Inquiry not found")
    inq.status = "POSTED_TO_WHATSAPP"
    db.commit()
    return {"status": "success", "message": "Inquiry marked as posted to WhatsApp"}
