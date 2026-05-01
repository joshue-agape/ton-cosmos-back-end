from fastapi import APIRouter
from app.api.v1.endpoints import health, admin, orders, stripe

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])
api_router.include_router(orders.router, prefix="/order", tags=["Order"])
api_router.include_router(stripe.router, prefix="/stripe", tags=["Stripe"])

