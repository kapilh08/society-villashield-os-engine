from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import models
from app.auth import get_current_user

router = APIRouter(prefix="/api/v1/admin", tags=["Admin Control Tower Portal"])

@router.get("/metrics")
def get_dashboard_metrics(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if current_user.role != models.UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Administrative access configuration privilege enforced")
    
    total_visitors = db.query(models.VisitorLog).count()
    approved_entries = db.query(models.VisitorLog).filter(models.VisitorLog.status == models.VisitorStatus.APPROVED).count()
    denied_entries = db.query(models.VisitorLog).filter(models.VisitorLog.status == models.VisitorStatus.DENIED).count()
    active_staff = db.query(models.StaffAttendance).filter(models.StaffAttendance.check_out == None).count()

    hourly_data = db.query(
        func.extract('hour', models.VisitorLog.created_at).label('hour'),
        func.count(models.VisitorLog.id).label('count')
    ).group_by('hour').all()
    
    chart_payload = {int(row.hour): row.count for row in hourly_data}

    return {
        "cards": {
            "total_visitors": total_visitors,
            "approved": approved_entries,
            "denied": denied_entries,
            "active_staff": active_staff
        },
        "hourly_distribution": chart_payload
    }
