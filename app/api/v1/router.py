from fastapi import APIRouter
from app.api.v1.endpoints import health, orders, stripe

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(orders.router, prefix="/order", tags=["Order"])
api_router.include_router(stripe.router, prefix="/stripe", tags=["Stripe"])

