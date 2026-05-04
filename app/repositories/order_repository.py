from typing import List, Optional
from sqlalchemy import func
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, joinedload
from app.models.order import Order, OrderStatus
from app.schemas.order import OrderCreate

class OrderRepository:
    def __init__(self, db: Session):
        self.db = db


    def create(self, order_data: OrderCreate) -> Order:
        db_order = Order(**order_data)
        self.db.add(db_order)
        self.db.commit()
        self.db.refresh(db_order)
        return db_order
    
    
    def update(self, order_id: int, order_data) -> Order:
        db_order = self.db.query(Order).filter(Order.id == order_id).first()

        if not db_order:
            return None

        for key, value in order_data.dict(exclude_unset=True).items():
            setattr(db_order, key, value)

        self.db.commit()
        self.db.refresh(db_order)

        return db_order


    def get_by_id(self, order_id: int) -> Optional[Order]:
        return self.db.query(Order).filter(Order.id == order_id).first()


    def get_by_stripe_session(self, session_id: str) -> Optional[Order]:
        return self.db.query(Order).filter(Order.stripe_session_id == session_id).first()


    def get_orders_by_email(self, email: str) -> List[Order]:
        return self.db.query(Order).filter(Order.email == email).all()
    

    def get_all(self) -> List[Order]:
        return self.db.query(Order).order_by(Order.created_at.desc()).all()


    def get_all_with_report(self) -> List[Order]:
        return (
            self.db.query(Order)
            .options(joinedload(Order.report))
            .order_by(Order.created_at.desc())
            .all()
        )


    def update_status(self, order_id: int, status: OrderStatus) -> Optional[Order]:
        db_order = self.get_by_id(order_id)
        if db_order:
            db_order.status = status
            self.db.commit()
            self.db.refresh(db_order)
        return db_order
    
    
    def get_dashboard_stats(self):
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=now.weekday())
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Revenus Aujourd'hui
        today_rev = self.db.query(func.sum(Order.amount_total)).filter(
            Order.status == OrderStatus.PAID, 
            Order.created_at >= today_start
        ).scalar() or 0

        # Revenus Semaine
        week_rev = self.db.query(func.sum(Order.amount_total)).filter(
            Order.status == OrderStatus.PAID, 
            Order.created_at >= week_start
        ).scalar() or 0

        # Revenus Mois
        month_rev = self.db.query(func.sum(Order.amount_total)).filter(
            Order.status == OrderStatus.PAID, 
            Order.created_at >= month_start
        ).scalar() or 0

        # Total historique
        total_rev = self.db.query(func.sum(Order.amount_total)).filter(
            Order.status == OrderStatus.PAID
        ).scalar() or 0

        # Stats de volume et livraison
        total_count = self.db.query(func.count(Order.id)).scalar() or 0
        completed_count = self.db.query(func.count(Order.id)).filter(
            Order.status == OrderStatus.COMPLETED
        ).scalar() or 0
        failed_count = self.db.query(func.count(Order.id)).filter(
            Order.status == OrderStatus.FAILED
        ).scalar() or 0
        
        return {
            "today_revenue": today_rev / 100,
            "week_revenue": week_rev / 100,
            "month_revenue": month_rev / 100,
            "total_revenue": total_rev / 100,
            "total_orders": total_count,
            "completed_orders": completed_count,
            "failed_orders": failed_count,
            "delivery_rate": round((completed_count / total_count * 100), 1) if total_count > 0 else 0
        }