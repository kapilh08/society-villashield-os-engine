from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import Optional
import datetime
import asyncio
import io
import csv

from app.database import engine, Base, get_db, SessionLocal
from app.routers import auth, visitors, staff, admin, invites, events, chat
from app.services.hardware_monitor import check_network_status
from app.models import models
from app.models.models import VisitorStatus, UserRole, InviteStatus
from sqlalchemy import text

Base.metadata.create_all(bind=engine)

# Auto-migration for existing PostgreSQL databases
def auto_migrate_db():
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE visitor_logs ADD COLUMN IF NOT EXISTS gate_name VARCHAR DEFAULT 'Main Gate';"))
            conn.execute(text("ALTER TABLE visitor_logs ADD COLUMN IF NOT EXISTS photo_url VARCHAR;"))
            conn.execute(text("ALTER TABLE pre_approved_invites ADD COLUMN IF NOT EXISTS pass_type VARCHAR DEFAULT 'SINGLE';"))
            conn.execute(text("ALTER TABLE pre_approved_invites ADD COLUMN IF NOT EXISTS max_uses INTEGER DEFAULT 1;"))
            conn.execute(text("ALTER TABLE pre_approved_invites ADD COLUMN IF NOT EXISTS current_uses INTEGER DEFAULT 0;"))
            conn.commit()
    except Exception as e:
        print(f"Migration note: {e}")

auto_migrate_db()

app = FastAPI(title="VillaShield OS Engine", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="app/templates")

app.include_router(auth.router)
app.include_router(visitors.router)
app.include_router(staff.router)
app.include_router(admin.router)
app.include_router(invites.router)
app.include_router(events.router)
app.include_router(chat.router)

HARDWARE_STATUS_CACHE = [
    {"name": "Main Entrance Guard Camera Unit 1", "ip": "127.0.0.1", "status": "ONLINE 🟢"},
    {"name": "South Wall Perimeter Detection Node", "ip": "10.0.0.254", "status": "ONLINE 🟢"}
]

async def check_network_status():
    import os
    global HARDWARE_STATUS_CACHE
    while True:
        for device in HARDWARE_STATUS_CACHE:
            # -c 1 means send 1 packet, -w 2 means wait 2 seconds for a response
            exit_code = os.system(f"ping -c 1 -w 2 {device['ip']} > /dev/null 2>&1")
            
            if exit_code == 0:
                device["status"] = "ONLINE 🟢"
            else:
                device["status"] = "OFFLINE 🚨"
                print(f"[CRITICAL HARDWARE FAULT]: {device['name']} is offline!")
                
        await asyncio.sleep(60) # Pings your cameras once every 60 seconds for live data

@app.on_event("startup")
async def startup_event():
    # 1. Fire up background network camera monitors
    asyncio.create_task(check_network_status())
    
    # 2. Automatically seed master system accounts if missing
    db = SessionLocal()
    try:
        from app.auth import get_password_hash
        
        # A. Master Admin Seeding
        admin_exists = db.query(models.User).filter(models.User.username == "admin").first()
        if not admin_exists:
            master_admin = models.User(
                username="society_admin",
                hashed_password=get_password_hash("admin@2026"),
                role=UserRole.ADMIN,
                owner_name="System Committee Director"
            )
            db.add(master_admin)
            
        # B. Anonymous / Common Area Entity Seeding (FIX FOR QUESTION 1)
        common_exists = db.query(models.User).filter(models.User.username == "common_areas").first()
        if not common_exists:
            common_area_profile = models.User(
                username="common_areas",
                hashed_password=get_password_hash("common@2026"), # Locked account, nobody logs into it
                role=UserRole.RESIDENT,
                villa_number="00",
                villa_block="Common",
                owner_name="Society Infrastructure / Vendor"
            )
            db.add(common_area_profile)
            
        db.commit()
        print("[SYSTEM LOG]: Production Master Admin and Common Area entity seeding complete.")
    finally:
        db.close()

# ==================== NEW FRONTEND ENGINE ROUTES ====================

@app.get("/", response_class=HTMLResponse)
def login_page(request: Request):
    if request.cookies.get("villashield_user"):
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register-action")
def process_registration(
    username: str = Form(...), password: str = Form(...), role: str = Form(...),
    villa_number: str = Form(None), villa_block: str = Form(None), owner_name: str = Form(None),
    db: Session = Depends(get_db)
):
    existing = db.query(models.User).filter(models.User.username == username).first()
    if existing:
        return RedirectResponse(url="/register?error=Username+Taken", status_code=303)
    
    from app.auth import get_password_hash
    new_user = models.User(
        username=username, hashed_password=get_password_hash(password), role=UserRole[role],
        villa_number=villa_number, villa_block=villa_block, owner_name=owner_name if owner_name else username
    )
    db.add(new_user)
    db.commit()
    return RedirectResponse(url="/?success=Registration+Complete+Log+In", status_code=303)

@app.post("/login-action")
def process_login(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == username).first()
    from app.auth import verify_password
    if not user or not verify_password(password, user.hashed_password):
        return RedirectResponse(url="/?error=Invalid+Credentials", status_code=303)
    
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(key="villashield_user", value=user.username, max_age=86400)
    response.set_cookie(key="villashield_role", value=user.role.value, max_age=86400)
    return response

@app.post("/admin/register-staff-action")
def web_register_new_staff(
    request: Request, # <-- FIXED: Standard FastAPI request object mapping signature
    full_name: str = Form(...), 
    role: str = Form(...), 
    passcode: str = Form(...), 
    db: Session = Depends(get_db)
):
    """
    Allows Admin Committee members to onboard domestic workers or guards and hash their clock-in PINs.
    """
    admin_role = request.cookies.get("villashield_role")
    if admin_role != "ADMIN":
        return RedirectResponse(url="/", status_code=303)
        
    from app.auth import get_password_hash
    hashed_pin = get_password_hash(passcode)
    
    new_staff = models.DomesticStaff(
        full_name=full_name,
        role=role,
        passcode_hash=hashed_pin,
        is_active=True
    )
    db.add(new_staff)
    db.commit()
    return RedirectResponse(url="/dashboard?success=Staff+Member+Onboarded+Successfully", status_code=303)

@app.post("/staff-punch-action/")
def web_staff_punch(passcode: str = Form(...), db: Session = Depends(get_db)):
    import datetime
    all_staff = db.query(models.DomesticStaff).filter(models.DomesticStaff.is_active == True).all()
    target_staff = None
    from app.auth import verify_password
    for s in all_staff:
        if verify_password(passcode, s.passcode_hash):
            target_staff = s
            break
    if not target_staff:
        return RedirectResponse(url="/dashboard?error=Invalid+Staff+PIN", status_code=303)

    active_session = db.query(models.StaffAttendance).filter(
        models.StaffAttendance.staff_id == target_staff.id, 
        models.StaffAttendance.check_out == None
    ).first()
    
    if active_session:
        active_session.check_out = datetime.datetime.utcnow()
        db.commit()
        # FIXED: Added the explicit redirect back to dashboard view loop
        return RedirectResponse(url="/dashboard?success=Staff+" + target_staff.full_name + "+Checked+Out", status_code=303)
    else:
        new_session = models.StaffAttendance(staff_id=target_staff.id)
        db.add(new_session)
        db.commit()
        # FIXED: Added the explicit redirect back to dashboard view loop
        return RedirectResponse(url="/dashboard?success=Staff+" + target_staff.full_name + "+Checked+In", status_code=303)

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_view(request: Request, db: Session = Depends(get_db)):
    username = request.cookies.get("villashield_user")
    role = request.cookies.get("villashield_role")
    if not username: return RedirectResponse(url="/", status_code=303)

    # 1. ROUTE TO EXECUTIVE COMMITTEE ADMIN OVERLOOK VIEW
    if role == "ADMIN":
        from zoneinfo import ZoneInfo
        ist_zone = ZoneInfo("Asia/Kolkata")

        total_visitors = db.query(models.VisitorLog).count()
        approved = db.query(models.VisitorLog).filter(models.VisitorLog.status == "APPROVED").count()
        denied = db.query(models.VisitorLog).filter(models.VisitorLog.status == "DENIED").count()
        active_staff = db.query(models.StaffAttendance).filter(models.StaffAttendance.check_out == None).count()
        
        # Safe extraction of all active guard system indices
        guards = db.query(models.User).filter(models.User.role == UserRole.GUARD).all()

        # FIXED: Pull raw logs sequentially to guarantee perfect data stability
        visitor_records = db.query(models.VisitorLog).order_by(models.VisitorLog.id.desc()).limit(50).all()
            
        logs = []
        for log_item in visitor_records:
            # FIXED: Intentionally check both relationship and raw attribute keys safely
            v_id = log_item.villa_id.id if hasattr(log_item.villa_id, 'id') else log_item.villa_id
            resident_profile = db.query(models.User).filter(models.User.id == v_id).first()
            
            if log_item.created_at:
                local_created = log_item.created_at.replace(tzinfo=ZoneInfo("UTC")).astimezone(ist_zone)
                created_str = local_created.strftime("%d-%b-%Y %I:%M %p")
            else:
                created_str = "Just Now ⏱️"

            logs.append({
                "id": log_item.id,
                "visitor_name": log_item.visitor_name,
                "phone_number": log_item.phone_number,
                "vehicle_number": log_item.vehicle_number,
                "purpose": log_item.purpose,
                "status": log_item.status,
                "timestamp": created_str,
                "destination_villa": f"{resident_profile.villa_number} - {resident_profile.villa_block}" if resident_profile else "Common Area / Infrastructure"
            })

        # FIXED: Apply the same robust check for the Staff Attendance profiles
        staff_records = db.query(models.StaffAttendance).order_by(models.StaffAttendance.id.desc()).limit(50).all()
            
        attendance_logs = []
        for att in staff_records:
            s_id = att.staff_id.id if hasattr(att.staff_id, 'id') else att.staff_id
            staff_member = db.query(models.DomesticStaff).filter(models.DomesticStaff.id == s_id).first()
            if staff_member:
                local_in = att.check_in.replace(tzinfo=ZoneInfo("UTC")).astimezone(ist_zone) if att.check_in else None
                local_out = att.check_out.replace(tzinfo=ZoneInfo("UTC")).astimezone(ist_zone) if att.check_out else None
                
                check_in_str = local_in.strftime("%d-%b-%Y %I:%M %p") if local_in else "N/A"
                check_out_str = local_out.strftime("%d-%b-%Y %I:%M %p") if local_out else "Still On Site 🟢"
                
                attendance_logs.append({
                    "name": staff_member.full_name,
                    "role": staff_member.role,
                    "check_in": check_in_str,
                    "check_out": check_out_str
                })

        global HARDWARE_STATUS_CACHE

        metrics_payload = {"cards": {"total_visitors": total_visitors, "approved": approved, "denied": denied, "active_staff": active_staff}}
        return templates.TemplateResponse("dashboard.html", {
            "request": request, 
            "username": username, 
            "metrics": metrics_payload, 
            "logs": logs, 
            "guards": guards, 
            "attendance_logs": attendance_logs,
            "hardware_status": HARDWARE_STATUS_CACHE
        })

    elif role == "GUARD":
        # Pull all resident directory nodes to formulate searchable select drops
        residents = db.query(models.User).filter(models.User.role == UserRole.RESIDENT).all()
        return templates.TemplateResponse("guard.html", {"request": request, "username": username, "residents": residents})

    elif role == "RESIDENT":
        current_res = db.query(models.User).filter(models.User.username == username).first()
        pending_visitors = db.query(models.VisitorLog).filter(models.VisitorLog.villa_id == current_res.id, models.VisitorLog.status == "PENDING").order_by(models.VisitorLog.id.desc()).all()
        active_invites = db.query(models.PreApprovedInvite).filter(models.PreApprovedInvite.villa_id == current_res.id).order_by(models.PreApprovedInvite.id.desc()).all()
        
        # Pull active competitions for quick resident registration with cutoff time calculation
        active_comps = db.query(models.EventCompetition).all()
        comp_list = []
        now_utc = datetime.datetime.utcnow()
        for c in active_comps:
            evt = db.query(models.Event).filter(models.Event.id == c.event_id).first()
            is_open = True
            cutoff_str = ""
            if evt and evt.event_date:
                cutoff_time = evt.event_date - datetime.timedelta(hours=1)
                is_open = now_utc < cutoff_time
                cutoff_str = cutoff_time.strftime("%d %b %I:%M %p")
            comp_list.append({
                "id": c.id,
                "title": c.title,
                "category": c.category,
                "event_title": evt.title if evt else "Society Event",
                "is_open": is_open,
                "cutoff_str": cutoff_str
            })

        return templates.TemplateResponse("resident.html", {
            "request": request, 
            "username": username,
            "villa_number": current_res.villa_number,
            "pending_visitors": pending_visitors, 
            "active_invites": active_invites,
            "competitions": comp_list
        })

    return RedirectResponse(url="/", status_code=303)

@app.get("/resident", response_class=HTMLResponse)
@app.get("/resident.html", response_class=HTMLResponse)
def resident_route_alias(request: Request):
    return RedirectResponse(url="/dashboard", status_code=303)

# --- BACKEND ENDPOINT FOR GUARD MONITOR API POLLING ---
@app.get("/api/v1/guard/live-tracker-json")
def guard_live_tracker_api(db: Session = Depends(get_db)):
    logs = db.query(models.VisitorLog).order_by(models.VisitorLog.id.desc()).limit(15).all()
    return [{"id": l.id, "name": l.visitor_name, "purpose": l.purpose, "villa_id": l.villa_id, "status": str(l.status).replace("VisitorStatus.", "")} for l in logs]

@app.post("/visitor-register-action")
def web_visitor_register(
    villa_id: int = Form(...), 
    visitor_name: str = Form(...), 
    phone_number: str = Form(...), 
    vehicle_number: str = Form(None), 
    purpose: str = Form(...),
    gate_name: str = Form("Main Gate"),
    photo_url: str = Form(None),
    db: Session = Depends(get_db)
):
    new_log = models.VisitorLog(
        villa_id=villa_id, 
        visitor_name=visitor_name, 
        phone_number=phone_number, 
        vehicle_number=vehicle_number, 
        purpose=purpose, 
        gate_name=gate_name,
        photo_url=photo_url,
        status=VisitorStatus.PENDING
    )
    db.add(new_log)
    db.commit()
    return RedirectResponse(url="/dashboard?success=Registered", status_code=303)

@app.post("/resident/create-invite-action")
def web_create_invite(
    request: Request,
    guest_name: str = Form(...),
    phone_number: str = Form(None),
    duration_hours: int = Form(12),
    pass_type: str = Form("SINGLE"),
    max_uses: int = Form(1),
    db: Session = Depends(get_db)
):
    username = request.cookies.get("villashield_user")
    current_res = db.query(models.User).filter(models.User.username == username).first()
    if not current_res:
        return RedirectResponse(url="/", status_code=303)
        
    from app.routers.invites import generate_unique_otp
    import datetime
    
    otp = generate_unique_otp(db)
    valid_until = datetime.datetime.utcnow() + datetime.timedelta(hours=duration_hours)
    
    p_enum = models.PassType.EVENT_GROUP if pass_type == "EVENT_GROUP" else models.PassType.SINGLE
    m_uses = max_uses if max_uses and max_uses > 0 else (50 if p_enum == models.PassType.EVENT_GROUP else 1)

    invite = models.PreApprovedInvite(
        villa_id=current_res.id,
        guest_name=guest_name,
        phone_number=phone_number,
        otp_code=otp,
        valid_until=valid_until,
        pass_type=p_enum,
        max_uses=m_uses,
        current_uses=0,
        status=InviteStatus.PENDING
    )
    db.add(invite)
    db.commit()
    msg = f"Event+Pass+Created!+OTP:+{otp}+Max+Guests:+{m_uses}" if p_enum == models.PassType.EVENT_GROUP else f"Single+Guest+Pass+Created!+OTP:+{otp}"
    return RedirectResponse(url=f"/dashboard?success={msg}", status_code=303)

@app.post("/guard/verify-otp-action")
def web_verify_otp(
    otp_code: str = Form(...),
    gate_name: str = Form("Main Gate"),
    db: Session = Depends(get_db)
):
    import datetime
    now = datetime.datetime.utcnow()
    
    invite = db.query(models.PreApprovedInvite).filter(
        models.PreApprovedInvite.otp_code == otp_code.strip(),
        models.PreApprovedInvite.status == InviteStatus.PENDING,
        models.PreApprovedInvite.valid_until >= now
    ).first()
    
    if not invite:
        return RedirectResponse(url="/dashboard?error=Invalid,+Expired,+or+Already+Used+OTP+Pass", status_code=303)
        
    invite.current_uses += 1
    if invite.pass_type == models.PassType.SINGLE or invite.current_uses >= invite.max_uses:
        invite.status = InviteStatus.USED

    if invite.pass_type == models.PassType.EVENT_GROUP:
        v_name = f"{invite.guest_name} (Event Guest #{invite.current_uses} of {invite.max_uses})"
        msg = f"EVENT+PASS+VERIFIED!+Guest+%23{invite.current_uses}+{invite.guest_name}+Entered"
    else:
        v_name = f"{invite.guest_name} (Pre-Approved)"
        msg = f"Pre-Approved+Pass+Verified!+Entry+Granted+for+{invite.guest_name}"

    new_log = models.VisitorLog(
        villa_id=invite.villa_id,
        visitor_name=v_name,
        phone_number=invite.phone_number or "Pre-Authorized Group Pass",
        purpose="Pre-Approved Event/Guest Entry",
        gate_name=gate_name,
        status=VisitorStatus.APPROVED
    )
    db.add(new_log)
    db.commit()
    return RedirectResponse(url=f"/dashboard?success={msg}", status_code=303)

@app.post("/resident-decision-action")
def web_resident_decision(log_id: int = Form(...), decision: str = Form(...), db: Session = Depends(get_db)):
    log_item = db.query(models.VisitorLog).filter(models.VisitorLog.id == log_id).first()
    if log_item:
        log_item.status = VisitorStatus[decision]
        db.commit()
    return RedirectResponse(url="/dashboard", status_code=303)

@app.post("/admin/evict-guard/{guard_id}")
def evict_guard_action(guard_id: int, request: Request, db: Session = Depends(get_db)):
    role = request.cookies.get("villashield_role")
    if role != "ADMIN": raise HTTPException(status_code=403)
    target_guard = db.query(models.User).filter(models.User.id == guard_id).first()
    if target_guard:
        db.delete(target_guard)
        db.commit()
    return RedirectResponse(url="/dashboard?success=Guard+Removed", status_code=303)

@app.get("/logout-action")
def process_logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("villashield_user")
    response.delete_cookie("villashield_role")
    return response

@app.get("/admin/export-visitors-csv")
def export_visitors_csv(request: Request, db: Session = Depends(get_db)):
    role = request.cookies.get("villashield_role")
    if role != "ADMIN": 
        return RedirectResponse(url="/", status_code=303)
        
    from zoneinfo import ZoneInfo
    ist_zone = ZoneInfo("Asia/Kolkata")
        
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Log ID", "Visitor Name", "Phone Number", "Vehicle Plate", "Target Villa", "Purpose", "Status", "Time of Crossing"])
    
    records = db.query(models.VisitorLog).order_by(models.VisitorLog.id.asc()).all()
    for log in records:
        res = db.query(models.User).filter(models.User.id == log.villa_id).first()
        dest = f"{res.villa_number} - {res.villa_block}" if res else "Common Area"
        status_str = str(log.status).replace("VisitorStatus.", "")
        
        if log.created_at:
            local_created = log.created_at.replace(tzinfo=ZoneInfo("UTC")).astimezone(ist_zone)
            # FIXED: Wrapped with single quotes so Excel treats it as text and hides the quote
            time_str = f"'{local_created.strftime('%d-%b-%Y %I:%M %p')}"
        else:
            time_str = "N/A"
            
        writer.writerow([log.id, log.visitor_name, log.phone_number, log.vehicle_number or 'Pedestrian', dest, log.purpose, status_str, time_str])
        
    output.seek(0)
    return StreamingResponse(io.BytesIO(output.getvalue().encode("utf-8")), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=VillaShield_Visitor_Audit_Log.csv"})

@app.get("/admin/export-attendance-csv")
def export_attendance_csv(request: Request, db: Session = Depends(get_db)):
    role = request.cookies.get("villashield_role")
    if role != "ADMIN": 
        return RedirectResponse(url="/", status_code=303)
        
    from zoneinfo import ZoneInfo
    ist_zone = ZoneInfo("Asia/Kolkata")
        
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Staff Name", "Designation Role", "Clocked Check-In", "Clocked Check-Out"])
    
    records = db.query(models.StaffAttendance).order_by(models.StaffAttendance.id.asc()).all()
    for att in records:
        staff = db.query(models.DomesticStaff).filter(models.DomesticStaff.id == att.staff_id).first()
        if staff:
            local_in = att.check_in.replace(tzinfo=ZoneInfo("UTC")).astimezone(ist_zone) if att.check_in else None
            local_out = att.check_out.replace(tzinfo=ZoneInfo("UTC")).astimezone(ist_zone) if att.check_out else None
            
            # FIXED: Wrapped with single quotes so Excel treats it as text and hides the quote
            in_str = f"'{local_in.strftime('%d-%b-%Y %I:%M %p')}" if local_in else "N/A"
            out_str = f"'{local_out.strftime('%d-%b-%Y %I:%M %p')}" if local_out else "Still On Site"
            
            writer.writerow([staff.full_name, staff.role, in_str, out_str])
            
    output.seek(0)
    return StreamingResponse(io.BytesIO(output.getvalue().encode("utf-8")), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=VillaShield_Staff_Attendance_Report.csv"})

# --- Society Event Management & Leaderboard Web Routes ---

@app.get("/events", response_class=HTMLResponse)
def get_events_page(request: Request, db: Session = Depends(get_db)):
    username = request.cookies.get("villashield_user")
    role = request.cookies.get("villashield_role")
    if not username:
        return RedirectResponse(url="/", status_code=303)

    events_list = db.query(models.Event).order_by(models.Event.id.desc()).all()
    events_data = []
    for evt in events_list:
        comps = db.query(models.EventCompetition).filter(models.EventCompetition.event_id == evt.id).all()
        comp_details = []
        for c in comps:
            participants = db.query(models.EventParticipant).filter(models.EventParticipant.competition_id == c.id).all()
            comp_details.append({
                "id": c.id,
                "title": c.title,
                "category": c.category,
                "coordinator_name": c.coordinator_name or "N/A",
                "coordinator_phone": c.coordinator_phone or "",
                "participant_count": len(participants),
                "participants": [
                    {
                        "id": p.id,
                        "name": p.participant_name,
                        "villa": p.villa_number,
                        "category": p.category,
                        "phone": p.phone_number or "N/A",
                        "rank": p.rank
                    } for p in participants
                ]
            })
        events_data.append({
            "id": evt.id,
            "title": evt.title,
            "description": evt.description,
            "event_date": evt.event_date.strftime("%d %b %Y, %I:%M %p") if evt.event_date else "TBD",
            "venue": evt.venue,
            "status": str(evt.status).replace("EventStatus.", ""),
            "competitions": comp_details
        })

    return templates.TemplateResponse("events.html", {
        "request": request,
        "username": username,
        "role": role,
        "events": events_data
    })

@app.post("/events/create-action")
def web_create_event(
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    event_date: str = Form(...),
    venue: str = Form("Community Hall"),
    db: Session = Depends(get_db)
):
    role = request.cookies.get("villashield_role")
    if role != "ADMIN":
        return RedirectResponse(url="/events", status_code=303)

    try:
        parsed_date = datetime.datetime.fromisoformat(event_date)
    except Exception:
        parsed_date = datetime.datetime.utcnow() + datetime.timedelta(days=7)

    new_evt = models.Event(
        title=title,
        description=description,
        event_date=parsed_date,
        venue=venue,
        status=models.EventStatus.UPCOMING
    )
    db.add(new_evt)
    db.commit()
    return RedirectResponse(url="/events", status_code=303)

@app.post("/events/add-competition-action")
def web_add_competition(
    request: Request,
    event_id: int = Form(...),
    title: str = Form(...),
    category: str = Form("OPEN"),
    coordinator_name: str = Form(""),
    coordinator_phone: str = Form(""),
    db: Session = Depends(get_db)
):
    role = request.cookies.get("villashield_role")
    if role != "ADMIN":
        return RedirectResponse(url="/events", status_code=303)

    new_comp = models.EventCompetition(
        event_id=event_id,
        title=title,
        category=category,
        coordinator_name=coordinator_name,
        coordinator_phone=coordinator_phone
    )
    db.add(new_comp)
    db.commit()
    return RedirectResponse(url="/events", status_code=303)

@app.post("/events/register-participant-action")
def web_register_participant(
    request: Request,
    competition_id: int = Form(...),
    participant_name: str = Form(...),
    villa_number: str = Form(...),
    category: str = Form("OPEN"),
    phone_number: str = Form(""),
    db: Session = Depends(get_db)
):
    username = request.cookies.get("villashield_user")
    role = request.cookies.get("villashield_role")
    if not username:
        return RedirectResponse(url="/", status_code=303)

    comp = db.query(models.EventCompetition).filter(models.EventCompetition.id == competition_id).first()
    if not comp:
        return RedirectResponse(url="/dashboard?error=Competition+not+found", status_code=303)

    event = db.query(models.Event).filter(models.Event.id == comp.event_id).first()
    if event and event.event_date:
        cutoff_time = event.event_date - datetime.timedelta(hours=1)
        if datetime.datetime.utcnow() >= cutoff_time and role != "ADMIN":
            return RedirectResponse(
                url="/dashboard?error=Registration+Closed:+Cutoff+window+is+1+hour+prior+to+competition+start.",
                status_code=303
            )

    new_p = models.EventParticipant(
        competition_id=competition_id,
        participant_name=participant_name,
        villa_number=villa_number,
        category=category,
        phone_number=phone_number,
        registration_source="VILLASHIELD_APP"
    )
    db.add(new_p)
    db.commit()
    return RedirectResponse(url="/dashboard?success=Registered+for+Competition+Successfully!", status_code=303)

@app.post("/events/declare-winners-action")
def web_declare_winners(
    request: Request,
    competition_id: int = Form(...),
    winner_id: int = Form(...),
    runner_up_1_id: Optional[int] = Form(None),
    runner_up_2_id: Optional[int] = Form(None),
    db: Session = Depends(get_db)
):
    role = request.cookies.get("villashield_role")
    if role != "ADMIN":
        return RedirectResponse(url="/events", status_code=303)

    comp = db.query(models.EventCompetition).filter(models.EventCompetition.id == competition_id).first()
    if not comp:
        return RedirectResponse(url="/events", status_code=303)

    # Clear old rankings and leaderboard entries
    db.query(models.EventLeaderboard).filter(models.EventLeaderboard.competition_id == competition_id).delete()
    db.query(models.EventParticipant).filter(models.EventParticipant.competition_id == competition_id).update({"rank": "NONE"})

    # 1st Place - Winner (10 Points)
    if winner_id:
        p1 = db.query(models.EventParticipant).filter(models.EventParticipant.id == winner_id).first()
        if p1:
            p1.rank = "WINNER"
            db.add(models.EventLeaderboard(event_id=comp.event_id, competition_id=competition_id, participant_id=p1.id, rank="WINNER", points=10))

    # 2nd Place - 1st Runner Up (7 Points)
    if runner_up_1_id:
        p2 = db.query(models.EventParticipant).filter(models.EventParticipant.id == runner_up_1_id).first()
        if p2:
            p2.rank = "RUNNER_UP_1"
            db.add(models.EventLeaderboard(event_id=comp.event_id, competition_id=competition_id, participant_id=p2.id, rank="RUNNER_UP_1", points=7))

    # 3rd Place - 2nd Runner Up (5 Points)
    if runner_up_2_id:
        p3 = db.query(models.EventParticipant).filter(models.EventParticipant.id == runner_up_2_id).first()
        if p3:
            p3.rank = "RUNNER_UP_2"
            db.add(models.EventLeaderboard(event_id=comp.event_id, competition_id=competition_id, participant_id=p3.id, rank="RUNNER_UP_2", points=5))

    db.commit()
    return RedirectResponse(url="/events", status_code=303)

@app.get("/leaderboard", response_class=HTMLResponse)
def get_leaderboard_page(
    request: Request,
    event_id: Optional[str] = None,
    competition_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    username = request.cookies.get("villashield_user")
    role = request.cookies.get("villashield_role")
    
    parsed_event_id: Optional[int] = int(event_id) if (event_id and event_id.strip().isdigit()) else None
    parsed_comp_id: Optional[int] = int(competition_id) if (competition_id and competition_id.strip().isdigit()) else None

    events = db.query(models.Event).order_by(models.Event.id.desc()).all()
    competitions_query = db.query(models.EventCompetition)
    if parsed_event_id:
        competitions_query = competitions_query.filter(models.EventCompetition.event_id == parsed_event_id)
    all_competitions = competitions_query.all()

    query = db.query(models.EventLeaderboard)
    if parsed_event_id:
        query = query.filter(models.EventLeaderboard.event_id == parsed_event_id)
    if parsed_comp_id:
        query = query.filter(models.EventLeaderboard.competition_id == parsed_comp_id)
    entries = query.all()

    # Group points by villa with tie-breaking stats
    villa_scores = {}
    winner_details = []

    for entry in entries:
        participant = db.query(models.EventParticipant).filter(models.EventParticipant.id == entry.participant_id).first()
        competition = db.query(models.EventCompetition).filter(models.EventCompetition.id == entry.competition_id).first()
        event = db.query(models.Event).filter(models.Event.id == entry.event_id).first() if entry.event_id else None
        
        if participant and competition:
            v_num = participant.villa_number or "101"
            if v_num not in villa_scores:
                villa_scores[v_num] = {"villa": v_num, "points": 0, "gold": 0, "silver": 0, "bronze": 0}
            
            villa_scores[v_num]["points"] += entry.points
            if entry.rank == "WINNER":
                villa_scores[v_num]["gold"] += 1
            elif entry.rank == "RUNNER_UP_1":
                villa_scores[v_num]["silver"] += 1
            elif entry.rank == "RUNNER_UP_2":
                villa_scores[v_num]["bronze"] += 1

            winner_details.append({
                "participant_name": participant.participant_name,
                "villa_number": participant.villa_number,
                "event_id": event.id if event else None,
                "event_title": event.title if event else "Society Event",
                "competition_id": competition.id,
                "competition_title": competition.title,
                "category": participant.category,
                "rank": entry.rank,
                "points": entry.points
            })

    # Tie-breaking sorting function: Points (desc) > Gold (desc) > Silver (desc) > Bronze (desc) > Villa No (asc)
    def villa_sort_key(v):
        v_num_clean = "".join(filter(str.isdigit, str(v["villa"])))
        v_int = int(v_num_clean) if v_num_clean else 999999
        return (-v["points"], -v["gold"], -v["silver"], -v["bronze"], v_int)

    sorted_villas = sorted(villa_scores.values(), key=villa_sort_key)
    
    # Assign positions with tied rank detection
    prev_score_tuple = None
    current_pos = 0
    for idx, v in enumerate(sorted_villas, start=1):
        score_tuple = (v["points"], v["gold"], v["silver"], v["bronze"])
        if score_tuple != prev_score_tuple:
            current_pos = idx
            prev_score_tuple = score_tuple
            v["is_tied"] = False
        else:
            v["is_tied"] = True
        v["position"] = current_pos

    # Build Competition-Wise Podium Cards view
    comp_cards = []
    card_comps = all_competitions
    if competition_id:
        card_comps = [c for c in all_competitions if c.id == competition_id]
    
    for c in card_comps:
        c_event = db.query(models.Event).filter(models.Event.id == c.event_id).first()
        parts = db.query(models.EventParticipant).filter(models.EventParticipant.competition_id == c.id).all()
        w1 = next((p for p in parts if p.rank == "WINNER"), None)
        w2 = next((p for p in parts if p.rank == "RUNNER_UP_1"), None)
        w3 = next((p for p in parts if p.rank == "RUNNER_UP_2"), None)
        
        comp_cards.append({
            "competition_id": c.id,
            "title": c.title,
            "event_title": c.event_title if hasattr(c, "event_title") and c.event_title else (c_event.title if c_event else "Society Event"),
            "category": c.category,
            "total_participants": len(parts),
            "winner": w1,
            "runner_up_1": w2,
            "runner_up_2": w3
        })

    return templates.TemplateResponse("leaderboard.html", {
        "request": request,
        "username": username,
        "role": role,
        "events": events,
        "competitions": all_competitions,
        "selected_event_id": event_id,
        "selected_comp_id": competition_id,
        "leaderboard": sorted_villas,
        "winners": winner_details,
        "comp_cards": comp_cards
    })
