import random
import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import models
from app.schemas import schemas
from app.auth import get_current_user
from app.services.websocket_manager import manager

router = APIRouter(prefix="/api/v1/invites", tags=["Pre-Approved Invites Portal"])

def generate_unique_otp(db: Session) -> str:
    """Generates a unique 4-digit OTP code."""
    for _ in range(100):
        otp = str(random.randint(1000, 9999))
        existing = db.query(models.PreApprovedInvite).filter(
            models.PreApprovedInvite.otp_code == otp,
            models.PreApprovedInvite.status == models.InviteStatus.PENDING
        ).first()
        if not existing:
            return otp
    return str(random.randint(100000, 999999))

@router.post("/create", response_model=schemas.InviteOut, status_code=status.HTTP_201_CREATED)
def create_preapproved_invite(
    payload: schemas.InviteCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if current_user.role != models.UserRole.RESIDENT:
        raise HTTPException(status_code=403, detail="Only residents can create pre-approved guest passes")
    
    otp = generate_unique_otp(db)
    valid_until = datetime.datetime.utcnow() + datetime.timedelta(hours=payload.duration_hours or 12)
    
    pass_type = payload.pass_type or models.PassType.SINGLE
    max_uses = payload.max_uses if payload.max_uses and payload.max_uses > 0 else (50 if pass_type == models.PassType.EVENT_GROUP else 1)

    invite = models.PreApprovedInvite(
        villa_id=current_user.id,
        guest_name=payload.guest_name,
        phone_number=payload.phone_number,
        otp_code=otp,
        valid_until=valid_until,
        pass_type=pass_type,
        max_uses=max_uses,
        current_uses=0,
        status=models.InviteStatus.PENDING
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return invite

@router.post("/verify-otp", response_model=schemas.VisitorOut)
async def verify_otp_pass(
    payload: schemas.OTPVerifyPayload,
    db: Session = Depends(get_db)
):
    now = datetime.datetime.utcnow()
    
    invite = db.query(models.PreApprovedInvite).filter(
        models.PreApprovedInvite.otp_code == payload.otp_code,
        models.PreApprovedInvite.status == models.InviteStatus.PENDING,
        models.PreApprovedInvite.valid_until >= now
    ).first()
    
    if not invite:
        raise HTTPException(status_code=400, detail="Invalid, expired, or already used OTP pass code")
    
    # 1. Increment usage count
    invite.current_uses += 1
    
    # 2. Mark as USED if SINGLE pass or max_uses reached
    if invite.pass_type == models.PassType.SINGLE or invite.current_uses >= invite.max_uses:
        invite.status = models.InviteStatus.USED
    
    # 3. Log an APPROVED entry in VisitorLog automatically
    if invite.pass_type == models.PassType.EVENT_GROUP:
        v_name = f"{invite.guest_name} (Event Guest #{invite.current_uses} of {invite.max_uses})"
    else:
        v_name = f"{invite.guest_name} (Pre-Approved)"

    new_log = models.VisitorLog(
        villa_id=invite.villa_id,
        visitor_name=v_name,
        phone_number=invite.phone_number or "Pre-Authorized Group Pass",
        purpose="Pre-Approved Event/Guest Entry",
        gate_name=payload.gate_name or "Main Gate",
        status=models.VisitorStatus.APPROVED
    )
    db.add(new_log)
    db.commit()
    db.refresh(new_log)

    # 4. Broadcast status update to active guard monitors
    await manager.broadcast_action_to_guards({
        "event": "VISITOR_STATUS_UPDATED",
        "log_id": new_log.id,
        "status": new_log.status,
        "villa_id": new_log.villa_id
    })
    
    return new_log

@router.get("/my-invites", response_model=List[schemas.InviteOut])
def list_my_invites(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if current_user.role != models.UserRole.RESIDENT:
        raise HTTPException(status_code=403, detail="Only residents can view their active invites")
    
    return db.query(models.PreApprovedInvite).filter(
        models.PreApprovedInvite.villa_id == current_user.id
    ).order_by(models.PreApprovedInvite.id.desc()).all()
