import time
import stripe
from sqlalchemy.orm import Session
from app.database.deps import get_db
from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends, Response, Request
from app.core.config import settings
from pydantic import BaseModel
from app.services.pdf_service import *
from app.services.stripe_service import *
from app.services.astrology_service import *
from app.schemas.order import *
from app.services.email_service import *
from app.services.claude_service import AIService
from app.services.response_service import ServiceResponse
from app.repositories.order_repository import OrderRepository
from app.repositories.report_repository import ReportRepository
from app.services.response_service import ServiceResponse

router = APIRouter()
stripe.api_key = settings.STRIPE_SECRET_KEY
endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

ai_service = AIService()
pdf_service = PDFService()
email_service = EmailService()
stripe_service = StripeService()
astrology_service = AstrologyService()


# ================================
# SCHEMA
# ================================
class OrderRequest(BaseModel):
    plan_type: str
    order_id: int
    amount_total: int
    email: str


# ================================
# CREATE CHECKOUT
# ================================
@router.post("/create-checkout-session")
async def create_checkout(body: OrderRequest):
    try:
        session = stripe_service.create_checkout_session(
            plan_type=body.plan_type,
            amount_total=body.amount_total,
            order_id=body.order_id,
            user_email=body.email
        )
        
        return ServiceResponse.success(
            status_code=200,
            message="Checkout session created successfully",
            data={
                "checkout_url": session.url,
                "session_id": session.id
            }
        )

    except HTTPException as e:
        return ServiceResponse.error(
            status_code=e.status_code,
            message=str(e.detail),
            data=None
        )

    except Exception as e:
        return ServiceResponse.error(
            status_code=500,
            message="An internal server error occurred",
            data={"details": str(e)}
        )
        

# ================================
# BACKGROUND TASK
# ================================
async def process_order(order_id: int, session_id: str):
    db: Session = next(get_db())
    order_repo = OrderRepository(db)
    report_repo = ReportRepository(db)
    
    # Protection contre les traitements en double
    if order_repo.get_by_session_id(session_id):
        return

    start_time = time.perf_counter()
    order = order_repo.get_by_id(order_id)
    if not order:
        db.close()
        return

    # Initialisation du statut et du stripe_id
    order.stripe_session_id = session_id
    order_repo.update_status(order.id, OrderStatus.PROCESSING)
    
    # Création préventive du rapport pour le suivi admin
    report = report_repo.create(order.id)
    error_message = None

    try:
        # Préparation des données de naissance
        birth_datetime = order.birth_date.replace(tzinfo=None)
        if order.birth_time:
            birth_datetime = birth_datetime.replace(
                hour=order.birth_time.hour,
                minute=order.birth_time.minute,
                second=0, microsecond=0
            )

        # Moteur Astral & IA (Claude API)
        chart = astrology_service.get_full_chart(
            birth_date=birth_datetime, 
            lat=order.latitude,
            lon=order.longitude
        )

        ai_text = ai_service.generate_astrology_report(
            chart=chart, 
            full_name=order.full_name, 
            plan_type=order.plan_type
        )
        
        report_repo.update_content(report_id=report.id, astral_data=chart, ai_content=ai_text)

        # Génération PDF Premium
        safe_name = (order.full_name or "user").replace(" ", "-")
        timestamp = datetime.now().strftime("%Y%m%d")
        output_filename = f"report-{safe_name}-{timestamp}.pdf"

        pdf_path = pdf_service.generate_astrological_report(
            template_name="premium_report",
            data={
                "full_name": order.full_name,
                "birth_chart": chart,
                "ai_content": ai_text
            },
            output_filename=output_filename
        )
        
        duration = round(time.perf_counter() - start_time, 2)
        report_repo.finalize_pdf(
            report_id=report.id, 
            pdf_url=pdf_path, 
            pdf_name=output_filename, 
            duration=duration
        )
        
        email_data = {
            "full_name": order.full_name,
            "current_year": datetime.now().year
        }
        
        # Envoi Email (PDF en pièce jointe impératif)
        email_result = await email_service.send_email_with_attachment(
            to=order.email,
            subject="Ton Cosmos : Ton Rapport Astral est arrivé !",
            template_name="report_ready",
            data=email_data,
            attachment_path=pdf_path
        )
        
        if email_result["success"]:
            order_repo.update_status(order.id, OrderStatus.COMPLETED)
        else:
            error_message = f"Email failed: {email_result.get('message')}"
            order_repo.update_status(order.id, OrderStatus.FAILED)

        # Alerte si délai > 5 min (300s) selon CDC
        if duration > 300:
            print(f"ALERT: Generation took {duration}s for order {order_id}")

    except Exception as e:
        error_message = str(e)
        print(f"CRITICAL ERROR [Order {order_id}]: {error_message}")
        order_repo.update_status(order.id, OrderStatus.FAILED)
        
    finally:
        if error_message:
            report_repo.log_error(report.id, error_message)
        
        db.commit()
        db.close()
    
    
# ================================
# STRIPE WEBHOOK
# ================================
@router.post("/stripe/webhook")
async def stripe_webhook(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    order_repo = OrderRepository(db)
    report_repo = ReportRepository(db)

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            endpoint_secret
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] != "checkout.session.completed":
        return {"status": "ignored"}

    session = event["data"]["object"]

    session_id = session.get("id")
    order_id = session.get("metadata", {}).get("order_id")
    payment_status = session.get("payment_status")

    if not session_id or not order_id:
        raise HTTPException(status_code=400, detail="Invalid session data")

    if payment_status != "paid":
        return {"status": "not_paid"}

    print(f"Paiement confirmé pour commande {order_id}")

    background_tasks.add_task(process_order, int(order_id), session_id)

    return {"status": "success"}
