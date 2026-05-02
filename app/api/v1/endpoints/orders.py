import os
from sqlalchemy.orm import Session
from app.database.deps import get_db
from fastapi.responses import FileResponse
from fastapi import APIRouter, Depends, status
from app.repositories.order_repository import OrderRepository
from app.repositories.report_repository import ReportRepository

from app.schemas.order import *
from app.schemas.report import *

from app.services.astrology_service import *
from app.services.stripe_service import *
from app.services.email_service import *
from app.services.pdf_service import *

router = APIRouter()
stripe_service = StripeService()
astrology_service = AstrologyService()
pdf_service = PDFService()


# ================================================================================= #
""" Crée une nouvelle commande après la saisie du formulaire sur la landing page. """
@router.post("/create", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(body: OrderPayload, db: Session = Depends(get_db)):
    order_repo = OrderRepository(db)
    amount = 990 if body.plan_type == PlanType.ESSENTIEL else 1990
    
    order = order_repo.create({
        "email": body.email,
        "full_name": body.full_name,
        "birth_date": body.birth_date,
        "birth_time": body.birth_time,
        "birth_city": body.birth_city,
        "latitude": body.latitude,
        "longitude": body.longitude,
        "plan_type": body.plan_type,
        "amount_total": amount,
        "status": OrderStatus.PENDING_PAYMENT
    })
    
    return order


# ==================================================================== #
""" Récupère toutes les commandes pour le Dashboard Admin de Joseph. """
@router.get("/find-all")
def get_orders(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    repo = OrderRepository(db)
    return repo.get_all(skip=skip, limit=limit)


# ================================================================ #
""" Télécharge le rapport PDF associé à une commande via son ID. """
@router.get("/report/download/pdf-report/{order_id}")
def download_report(order_id: int, db: Session = Depends(get_db)):
    order_repo = OrderRepository(db)
    report_repo = ReportRepository(db)

    order = order_repo.get_by_id(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Commande introuvable")

    report = report_repo.get_by_order_id(order_id)
    if not report or not report.pdf_url:
        raise HTTPException(status_code=404, detail="PDF non disponible")

    file_path = report.pdf_url

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Fichier introuvable")

    return FileResponse(
        path=file_path,
        filename=report.pdf_name,
        media_type="application/pdf"
    )
    
