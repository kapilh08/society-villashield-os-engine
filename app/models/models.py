import enum
import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Boolean
from sqlalchemy.orm import relationship
from app.database import Base

class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    RESIDENT = "RESIDENT"
    GUARD = "GUARD"

class VisitorStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DENIED = "DENIED"

class InviteStatus(str, enum.Enum):
    PENDING = "PENDING"
    USED = "USED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"

class PassType(str, enum.Enum):
    SINGLE = "SINGLE"
    EVENT_GROUP = "EVENT_GROUP"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    
    # Villa tracking fields
    villa_number = Column(String, nullable=True)
    villa_block = Column(String, nullable=True) # e.g., 'A', 'B', 'Soham', 'Pushpa'
    owner_name = Column(String, nullable=True)  # Full name for guard search lookups
    
    fcm_token = Column(String, nullable=True)

class VisitorLog(Base):
    __tablename__ = "visitor_logs"
    id = Column(Integer, primary_key=True, index=True)
    villa_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    visitor_name = Column(String, nullable=False)
    phone_number = Column(String, nullable=False)
    vehicle_number = Column(String, nullable=True)
    purpose = Column(String, nullable=False)
    gate_name = Column(String, default="Main Gate", nullable=False)
    photo_url = Column(String, nullable=True)
    status = Column(Enum(VisitorStatus), default=VisitorStatus.PENDING)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class PreApprovedInvite(Base):
    __tablename__ = "pre_approved_invites"
    id = Column(Integer, primary_key=True, index=True)
    villa_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    guest_name = Column(String, nullable=False)
    phone_number = Column(String, nullable=True)
    otp_code = Column(String, unique=True, index=True, nullable=False) # e.g., '8492'
    valid_until = Column(DateTime, nullable=False)
    pass_type = Column(Enum(PassType), default=PassType.SINGLE, nullable=False)
    max_uses = Column(Integer, default=1, nullable=False)
    current_uses = Column(Integer, default=0, nullable=False)
    status = Column(Enum(InviteStatus), default=InviteStatus.PENDING)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class DomesticStaff(Base):
    __tablename__ = "domestic_staff"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    role = Column(String, nullable=False)
    passcode_hash = Column(String, unique=True, nullable=False)
    is_active = Column(Boolean, default=True)

class StaffAttendance(Base):
    __tablename__ = "staff_attendance"
    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("domestic_staff.id"), nullable=False)
    check_in = Column(DateTime, default=datetime.datetime.utcnow)
    check_out = Column(DateTime, nullable=True)

class EventStatus(str, enum.Enum):
    UPCOMING = "UPCOMING"
    LIVE = "LIVE"
    COMPLETED = "COMPLETED"

class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    event_date = Column(DateTime, nullable=False)
    venue = Column(String, default="Community Hall")
    status = Column(Enum(EventStatus), default=EventStatus.UPCOMING)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class EventCompetition(Base):
    __tablename__ = "event_competitions"
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    title = Column(String, nullable=False)
    category = Column(String, default="OPEN")
    coordinator_name = Column(String, nullable=True)
    coordinator_phone = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class EventParticipant(Base):
    __tablename__ = "event_participants"
    id = Column(Integer, primary_key=True, index=True)
    competition_id = Column(Integer, ForeignKey("event_competitions.id"), nullable=False)
    participant_name = Column(String, nullable=False)
    villa_number = Column(String, nullable=False)
    category = Column(String, default="OPEN")
    phone_number = Column(String, nullable=True)
    registration_source = Column(String, default="VILLASHIELD_APP")
    rank = Column(String, default="NONE") # 'NONE', 'WINNER', 'RUNNER_UP_1', 'RUNNER_UP_2'
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class EventLeaderboard(Base):
    __tablename__ = "event_leaderboard"
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    competition_id = Column(Integer, ForeignKey("event_competitions.id"), nullable=False)
    participant_id = Column(Integer, ForeignKey("event_participants.id"), nullable=False)
    rank = Column(String, nullable=False) # 'WINNER', 'RUNNER_UP_1', 'RUNNER_UP_2'
    points = Column(Integer, default=0) # 10 (Winner), 7 (Runner 1), 5 (Runner 2)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

