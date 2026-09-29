import os
import urllib.parse
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from app.models import models
from app.schemas import schemas
from app.database import get_db

router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])

def seed_role_faqs(db: Session):
    roles = ["VISITOR", "GUARD", "RESIDENT", "ADMIN"]
    
    faq_data = {
        "VISITOR": [
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
        ],
        "GUARD": [
            models.SocietyFAQ(
                role_target="GUARD",
                category="RULES",
                question_en="What are the general society rules & resident guidelines?",
                answer_en="🔑 *VillaShield General Society Guidelines:*\n1. Quiet hours observed 10:00 PM - 06:00 AM.\n2. All visitor vehicles must be parked in designated visitor parking slots.\n3. Renters/Tenants MUST submit ID proof and verified family documents to the Secretary prior to move-in.\n4. No loud music or commercial activities permitted inside residential villas.",
                question_hi="सामान्य सोसायटी नियम और निवासी दिशानिर्देश क्या हैं?",
                answer_hi="🔑 *विलाशील्ड सामान्य सोसायटी दिशानिर्देश:*\n1. रात 10:00 बजे से सुबह 06:00 बजे तक शांति बनाए रखें।\n2. सभी आगंतुक वाहन निर्धारित पार्किंग स्थल पर खड़े करें।\n3. किराएदारों को शिफ्टिंग से पहले सचिव को पहचान पत्र और पारिवारिक दस्तावेज जमा करना अनिवार्य है।\n4. रिहायशी विला में तेज संगीत या व्यावसायिक गतिविधियों की अनुमति नहीं है।"
            ),
            models.SocietyFAQ(
                role_target="GUARD",
                category="RULES",
                question_en="What are the main gate entry verification rules for visitors & cabs?",
                answer_en="🛡️ *Main Gate Entry Rules:*\n1. Every visitor, cab, or delivery vendor MUST be registered via the Guard Terminal.\n2. Automated broadcast approval request sent to destination villa.\n3. Do not grant entry until Villa Status shows 'APPROVED'.\n4. For pre-approved guest OTP passes, punch 4-digit code in Quick OTP entry box.",
                question_hi="आगंतुकों और कैब के लिए मुख्य द्वार प्रवेश नियम क्या हैं?",
                answer_hi="🛡️ *मुख्य द्वार प्रवेश नियम:*\n1. प्रत्येक आगंतुक, कैब या डिलीवरी विक्रेता को गार्ड टर्मिनल से पंजीकृत होना चाहिए।\n2. गंतव्य विला को स्वचालित अनुमोदन अनुरोध भेजा जाता है।\n3. जब तक विला स्थिति 'अनुमोदित' न दिखाए, प्रवेश न दें।\n4. पूर्व-अनुमोदित अतिथि ओटीपी पास के लिए, 4-अंकीय कोड दर्ज करें।"
            ),
            models.SocietyFAQ(
                role_target="GUARD",
                category="RULES",
                question_en="How do daily maids, cooks, and security guards punch shift attendance?",
                answer_en="⏰ *Staff Attendance Protocol:*\n1. Daily workers (maids, cooks, security guards) must use the Staff Attendance Terminal.\n2. Punch 4-digit secret PIN badge.\n3. Terminal clocks timestamp automatically on check-in and check-out.",
                question_hi="दैनिक कामवाली, रसोइया और सुरक्षा गार्ड हाजिरी कैसे लगाते हैं?",
                answer_hi="⏰ *कर्मचारी उपस्थिति नियम:*\n1. दैनिक कर्मचारी (कामवाली, रसोइया, सुरक्षा गार्ड) स्टाफ अटेंडेंस टर्मिनल का उपयोग करें।\n2. 4-अंकीय गुप्त पिन दर्ज करें।\n3. टर्मिनल चेक-इन और चेक-आउट के समय स्वचालित रूप से समय दर्ज करता है।"
            ),
            models.SocietyFAQ(
                role_target="GUARD",
                category="CONTACTS",
                question_en="Who to contact in case of emergency support or gate disruption?",
                answer_en="🚨 *Emergency Contacts Directory:*\n• 👮 Gate Supervisor: +91 9876500111\n• 👤 President (Mr. Vikramaditya): +91 9876543210\n• 👤 Secretary (Mrs. Ananya): +91 9123456789\n• 🚓 Local Police Station: 112 / 022-28001122\n• 🚒 Fire Station Control Room: 101",
                question_hi="आपातकालीन सहायता या गेट समस्या के स्थिति में किससे संपर्क करें?",
                answer_hi="🚨 *आपातकालीन संपर्क निर्देशिका:*\n• 👮 गेट पर्यवेक्षक: +91 9876500111\n• 👤 अध्यक्ष (श्री विक्रमादित्य): +91 9876543210\n• 👤 सचिव (श्रीमती अनन्या): +91 9123456789\n• 🚓 स्थानीय पुलिस स्टेशन: 112\n• 🚒 फायर स्टेशन कंट्रोल रूम: 101"
            )
        ],
        "RESIDENT": [
            models.SocietyFAQ(
                role_target="RESIDENT",
                category="RULES",
                question_en="How do I pre-approve visitors and generate OTP passes?",
                answer_en="📲 *Pre-Approving Guests:*\n1. Navigate to Resident Portal -> Pre-Approve Guests.\n2. Enter Guest Name & Expected Date.\n3. Copy 4-digit OTP pass and share directly with guest on WhatsApp.",
                question_hi="मैं मेहमानों को पूर्व-अनुमोदित कैसे करूं और ओटीपी पास कैसे बनाऊं?",
                answer_hi="📲 *अतिथि पूर्व-अनुमोदन नियम:*\n1. रेजिडेंट पोर्टल पर जाएं -> प्री-अप्रूव गेस्ट चुनें।\n2. अतिथि नाम और तिथि दर्ज करें।\n3. 4-अंकीय ओटीपी पास कॉपी करें और व्हाट्सएप पर शेयर करें।"
            ),
            models.SocietyFAQ(
                role_target="RESIDENT",
                category="FINANCE",
                question_en="How to pay maintenance bills & verify payment via WhatsApp OCR?",
                answer_en="💵 *Maintenance Payment & Receipt Confirmation:*\n1. Pay via UPI/GPay to Society QR Code.\n2. Upload payment screenshot in Resident Chat Assistant.\n3. Automated OCR parses payment amount & UTR reference and posts confirmation to WhatsApp Group.",
                question_hi="रखरखाव बिल का भुगतान कैसे करें और व्हाट्सएप OCR से सत्यापन कैसे करें?",
                answer_hi="💵 *रखरखाव भुगतान और रसीद पुष्टि:*\n1. सोसायटी क्यूआर कोड पर यूपीआई/जीपे द्वारा भुगतान करें।\n2. रेजिडेंट चैट असिस्टेंट में स्क्रीनशॉट अपलोड करें।\n3. स्वचालित ओसीआर राशि और यूटीआर पार्स करके व्हाट्सएप ग्रुप में पुष्टि भेजता है।"
            ),
            models.SocietyFAQ(
                role_target="RESIDENT",
                category="CONTACTS",
                question_en="What are the Main Gate Guardhouse & Clubhouse contact numbers?",
                answer_en="📞 *Important Internal Contacts:*\n• 🛡️ Main Security Gatehouse: Ext 101 / +91 9876500111\n• 🏊 Clubhouse & Facility Manager: Ext 104 / +91 9876500222\n• 🛠️ Plumbing & Electrician Desk: Ext 105",
                question_hi="मुख्य गेट गार्डहाउस और क्लब हाउस के संपर्क नंबर क्या हैं?",
                answer_hi="📞 *महत्वपूर्ण आंतरिक संपर्क:*\n• 🛡️ मुख्य गेट सुरक्षा: एक्सटेंशन 101 / +91 9876500111\n• 🏊 क्लब हाउस मैनेजर: एक्सटेंशन 104 / +91 9876500222\n• 🛠️ प्लंबिंग और इलेक्ट्रीशियन: एक्सटेंशन 105"
            )
        ],
        "ADMIN": [
            models.SocietyFAQ(
                role_target="ADMIN",
                category="RULES",
                question_en="How do I access visitor analytics & staff attendance logs?",
                answer_en="📊 *Admin Command Tower:* Access `/admin/dashboard` for live metric counters, visitor log filters, and daily staff shift attendance exports.",
                question_hi="मैं आगंतुक विश्लेषिकी और कर्मचारी उपस्थिति लॉग कैसे देखूं?",
                answer_hi="📊 *एडमिन कमांड टॉवर:* लाइव मीट्रिक काउंटर, आगंतुक लॉग फ़िल्टर और दैनिक उपस्थिति निर्यात के लिए `/admin/dashboard` पर जाएं।"
            ),
            models.SocietyFAQ(
                role_target="ADMIN",
                category="RULES",
                question_en="How to handle Gate Emergency SOS alerts?",
                answer_en="🚨 *Emergency Alerts:* Check the Active Gate Emergency Alerts table on `/admin/dashboard`. Use the single-click WhatsApp share button to alert society residents.",
                question_hi="गेट आपातकालीन एसओएस अलर्ट को कैसे संभालें?",
                answer_hi="🚨 *आपातकालीन चेतावनी:* `/admin/dashboard` पर सक्रिय आपातकालीन अलर्ट तालिका जांचें। निवासियों को सचेत करने के लिए व्हाट्सएप शेयर बटन का उपयोग करें।"
            )
        ]
    }

    for role in roles:
        if role in faq_data:
            for faq in faq_data[role]:
                exists = db.query(models.SocietyFAQ).filter(
                    models.SocietyFAQ.role_target == role,
                    models.SocietyFAQ.question_en == faq.question_en
                ).first()
                if not exists:
                    db.add(faq)
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
    seed_role_faqs(db)
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

@router.post("/guard-sos")
def trigger_guard_sos(payload: schemas.GuardSOSCreate, db: Session = Depends(get_db)):
    alert = models.EmergencyAlert(
        guard_username=payload.guard_username or "guard1",
        gate_name=payload.gate_name or "Main Gate",
        alert_type=payload.alert_type or "INTRUDER_ALERT",
        notes=payload.notes,
        status="ACTIVE_DISTRESS"
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)

    # Format WhatsApp SOS Distress Broadcast Message
    sos_message = (
        f"🚨 *VILLASHIELD GATE EMERGENCY DISTRESS ALERT*\n\n"
        f"📍 *Location:* {alert.gate_name}\n"
        f"⚠️ *Alert Type:* {alert.alert_type.replace('_', ' ')}\n"
        f"👤 *Reporting Guard:* {alert.guard_username}\n"
        f"📝 *Details:* {alert.notes or 'Immediate assistance required at main gate.'}\n"
        f"⏰ *Timestamp:* {alert.created_at.strftime('%Y-%m-%d %H:%M:%S') if alert.created_at else 'Just now'}\n\n"
        f"📢 *ACTION REQUIRED:* Gate supervisor & surrounding guards report immediately to {alert.gate_name}!"
    )
    encoded_text = urllib.parse.quote(sos_message)
    wa_link = f"https://wa.me/?text={encoded_text}"

    return {
        "status": "success",
        "alert_id": alert.id,
        "message": f"🚨 Emergency SOS distress alert recorded for {alert.gate_name}!",
        "whatsapp_message": sos_message,
        "whatsapp_link": wa_link
    }

@router.get("/admin/emergency-alerts")
def get_admin_emergency_alerts(db: Session = Depends(get_db)):
    alerts = db.query(models.EmergencyAlert).order_by(models.EmergencyAlert.created_at.desc()).all()
    results = []
    for a in alerts:
        sos_message = (
            f"🚨 *VILLASHIELD GATE EMERGENCY DISTRESS ALERT*\n\n"
            f"📍 *Location:* {a.gate_name}\n"
            f"⚠️ *Alert Type:* {a.alert_type.replace('_', ' ')}\n"
            f"👤 *Reporting Guard:* {a.guard_username}\n"
            f"📝 *Details:* {a.notes or 'Immediate assistance required at main gate.'}\n"
            f"⏰ *Timestamp:* {a.created_at.strftime('%Y-%m-%d %H:%M:%S') if a.created_at else ''}\n\n"
            f"📢 *ACTION REQUIRED:* Gate supervisor & surrounding guards report immediately to {a.gate_name}!"
        )
        encoded_text = urllib.parse.quote(sos_message)
        wa_link = f"https://wa.me/?text={encoded_text}"

        results.append({
            "id": a.id,
            "guard_username": a.guard_username,
            "gate_name": a.gate_name,
            "alert_type": a.alert_type,
            "notes": a.notes,
            "status": a.status,
            "created_at": a.created_at.strftime("%Y-%m-%d %H:%M:%S") if a.created_at else "",
            "whatsapp_message": sos_message,
            "whatsapp_link": wa_link
        })
    return results
