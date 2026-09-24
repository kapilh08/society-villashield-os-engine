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
