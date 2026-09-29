from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.models.models import UserRole, VisitorStatus, InviteStatus, PassType

class UserCreate(BaseModel):
    username: str
    password: str
    role: UserRole
    villa_number: Optional[str] = None
    villa_block: Optional[str] = None
    owner_name: Optional[str] = None

class UserOut(BaseModel):
    id: int
    username: str
    role: UserRole
    villa_number: Optional[str] = None
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class VisitorCreate(BaseModel):
    villa_id: int
    visitor_name: str
    phone_number: str
    vehicle_number: Optional[str] = None
    purpose: str
    gate_name: Optional[str] = "Main Gate"
    photo_url: Optional[str] = None

class VisitorOut(BaseModel):
    id: int
    villa_id: int
    visitor_name: str
    phone_number: str
    vehicle_number: Optional[str] = None
    purpose: str
    gate_name: Optional[str] = "Main Gate"
    photo_url: Optional[str] = None
    status: VisitorStatus
    created_at: datetime
    class Config:
        from_attributes = True

class VisitorAction(BaseModel):
    status: VisitorStatus

class StaffCreate(BaseModel):
    full_name: str
    role: str
    passcode: str

class StaffClockPayload(BaseModel):
    passcode: str

class InviteCreate(BaseModel):
    guest_name: str
    phone_number: Optional[str] = None
    duration_hours: Optional[int] = 12
    pass_type: Optional[PassType] = PassType.SINGLE
    max_uses: Optional[int] = 1

class InviteOut(BaseModel):
    id: int
    villa_id: int
    guest_name: str
    phone_number: Optional[str] = None
    otp_code: str
    valid_until: datetime
    pass_type: PassType
    max_uses: int
    current_uses: int
    status: InviteStatus
    created_at: datetime
    class Config:
        from_attributes = True

class OTPVerifyPayload(BaseModel):
    otp_code: str
    gate_name: Optional[str] = "Main Gate"

class EventCreate(BaseModel):
    title: str
    description: Optional[str] = None
    event_date: datetime
    venue: Optional[str] = "Community Hall"

class CompetitionCreate(BaseModel):
    title: str
    category: Optional[str] = "OPEN"
    coordinator_name: Optional[str] = None
    coordinator_phone: Optional[str] = None

class ParticipantCreate(BaseModel):
    competition_id: int
    participant_name: str
    villa_number: str
    category: Optional[str] = "OPEN"
    phone_number: Optional[str] = None

class WinnerPayload(BaseModel):
    winner_id: int
    runner_up_1_id: Optional[int] = None
    runner_up_2_id: Optional[int] = None

class PropertyInquiryCreate(BaseModel):
    visitor_name: str
    phone_number: str
    inquiry_type: Optional[str] = "RENT" # 'RENT' or 'PURCHASE'
    bhk_preference: Optional[str] = "3BHK" # '1BHK', '2BHK', '3BHK', 'VILLA'
    notes: Optional[str] = None

class GuardSOSCreate(BaseModel):
    gate_name: Optional[str] = "Main Gate"
    alert_type: Optional[str] = "INTRUDER_ALERT" # 'INTRUDER_ALERT', 'MEDICAL_EMERGENCY', 'HARASSMENT', 'GENERAL_DISTRESS'
    guard_username: Optional[str] = "guard1"
    notes: Optional[str] = None

