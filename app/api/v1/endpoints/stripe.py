import stripe
from fastapi import APIRouter, HTTPException
from app.core.config import settings
from pydantic import BaseModel, EmailStr
from datetime import datetime

router = APIRouter()
stripe.api_key = settings.STRIPE_SECRET_KEY

class OrderRequest(BaseModel):
    email: EmailStr
    plan_type: str
    amount_total: int

@router.post("/create-checkout-session")
async def create_checkout(order: OrderRequest):
    try:
        user_id_dummy = datetime.now().strftime("%Y%m%d%H%M%S")

        session = stripe.checkout.Session.create(
            customer_email=order.email,
            automatic_payment_methods={"enabled": True},
            mode="payment",
            
            metadata={
                "plan_type": order.plan_type,
                "user_id": user_id_dummy,
                "user_email": order.email
            },

            line_items=[
                {
                    "price_data": {
                        "currency": "eur",
                        "product_data": {
                            "name": f"Rapport astrologique ({order.plan_type})",
                        },
                        "unit_amount": order.amount_total,
                    },
                    "quantity": 1,
                }
            ],
            
            success_url=f"{settings.FRONTEND_URL}/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.FRONTEND_URL}/cancel",
        )
        
        return {"url": session.url, "id": session.id}
        
    except stripe.error.StripeError as e:
        print(f"Erreur Stripe: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Erreur interne: {e}")
        raise HTTPException(status_code=500, detail="Erreur serveur interne")