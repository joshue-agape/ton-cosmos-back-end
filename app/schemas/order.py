from pydantic import BaseModel, EmailStr
from datetime import datetime, time
from typing import Optional, List
from app.models.order import OrderStatus, PlanType

class OrderPayload(BaseModel):
    email: EmailStr
    full_name: str
    birth_date: datetime
    birth_time: Optional[time] = None
    birth_city: str
    latitude: float
    longitude: float
    plan_type: PlanType
    

class PaidPayload(BaseModel):
    session_id: str
    order_id: int
    

class OrderCreate(BaseModel):
    email: EmailStr
    full_name: str
    birth_date: datetime
    birth_time: Optional[str] = None
    birth_city: str
    latitude: float
    longitude: float
    plan_type: PlanType
    amount_total: int
    status: str


class OrderResponse(BaseModel):
    id: int
    email: str
    status: OrderStatus
    plan_type: PlanType
    amount_total: int
    created_at: datetime

    class Config:
        from_attributes = True