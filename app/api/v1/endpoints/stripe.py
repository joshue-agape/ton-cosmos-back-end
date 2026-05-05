import stripe
import time as time_module
from datetime import datetime
from sqlalchemy.orm import Session
from app.database.deps import get_db
from fastapi import APIRouter, BackgroundTasks, HTTPException, WebSocket, WebSocketDisconnect, Request, Response
from app.core.config import settings
from pydantic import BaseModel
from app.services.pdf_service import PDFService
from app.services.stripe_service import StripeService
from app.services.astrology_service import AstrologyService
from app.schemas.order import *
from app.services.email_service import EmailService
from app.services.claude_service import AIService
from app.services.response_service import ServiceResponse
from app.repositories.order_repository import OrderRepository
from app.repositories.report_repository import ReportRepository
from app.services.response_service import ServiceResponse
from app.core.websocket_manager import *

from app.schemas.report import *

router = APIRouter()
stripe.api_key = settings.STRIPE_SECRET_KEY
endpoint_secret = settings.STRIPE_WEBHOOK_SECRET
stripe.api_version = "2026-04-22.dahlia"

ai_service = AIService()
pdf_service = PDFService()
email_service = EmailService()
stripe_service = StripeService()
astrology_service = AstrologyService()


class OrderRequest(BaseModel):
    plan_type: str
    order_id: int
    amount_total: int
    email: str


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
        

@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(session_id, websocket)
    try:
        while True:
            await websocket.receive_text() 
    except WebSocketDisconnect:
        manager.disconnect(session_id)
        
        
async def process_order(order_id: int, session_id: str):
    db: Session = next(get_db())
    order_repo = OrderRepository(db)
    report_repo = ReportRepository(db)
    
    if order_repo.get_by_stripe_session(session_id):
        return
    
    start_time = time_module.perf_counter()
    
    order = order_repo.get_by_id(order_id)
    if not order:
        db.close()
        return

    order.stripe_session_id = session_id
    order_repo.update_status(order.id, OrderStatus.PROCESSING)
    
    await manager.send_update(session_id, { "step": 1, "status": True })
    
    report_data = ReportCreate(
        order_id=order.id,
        generation_duration=0
    )
    report = report_repo.create(report_data)
    error_message = None

    try:
        birth_datetime = order.birth_date.replace(tzinfo=None)
        if order.birth_time:
            birth_datetime = birth_datetime.replace(
                hour=order.birth_time.hour,
                minute=order.birth_time.minute,
                second=0, microsecond=0
            )

        chart = astrology_service.get_full_chart(
            birth_date=birth_datetime, 
            lat=order.latitude,
            lon=order.longitude
        )
        
        report_repo.update_astral_data_json(report_id=report.id, astral_data=chart)
        
        await manager.send_update(session_id, { "step": 2, "status": True })
        
        BASE_SECTIONS = [
            "introduction", 
            "piliers", 
            "mental", 
            "dominantes", 
            "maisons_vie_1", 
            "maisons_vie_2", 
            "amour", 
            "mission", 
            "destin",
            "conseils", 
            "synthese"
        ]

        EXTRA_COMPLETE = [
            "ombres", 
            "aspects_majeurs", 
            "predictions"
        ]

        if order.plan_type.lower() == "complet":
            sections_to_generate = BASE_SECTIONS[:-2] + EXTRA_COMPLETE + BASE_SECTIONS[-2:]
        else:
            sections_to_generate = BASE_SECTIONS
            
        final_report_sections = []
        
        for section_id in enumerate(sections_to_generate):
            print(f"STEP = {section_id}")

            section_json = ai_service.generate_astrology_report(chart, order.full_name, section_id)
            final_report_sections.append(section_json)

        ai_content_final = { "sections": final_report_sections }
        
        await manager.send_update(session_id, { "step": 3, "status": True })
        
        report_repo.update_ai_content_json(report_id=report.id, ai_content=ai_content_final)
        
        safe_name = (order.full_name or "user").replace(" ", "-")
        timestamp = datetime.now().strftime("%Y%m%d")
        output_filename = f"report-{safe_name}-{timestamp}.pdf"

        pdf_path = pdf_service.generate_astrological_report(
            template_name="premium_report",
            data={
                "full_name": order.full_name,
                "birth_chart": chart.get("birth_chart", {}),
                "ai_content": ai_content_final,
                "forecast": chart.get("forecast", []),
                "birth_date_info": f"{order.birth_date} {order.birth_time}",
                "current_date": datetime.now().strftime("%d/%m/%Y"),
                "chart_image_url": chart.get("chart_image_url", "")
            },
            output_filename=output_filename
        )
        
        duration = round(time_module.perf_counter() - start_time, 2)
        report_repo.finalize_pdf(
            report_id=report.id, 
            pdf_url=pdf_path, 
            pdf_name=output_filename, 
            duration=duration
        )
        
        await manager.send_update(session_id, { "step": 4, "status": True })
        
        email_data = {
            "full_name": order.full_name,
            "current_year": datetime.now().year
        }
        
        email_result = await email_service.send_email_with_attachment(
            to=order.email,
            subject="Ton Cosmos : Ton Rapport Astral est arrivé !",
            template_name="report_ready",
            data=email_data,
            attachment_path=pdf_path
        )
        
        if email_result["success"]:
            order_repo.update_status(order.id, OrderStatus.COMPLETED)
            
            await manager.send_update(session_id, { "step": 5, "status": True })
            
        else:
            error_message = f"Email failed: {email_result.get('message')}"
            order_repo.update_status(order.id, OrderStatus.FAILED)
            await manager.send_update(session_id, { "step": 5, "status": False })

        if duration > 300:
            print(f"ALERT: Generation took {duration}s for order {order_id}")

    except Exception as e:
        error_message = str(e)
        print(f"CRITICAL ERROR [Order {order_id}]: {error_message}")
        order_repo.update_status(order.id, OrderStatus.FAILED)
        await manager.send_update(session_id, { "step": 2, "status": False })
        
    finally:
        if error_message:
            report_repo.log_error(report.id, error_message)
        
        db.commit()
        db.close()
    
    
@router.post("/stripe/webhook")
async def stripe_webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            endpoint_secret
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] != "checkout.session.completed":
        return {"status": "ignored"}

    session_obj = event["data"]["object"]
    session = session_obj.to_dict() 
    
    session_id = session.get("id")
    metadata = session.get("metadata", {})
    order_id = metadata.get("order_id")
    payment_status = session.get("payment_status")

    print(f"DEBUG: Session={session_id} | Order={order_id} | Status={payment_status}")

    if not session_id or not order_id:
        return {"status": "error", "message": "Missing order_id in metadata"}

    if payment_status != "paid":
        print(f"Paiement non finalisé (Status: {payment_status})")
        return {"status": "not_paid"}

    try:
        print(f"Validation commande {order_id} en cours...")
        background_tasks.add_task(process_order, int(order_id), session_id)
    except ValueError:
        print(f"Erreur: order_id '{order_id}' n'est pas un nombre.")
        return {"status": "invalid_id"}
    
    return Response(status_code=200)

