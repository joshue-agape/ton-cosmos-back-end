import stripe
from fastapi import APIRouter, HTTPException
from app.core.config import settings
from pydantic import BaseModel
from app.services.stripe_service import *

router = APIRouter()
stripe.api_key = settings.STRIPE_SECRET_KEY

stripe_service = StripeService()

class OrderRequest(BaseModel):
    plan_type: str
    order_id: int
    amount_total: int


@router.post("/create-checkout-session")
async def create_checkout(body: OrderRequest):
    try:
        session = stripe_service.create_checkout_session(
            plan_type=body.plan_type,
            amount_total=body.amount_total,
            order_id=body.order_id
        )

        return {
            "success": True,
            "checkout_url": session.url,
            "session_id": session.id
        }

    except HTTPException as e:
        raise e

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
        