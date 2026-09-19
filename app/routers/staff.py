from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import datetime
from app.database import get_db
from app.models import models
from app.schemas import schemas
from app.auth import get_current_user, get_password_hash

router = APIRouter(prefix="/api/v1/staff", tags=["Staff Management Ledger Module"])

@router.post("/register", response_model=schemas.StaffCreate, status_code=status.HTTP_201_CREATED)
def register_staff(payload: schemas.StaffCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if current_user.role != models.UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Administrative access configuration privilege enforced")
    
    hashed_passcode = get_password_hash(payload.passcode)
    new_staff = models.DomesticStaff(
        full_name=payload.full_name,
        role=payload.role,
        passcode_hash=hashed_passcode,
        is_active=True
    )
    db.add(new_staff)
    db.commit()
    return payload

@router.post("/clock-io")
def staff_clock_io(payload: schemas.StaffClockPayload, db: Session = Depends(get_db)):
    all_staff = db.query(models.DomesticStaff).filter(models.DomesticStaff.is_active == True).all()
    target_staff = None
    from app.auth import verify_password
    for s in all_staff:
        if verify_password(payload.passcode, s.passcode_hash):
            target_staff = s
            break
            
    if not target_staff:
        raise HTTPException(status_code=401, detail="Invalid credential identification signature string")

    active_session = db.query(models.StaffAttendance).filter(
        models.StaffAttendance.staff_id == target_staff.id,
        models.StaffAttendance.check_out == None
    ).first()

    if active_session:
        active_session.check_out = datetime.datetime.utcnow()
        db.commit()
        return {"action": "CHECK_OUT", "staff_name": target_staff.full_name, "timestamp": active_session.check_out}
    else:
        new_session = models.StaffAttendance(staff_id=target_staff.id)
        db.add(new_session)
        db.commit()
        return {"action": "CHECK_IN", "staff_name": target_staff.full_name, "timestamp": new_session.check_in}
