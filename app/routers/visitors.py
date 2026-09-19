from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import models
from app.schemas import schemas
from app.auth import get_current_user
from app.services.websocket_manager import manager

router = APIRouter(prefix="/api/v1/visitors", tags=["Visitor Management Module Portal"])

@router.post("/register", response_model=schemas.VisitorOut, status_code=status.HTTP_201_CREATED)
async def register_visitor(payload: schemas.VisitorCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if current_user.role != models.UserRole.GUARD:
        raise HTTPException(status_code=403, detail="Privilege access authorization mapping restriction violation")
    
    new_log = models.VisitorLog(
        villa_id=payload.villa_id,
        visitor_name=payload.visitor_name,
        phone_number=payload.phone_number,
        vehicle_number=payload.vehicle_number,
        purpose=payload.purpose,
        status=models.VisitorStatus.PENDING
    )
    db.add(new_log)
    db.commit()
    db.refresh(new_log)

    # Dispatches live alert event over Active Resident App Client WebSockets
    await manager.send_gate_alert_to_resident(
        user_id=payload.villa_id,
        payload={
            "event": "VISITOR_AWAITING_APPROVAL",
            "log_id": new_log.id,
            "visitor_name": new_log.visitor_name,
            "purpose": new_log.purpose,
            "vehicle_number": new_log.vehicle_number
        }
    )
    return new_log

@router.patch("/{log_id}/action", response_model=schemas.VisitorOut)
async def process_visitor_action(log_id: int, payload: schemas.VisitorAction, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if current_user.role != models.UserRole.RESIDENT:
        raise HTTPException(status_code=403, detail="Action signature restricted strictly to target residents")
    
    log_item = db.query(models.VisitorLog).filter(models.VisitorLog.id == log_id).first()
    if not log_item:
        raise HTTPException(status_code=404, detail="Target processing record reference key not found")
    
    if log_item.villa_id != current_user.id:
        raise HTTPException(status_code=403, detail="Data modification domain payload authorization error")

    log_item.status = payload.status
    db.commit()
    db.refresh(log_item)

    # Propagates updated log tracking arrays directly onto active Guard monitors
    await manager.broadcast_action_to_guards({
        "event": "VISITOR_STATUS_UPDATED",
        "log_id": log_item.id,
        "status": log_item.status,
        "villa_id": log_item.villa_id
    })
    return log_item
