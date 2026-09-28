from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import datetime

from app.database import get_db
from app.models import models
from app.schemas import schemas
from app.auth import get_current_user

router = APIRouter(prefix="/api/v1/events", tags=["Society Event Management & Leaderboard Engine"])

@router.post("/create", response_model=schemas.EventCreate, status_code=status.HTTP_201_CREATED)
def create_event(payload: schemas.EventCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if current_user.role != models.UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Administrative privileges required to create society events")
    
    new_event = models.Event(
        title=payload.title,
        description=payload.description,
        event_date=payload.event_date,
        venue=payload.venue or "Community Hall",
        status=models.EventStatus.UPCOMING
    )
    db.add(new_event)
    db.commit()
    db.refresh(new_event)
    return payload

@router.post("/{event_id}/competitions", status_code=status.HTTP_201_CREATED)
def add_competition(event_id: int, payload: schemas.CompetitionCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if current_user.role != models.UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Administrative privileges required to add competitions")
    
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Society event not found")
        
    comp = models.EventCompetition(
        event_id=event_id,
        title=payload.title,
        category=payload.category or "OPEN",
        coordinator_name=payload.coordinator_name,
        coordinator_phone=payload.coordinator_phone
    )
    db.add(comp)
    db.commit()
    db.refresh(comp)
    return comp

@router.post("/register-participant", status_code=status.HTTP_201_CREATED)
def register_participant(payload: schemas.ParticipantCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    comp = db.query(models.EventCompetition).filter(models.EventCompetition.id == payload.competition_id).first()
    if not comp:
        raise HTTPException(status_code=404, detail="Target competition not found")

    # Enforce 1-hour registration cutoff before event start for residents
    event = db.query(models.Event).filter(models.Event.id == comp.event_id).first()
    if event and event.event_date:
        cutoff_time = event.event_date - datetime.timedelta(hours=1)
        if datetime.datetime.utcnow() >= cutoff_time and current_user.role != models.UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Registration closed: Cutoff window is 1 hour prior to competition start."
            )

    participant = models.EventParticipant(
        competition_id=payload.competition_id,
        participant_name=payload.participant_name,
        villa_number=payload.villa_number or (current_user.villa_number or "101"),
        category=payload.category or comp.category,
        phone_number=payload.phone_number,
        registration_source="VILLASHIELD_APP"
    )
    db.add(participant)
    db.commit()
    db.refresh(participant)
    return participant

@router.get("/competitions/{comp_id}/participants")
def get_competition_participants(comp_id: int, category: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(models.EventParticipant).filter(models.EventParticipant.competition_id == comp_id)
    if category and category.upper() != "ALL":
        query = query.filter(models.EventParticipant.category.ilike(f"%{category}%"))
    participants = query.all()
    return participants

@router.post("/competitions/{comp_id}/winners")
def declare_winners(comp_id: int, payload: schemas.WinnerPayload, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if current_user.role != models.UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Administrative privileges required to declare winners")

    comp = db.query(models.EventCompetition).filter(models.EventCompetition.id == comp_id).first()
    if not comp:
        raise HTTPException(status_code=404, detail="Target competition not found")

    # Clear previous leaderboard entries for this competition
    db.query(models.EventLeaderboard).filter(models.EventLeaderboard.competition_id == comp_id).delete()
    
    # Reset ranks for all participants in this competition
    db.query(models.EventParticipant).filter(models.EventParticipant.competition_id == comp_id).update({"rank": "NONE"})

    winners_summary = []

    # 1st Place - Winner (10 Points)
    if payload.winner_id:
        p1 = db.query(models.EventParticipant).filter(models.EventParticipant.id == payload.winner_id).first()
        if p1:
            p1.rank = "WINNER"
            lb1 = models.EventLeaderboard(
                event_id=comp.event_id,
                competition_id=comp_id,
                participant_id=p1.id,
                rank="WINNER",
                points=10
            )
            db.add(lb1)
            winners_summary.append({"rank": "WINNER", "name": p1.participant_name, "villa": p1.villa_number, "points": 10})

    # 2nd Place - 1st Runner Up (7 Points)
    if payload.runner_up_1_id:
        p2 = db.query(models.EventParticipant).filter(models.EventParticipant.id == payload.runner_up_1_id).first()
        if p2:
            p2.rank = "RUNNER_UP_1"
            lb2 = models.EventLeaderboard(
                event_id=comp.event_id,
                competition_id=comp_id,
                participant_id=p2.id,
                rank="RUNNER_UP_1",
                points=7
            )
            db.add(lb2)
            winners_summary.append({"rank": "RUNNER_UP_1", "name": p2.participant_name, "villa": p2.villa_number, "points": 7})

    # 3rd Place - 2nd Runner Up (5 Points)
    if payload.runner_up_2_id:
        p3 = db.query(models.EventParticipant).filter(models.EventParticipant.id == payload.runner_up_2_id).first()
        if p3:
            p3.rank = "RUNNER_UP_2"
            lb3 = models.EventLeaderboard(
                event_id=comp.event_id,
                competition_id=comp_id,
                participant_id=p3.id,
                rank="RUNNER_UP_2",
                points=5
            )
            db.add(lb3)
            winners_summary.append({"rank": "RUNNER_UP_2", "name": p3.participant_name, "villa": p3.villa_number, "points": 5})

    db.commit()
    return {"message": "Competition Winners Declared & Leaderboard Updated!", "winners": winners_summary}

@router.get("/{event_id}/leaderboard")
def get_event_leaderboard(event_id: int, db: Session = Depends(get_db)):
    entries = db.query(models.EventLeaderboard).filter(models.EventLeaderboard.event_id == event_id).all()
    results = []
    for entry in entries:
        participant = db.query(models.EventParticipant).filter(models.EventParticipant.id == entry.participant_id).first()
        competition = db.query(models.EventCompetition).filter(models.EventCompetition.id == entry.competition_id).first()
        if participant and competition:
            results.append({
                "participant_id": participant.id,
                "participant_name": participant.participant_name,
                "villa_number": participant.villa_number,
                "competition_title": competition.title,
                "category": participant.category,
                "rank": entry.rank,
                "points": entry.points
            })
    
    # Sort leaderboard by points descending
    results.sort(key=lambda x: x["points"], reverse=True)
    return results
