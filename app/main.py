from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import asyncio
import io
import csv

from app.database import engine, Base, get_db, SessionLocal
from app.routers import auth, visitors, staff, admin, invites
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
        return templates.TemplateResponse("resident.html", {"request": request, "username": username, "pending_visitors": pending_visitors, "active_invites": active_invites})

    return RedirectResponse(url="/", status_code=303)

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