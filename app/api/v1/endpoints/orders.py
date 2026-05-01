import time
from typing import List
from sqlalchemy.orm import Session
from app.database.deps import get_db
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
    start_time = time.perf_counter()
    order_repo = OrderRepository(db)
    report_repo = ReportRepository(db)
    
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
        "stripe_session_id": body.stripe_session_id,
        "amount_total": amount,
        "status": OrderStatus.PENDING_PAYMENT
    })
    
    # gérer heure inconnue
    birth_datetime = body.birth_date
    if body.birth_time:
        birth_datetime = birth_datetime.replace(
            hour=body.birth_time.hour,
            minute=body.birth_time.minute
        )

    chart = astrology_service.get_full_chart(
        birth_datetime,
        body.latitude,
        body.longitude
    )
    
    report = report_repo.create(order.id)
    report_repo.update_content(report.id, astral_data=chart, ai_content={})
    
    output_filename = f"report_{order.id}_{body.full_name.replace(' ', '_')}.pdf"
    pdf_path = pdf_service.generate_astrological_report(
        data={"full_name": body.full_name, "birth_chart": chart, "ai_content": {}},
        output_filename=output_filename
    )
    end_time = time.perf_counter()
    execution_duration = round(end_time - start_time, 2)
    
    report_repo.finalize_pdf(
        report_id=report.id,
        pdf_url=pdf_path,
        pdf_name=output_filename,
        duration=execution_duration
    )
    
    order_repo.update_status(order.id, OrderStatus.PROCESSING)
    db.refresh(order)

    return order


# ==================================================================== #
""" Récupère toutes les commandes pour le Dashboard Admin de Joseph. """
@router.get("/", response_model=List[OrderResponse])
def get_orders(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    repo = OrderRepository(db)
    return repo.get_all(skip=skip, limit=limit)

