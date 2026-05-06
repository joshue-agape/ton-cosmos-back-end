import time
import stripe
import asyncio
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, WebSocket, WebSocketDisconnect, Request, Response
from pydantic import BaseModel

from app.database.deps import get_db
from app.core.config import settings
from app.core.websocket_manager import manager
from app.services.pdf_service import PDFService
from app.services.stripe_service import StripeService
from app.services.astrology_service import AstrologyService
from app.services.email_service import EmailService
from app.services.claude_service import AIService
from app.services.response_service import ServiceResponse
from app.repositories.order_repository import OrderRepository
from app.repositories.report_repository import ReportRepository
from app.schemas.order import OrderStatus
from app.schemas.report import ReportCreate

router = APIRouter()
logger = logging.getLogger(__name__)

# Configuration Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY
endpoint_secret = settings.STRIPE_WEBHOOK_SECRET
stripe.api_version = "2026-04-22.dahlia"

# Initialisation des services
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
        session = await stripe_service.create_checkout_session(
            plan_type=body.plan_type,
            amount_total=body.amount_total,
            order_id=body.order_id,
            user_email=body.email
        )
        
        return ServiceResponse.success(
            message="Session de paiement créée",
            data={"checkout_url": session.url, "session_id": session.id}
        )
    except Exception as e:
        logger.error(f"Erreur Stripe Session: {e}")
        return ServiceResponse.error(message="Erreur lors de la création du paiement", status_code=500)
   
        
@router.websocket("/ws/{session_id}")
async def websocket_endpoint_for_check_steps(websocket: WebSocket, session_id: str):
    await manager.connect(session_id, websocket)
    try:
        while True:
            await websocket.receive_text() 
    except WebSocketDisconnect:
        manager.disconnect(session_id, websocket)
        

@router.websocket("/order/ws/order-status-for-admin")
async def websocket_endpoint_for_check_new_event(websocket: WebSocket):
    admin_socket_session = "order-status-for-admin"
    await manager.connect(admin_socket_session, websocket)
    try:
        while True:
            await websocket.receive_text() 
    except WebSocketDisconnect:
        manager.disconnect(admin_socket_session, websocket)


async def process_order(order_id: int, stripe_session_id: str):
    async for db in get_db():
        order_repo = OrderRepository(db)
        report_repo = ReportRepository(db)
        
        admin_ws = "order-status-for-admin"
        socket_session_id = f"ton-cosmos-{order_id}"
        
        try:
            existing_order = await order_repo.get_by_stripe_session(stripe_session_id)
            
            if existing_order and existing_order.status == OrderStatus.COMPLETED:
                return

            order = await order_repo.get_by_id(order_id)
            
            if not order: 
                logger.error(f"Order {order_id} not found in DB")
                return

            start_time = asyncio.get_event_loop().time()
            await order_repo.update_status(order_id=order.id, status=OrderStatus.PROCESSING, stripe_session_id=stripe_session_id)
            await manager.send_update(admin_ws, {"order_id": order_id, "status": OrderStatus.PROCESSING})
            await manager.send_update(socket_session_id, {"step": 1, "status": True})

            report = await report_repo.create(ReportCreate(order_id=order.id, generation_duration=0))

            birth_dt = order.birth_date.replace(tzinfo=None)
            if order.birth_time:
                birth_dt = datetime.combine(birth_dt.date(), order.birth_time)

            chart = await astrology_service.get_full_chart(
                birth_date=birth_dt, 
                lat=order.latitude,
                lon=order.longitude
            )
            
            logger.info(f"CHART = {chart}")
            
            await report_repo.update_astral_data_json(report.id, chart)
            await manager.send_update(socket_session_id, {"step": 2, "status": True})

            sections = ["introduction", "piliers", "mental", "dominantes", "maisons_vie_1", 
                        "maisons_vie_2", "amour", "mission", "destin", "conseils", "synthese"]
            
            if order.plan_type.lower() == "complet":
                sections[8:8] = ["ombres", "aspects_majeurs", "predictions"]
            
            pause_event = asyncio.Event()
            pause_event.set()
            
            async def fetch_section(section_id, semaphore, chart, order):
                    max_retries = 10 
                    
                    for attempt in range(max_retries):
                        await pause_event.wait()

                        async with semaphore:
                            try:
                                print(f"Tentative ({attempt+1}) : {section_id}")
                                return await ai_service.generate_astrology_report(
                                    chart, order.full_name, section_id
                                )
                                
                            except Exception as e:
                                if "429" in str(e):
                                    if pause_event.is_set():
                                        pause_event.clear()
                                        print(f"Rate limit sur {section_id}. Pause de 5s...")
                                        await asyncio.sleep(5)
                                        pause_event.set()
                                    
                                    continue 

                                print(f"Erreur critique sur {section_id}: {e}")
                                return f"Données indisponibles ({section_id})"

                    return f"Timeout après plusieurs essais pour {section_id}"
            
            semaphore = asyncio.Semaphore(5)
            tasks = [fetch_section(s, semaphore, chart, order) for s in sections]
            final_sections = await asyncio.gather(*tasks)

            ai_content = {"sections": final_sections}
            await report_repo.update_ai_content_json(report.id, ai_content)
            await manager.send_update(socket_session_id, {"step": 3, "status": True})

            safe_name = order.full_name.replace(" ", "-") if order.full_name else "user"
            output_filename = f"report-{order.plan_type.lower()}-{safe_name}-{datetime.now().strftime('%Y%m%d')}.pdf"

            pdf_path = await pdf_service.generate_astrological_report(
                template_name="premium_report",
                data={
                    "full_name": order.full_name,
                    "birth_chart": chart.get("birth_chart", {}),
                    "ai_content": ai_content,
                    "birth_date_info": f"{order.birth_date} {order.birth_time}"
                },
                output_filename=output_filename
            )
                
            logger.info(f"PDF PATH = {pdf_path}")

            duration = round(asyncio.get_event_loop().time() - start_time, 2)
            await report_repo.finalize_pdf(report.id, pdf_path, output_filename, duration)
            await manager.send_update(socket_session_id, {"step": 4, "status": True})

            email_result = await email_service.send_email(
                to=order.email,
                subject="Ton Cosmos : Ton Rapport Astral est prêt !",
                template_name="report_ready",
                data={"full_name": order.full_name, "current_year": datetime.now().year},
                attachment_path=pdf_path
            )
                
            logger.info(f"EMAIL RESULT = {email_result}")

            if email_result.get("success"):
                logger.info(f"Email success")
                await order_repo.update_status(order.id, OrderStatus.COMPLETED)
                await manager.send_update(socket_session_id, {"step": 5, "status": True})
                await manager.send_update(admin_ws, {"order_id": order_id, "status": OrderStatus.COMPLETED})
            else:
                raise Exception(f"Email error: {email_result.get('message')}")

        except Exception as e:
            logger.error(f"CRITICAL ERROR [Order {order_id}]: {str(e)}")
            await order_repo.update_status(order_id, OrderStatus.FAILED)
            await manager.send_update(socket_session_id, {"step": 1, "status": False, "error": str(e)})
            if 'report' in locals():
                await report_repo.log_error(report.id, str(e))
        
        finally:
            await db.commit()
        
        break
    
    
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
        logger.error(f"Signature verification failed: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] != "checkout.session.completed":
        return {"status": "ignored"}

    session_obj = event["data"]["object"]
    session = session_obj.to_dict() 
    
    session_id = session.get("id")
    metadata = session.get("metadata", {})
    order_id = metadata.get("order_id")
    payment_status = session.get("payment_status")

    logger.info(f"DEBUG: Session={session_id} | Order={order_id} | Status={payment_status}")

    if not session_id or not order_id:
        logger.warning("Missing data: session_id or order_id in metadata")
        return {"status": "error", "message": "Missing order_id in metadata"}

    if payment_status != "paid":
        logger.info(f"Paiement non finalisé (Status: {payment_status})")
        return {"status": "not_paid"}

    try:
        logger.info(f"Validation commande {order_id} lancée en arrière-plan...")
        
        background_tasks.add_task(process_order, int(order_id), session_id)
        
    except ValueError:
        logger.error(f"Erreur: order_id '{order_id}' n'est pas un nombre valide.")
        return {"status": "invalid_id"}
    
    return Response(content="Webhook processed", status_code=200)


@router.post("/resend-email/{order_id}")
async def resend_email(order_id: int, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    order_repo = OrderRepository(db)
    
    order = await order_repo.get_by_id(order_id)
    if not order:
        return ServiceResponse.error(message="Commande non trouvée", status_code=404)

    background_tasks.add_task(process_resend_email, order_id)
    
    return ServiceResponse.success(message="Le processus de génération et d'envoi a été relancé.")


async def process_resend_email(order_id: int):
    async for db in get_db():
        order_repo = OrderRepository(db)
        report_repo = ReportRepository(db)
        
        admin_ws = "order-status-for-admin"
        socket_session_id = f"ton-cosmos-{order_id}"
        
        try:
            order = await order_repo.get_by_id(order_id)
            start_time = asyncio.get_event_loop().time()
            
            # Initialisation Rapport
            report = await report_repo.get_by_order_id(order_id=order_id)
            if not report:
                report = await report_repo.create(ReportCreate(order_id=order.id, generation_duration=0))

            # Update Status -> PROCESSING
            await order_repo.update_status(order_id=order.id, status=OrderStatus.PROCESSING)
            await manager.send_update(admin_ws, {"order_id": order_id, "status": OrderStatus.PROCESSING})
            await manager.send_update(socket_session_id, {"step": 1, "status": True})
            
            # --- ÉTAPE 1 : CHART ASTRALE ---
            chart = report.astral_data_json
            if not chart:
                birth_dt = order.birth_date.replace(tzinfo=None)
                if order.birth_time:
                    birth_dt = datetime.combine(birth_dt.date(), order.birth_time)

                chart = await astrology_service.get_full_chart(
                    birth_date=birth_dt, 
                    lat=order.latitude,
                    lon=order.longitude
                )
                await report_repo.update_astral_data_json(report.id, chart)
            
            await manager.send_update(socket_session_id, {"step": 2, "status": True})
                
            # --- ÉTAPE 2 : CONTENU IA ---
            ai_content = report.ai_content_json
            if not ai_content:
                sections = ["introduction", "piliers", "mental", "dominantes", "maisons_vie_1", 
                            "maisons_vie_2", "amour", "mission", "destin", "conseils", "synthese"]
                
                if order.plan_type.lower() == "complet":
                    sections[8:8] = ["ombres", "aspects_majeurs", "predictions"]

                pause_event = asyncio.Event()
                pause_event.set()
                
                async def fetch_section(section_id, semaphore, chart, order):
                        max_retries = 10 
                        
                        for attempt in range(max_retries):
                            await pause_event.wait()

                            async with semaphore:
                                try:
                                    print(f"Tentative ({attempt+1}) : {section_id}")
                                    return await ai_service.generate_astrology_report(
                                        chart, order.full_name, section_id
                                    )
                                    
                                except Exception as e:
                                    if "429" in str(e):
                                        if pause_event.is_set():
                                            pause_event.clear()
                                            print(f"Rate limit sur {section_id}. Pause de 5s...")
                                            await asyncio.sleep(5)
                                            pause_event.set()
                                        
                                        continue 

                                    print(f"Erreur critique sur {section_id}: {e}")
                                    return f"Données indisponibles ({section_id})"

                        return f"Timeout après plusieurs essais pour {section_id}"
                
                semaphore = asyncio.Semaphore(5)
                tasks = [fetch_section(s, semaphore, chart, order) for s in sections]
                final_sections = await asyncio.gather(*tasks)

                ai_content = {"sections": final_sections}
                await report_repo.update_ai_content_json(report.id, ai_content)
            
            await manager.send_update(socket_session_id, {"step": 3, "status": True})
                
            # --- ÉTAPE 3 : GÉNÉRATION PDF ---
            pdf_path = report.pdf_url
            if not pdf_path:
                safe_name = order.full_name.replace(" ", "-") if order.full_name else "user"
                output_filename = f"report-{order.plan_type.lower()}-{safe_name}-{datetime.now().strftime('%Y%m%d')}.pdf"

                pdf_path = await pdf_service.generate_astrological_report(
                    template_name="premium_report",
                    data={
                        "full_name": order.full_name,
                        "birth_chart": chart.get("birth_chart", {}),
                        "ai_content": ai_content,
                        "birth_date_info": f"{order.birth_date} {order.birth_time}"
                    },
                    output_filename=output_filename
                )
                duration = round(asyncio.get_event_loop().time() - start_time, 2)
                await report_repo.finalize_pdf(report.id, pdf_path, output_filename, duration)
                
            await manager.send_update(socket_session_id, {"step": 4, "status": True})
            
            # --- ÉTAPE 4 : ENVOI EMAIL ---
            email_result = await email_service.send_email(
                to=order.email,
                subject="Ton Cosmos : Ton Rapport Astral est prêt !",
                template_name="report_ready",
                data={"full_name": order.full_name, "current_year": datetime.now().year},
                attachment_path=pdf_path
            )
            
            if email_result.get("success"):
                await order_repo.update_status(order.id, OrderStatus.COMPLETED)
                await manager.send_update(socket_session_id, {"step": 5, "status": True})
                await manager.send_update(admin_ws, {"order_id": order_id, "status": OrderStatus.COMPLETED})
                await db.commit()
            else:
                raise Exception(f"Email error: {email_result.get('message')}")
        
        except Exception as e:
            await db.rollback()
            logger.error(f"CRITICAL ERROR [Order {order_id}]: {str(e)}")
            await order_repo.update_status(order_id, OrderStatus.FAILED)
            await manager.send_update(socket_session_id, {"step": 1, "status": False, "error": str(e)})
            await manager.send_update(admin_ws, {"order_id": order_id, "status": OrderStatus.FAILED})