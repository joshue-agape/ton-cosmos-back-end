from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.order import Order, OrderStatus
from app.schemas.order import OrderCreate

class OrderRepository:
    def __init__(self, db: Session):
        self.db = db


    # ================================================== #
    """ Crée une nouvelle commande en base de données. """
    def create(self, order_data: OrderCreate) -> Order:
        db_order = Order(**order_data)
        self.db.add(db_order)
        self.db.commit()
        self.db.refresh(db_order)
        return db_order


    # ============================================ #
    """ Récupère une commande par son ID unique. """
    def get_by_id(self, order_id: int) -> Optional[Order]:
        return self.db.query(Order).filter(Order.id == order_id).first()


    # ======================================================= #
    """ Récupère une commande via son ID de session Stripe. """
    def get_by_stripe_session(self, session_id: str) -> Optional[Order]:
        return self.db.query(Order).filter(Order.stripe_session_id == session_id).first()


    # ============================================================ #
    """ Récupère l'historique des commandes pour un email donné. """
    def get_orders_by_email(self, email: str) -> List[Order]:
        return self.db.query(Order).filter(Order.email == email).all()


    # ============================================================ #
    """ Récupère la liste des commandes pour le Dashboard Admin. """
    def get_all(self, skip: int = 0, limit: int = 10000) -> List[Order]:
        return self.db.query(Order).offset(skip).limit(limit).all()


    # ========================================================================== #
    """ Met à jour le statut d'une commande (ex: passage à PAID après Stripe). """
    def update_status(self, order_id: int, status: OrderStatus) -> Optional[Order]:
        db_order = self.get_by_id(order_id)
        if db_order:
            db_order.status = status
            self.db.commit()
            self.db.refresh(db_order)
        return db_order
    