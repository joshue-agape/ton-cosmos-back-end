import enum
from sqlalchemy import Column, Integer, String, DateTime, Enum, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.base import Base

class OrderStatus(str, enum.Enum):
    PENDING_PAYMENT = "pending_payment"
    PAID = "paid"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class PlanType(str, enum.Enum):
    ESSENTIEL = "essentiel" # 9,90€
    COMPLET = "complet"   # 19,90€
    
class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), index=True, nullable=False)
    
    # Données natales pour le rapport
    full_name = Column(String(255), nullable=False)
    birth_date = Column(DateTime, nullable=False)
    birth_time = Column(String(20), nullable=True)
    birth_city = Column(String(100), nullable=False)
    
    # Coordonnées géographiques pour calcul astral
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    
    # Intégration Stripe
    stripe_session_id = Column(String(255), unique=True, index=True, nullable=True)
    plan_type = Column(Enum(PlanType), nullable=False)
    status = Column(Enum(OrderStatus), default=OrderStatus.PENDING_PAYMENT)
    amount_total = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relations
    report = relationship("AstrologicalReport", back_populates="order", uselist=False, cascade="all, delete-orphan")