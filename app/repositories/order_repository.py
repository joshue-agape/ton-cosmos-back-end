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

        paid_statuses = [OrderStatus.PAID, OrderStatus.PROCESSING, OrderStatus.COMPLETED]

        def get_revenue(start_date=None):
            query = self.db.query(func.sum(Order.amount_total)).filter(
                Order.status.in_(paid_statuses)
            )
            if start_date:
                query = query.filter(Order.created_at >= start_date)
            return query.scalar() or 0

        today_rev = get_revenue(today_start)
        week_rev = get_revenue(week_start)
        month_rev = get_revenue(month_start)
        total_rev = get_revenue()

        total_paid_count = self.db.query(func.count(Order.id)).filter(
            Order.status.in_(paid_statuses)
        ).scalar() or 0

        completed_count = self.db.query(func.count(Order.id)).filter(
            Order.status == OrderStatus.COMPLETED
        ).scalar() or 0

        processing_count = self.db.query(func.count(Order.id)).filter(
            Order.status.in_([OrderStatus.PAID, OrderStatus.PROCESSING])
        ).scalar() or 0

        failed_delivery_count = self.db.query(func.count(Order.id)).filter(
            Order.status == OrderStatus.FAILED
        ).scalar() or 0

        denominator = total_paid_count + failed_delivery_count
        delivery_rate = round((completed_count / denominator * 100), 1) if denominator > 0 else 0

        return {
            "today_revenue": today_rev / 100,
            "week_revenue": week_rev / 100,
            "month_revenue": month_rev / 100,
            "total_revenue": total_rev / 100,
            "total_paid": total_paid_count,
            "completed_orders": completed_count,
            "processing_orders": processing_count,
            "failed_deliveries": failed_delivery_count,
            "delivery_rate": delivery_rate
        }
        
        