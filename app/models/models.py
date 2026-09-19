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

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    
    # Updated: Separating Villa tracking matrices cleanly
    villa_number = Column(String, nullable=True)
    villa_block = Column(String, nullable=True) # To store e.g., 'A', 'B', 'Soham', 'Pushpa'
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
    status = Column(Enum(VisitorStatus), default=VisitorStatus.PENDING)
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
 
