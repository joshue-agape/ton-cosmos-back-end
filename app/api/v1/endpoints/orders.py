import os
from sqlalchemy.orm import Session
from app.database.deps import get_db
from fastapi.responses import FileResponse
from fastapi.encoders import jsonable_encoder
from fastapi import APIRouter, Depends, status, Request
from app.services.response_service import ServiceResponse
from app.repositories.order_repository import OrderRepository
from app.repositories.report_repository import ReportRepository
from app.repositories.admin_repository import AdminRepository

from app.schemas.order import *
from app.schemas.report import *

from app.services.utility_service import *
from app.services.astrology_service import *
from app.services.stripe_service import *
from app.services.email_service import *
from app.services.pdf_service import *

router = APIRouter()
jwt_service = JWTService()
stripe_service = StripeService()
astrology_service = AstrologyService()
pdf_service = PDFService()


def VerifyUser(request: Request, db: Session = Depends(get_db) ):
    admin_repo = AdminRepository(db)
    
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        return ServiceResponse.error("Jeton de rafraîchissement manquant", 401)
    
    refresh_payload = jwt_service.decode_token(refresh_token)
    
    if not refresh_payload or refresh_payload.get("type") != "refresh":
        return ServiceResponse.error(message="Jeton de rafraîchissement invalide", status_code=401)

    exp_timestamp = refresh_payload.get("exp")

    if not exp_timestamp:
        return ServiceResponse.error(message="Date d'expiration invalide", status_code=401)

    user_id = refresh_payload.get("sub")

    if not user_id:
        return ServiceResponse.error(message="Contenu du jeton invalide", status_code=401)
    
    try:
        user_id = int(user_id)
    except ValueError:
        return ServiceResponse.error(message="Identifiant utilisateur invalide", status_code=401)
    
    admin = admin_repo.get_by_id(user_id)

    if not admin:
        return ServiceResponse.error(message="Administrateur introuvable", status_code=404)
    

@router.post("/create", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(body: OrderPayload, db: Session = Depends(get_db)):
    order_repo = OrderRepository(db)
    amount = 990 if body.plan_type == PlanType.ESSENTIEL else 1990
    print(body)
    
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
    
    data_json = jsonable_encoder(order)
    
    return ServiceResponse.success(
        status_code=201,
        message="Order created successfully.",
        data=data_json
    )


@router.get("/find-all")
def get_orders(request: Request, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    VerifyUser(request=request, db=db)
    
    repo = OrderRepository(db)
    orders = repo.get_all(skip=skip, limit=limit)
    
    data_json = jsonable_encoder(orders)
    
    return ServiceResponse.success(
        status_code=200,
        data=data_json,
        message="Orders lists"
    )


@router.get("/find-all-with-report")
def get_orders_with_report(request: Request, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    VerifyUser(request=request, db=db)
    
    repo = OrderRepository(db)
    orders = repo.get_all_with_report(skip=skip, limit=limit)
    
    data_json = jsonable_encoder(orders)
    
    return ServiceResponse.success(
        status_code=200,
        data=data_json,
        message="Orders lists"
    )
    

@router.get("/report/download/pdf-report/{order_id}")
def download_report(order_id: int, request: Request, db: Session = Depends(get_db)):
    VerifyUser(request=request, db=db)
    
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
    
    
@router.get("/stats")
async def read_dashboard_stats(request: Request, db: Session = Depends(get_db)):
    VerifyUser(request=request, db=db)
    
    order_repo = OrderRepository(db)
    
    s = order_repo.get_dashboard_stats()
    
    stats = [
        {
            "label": "CA Aujourd'hui",
            "value": f"{s['today_revenue']:.2f}€",
            "icon": "Euro",
            "sub": f"{s['week_revenue']:.2f}€ cette semaine",
        },
        {
            "label": "CA Global",
            "value": f"{s['month_revenue']:.2f}€",
            "icon": "TrendingUp",
            "sub": f"Total: {s['total_revenue']:.2f}€",
        },
        {
            "label": "En cours",
            "value": str(s['processing_orders']),
            "icon": "Users",
            "sub": f"{s['total_paid']} ventes totales",
        },
        {
            "label": "Taux de livraison",
            "value": f"{s['delivery_rate']}%",
            "icon": "BarChart3",
            "sub": f"{s['failed_deliveries']} erreur(s) technique(s)",
            "alert": s['delivery_rate'] < 95 and s['total_paid'] > 0,
        },
    ]

    data_json = jsonable_encoder(stats)
    
    return ServiceResponse.success(
        status_code=200,
        message="Statistiques récupérées avec succès",
        data=data_json
    )
    

@router.delete("/delete/{order_id}")
async def delete_order(order_id: int, request: Request, db: Session = Depends(get_db)):
    VerifyUser(request=request, db=db)
    
    order_repo = OrderRepository(db)
    
    order = order_repo.get_by_id(order_id)
    if not order:
        return ServiceResponse.error(
            status_code=404,
            message="Commande introuvable",
            data=None
        )
    
    try:
        success = order_repo.delete_by_id(order_id)
        if not success:
             return ServiceResponse.error(
                status_code=500,
                message="Erreur lors de la suppression",
                data=None
            )
            
        return ServiceResponse.success(
            status_code=200,
            message=f"Commande {order_id} et documents associés supprimés avec succès",
            data=None
        )
    except Exception as e:
        return ServiceResponse.error(
            status_code=500,
            message=f"Erreur serveur : {str(e)}",
            data=None
        )
        
