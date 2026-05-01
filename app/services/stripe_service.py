import stripe
from fastapi import HTTPException
from app.core.config import settings

stripe.api_key = settings.STRIPE_SECRET_KEY

class StripeService:
    @staticmethod
    def create_checkout_session(plan_type: str, amount_total: int, user_id: str = None):
        try:
            session = stripe.checkout.Session.create(
                mode="payment",
                payment_method_types=["card"],
                
                metadata={
                    "plan_type": plan_type,
                    "user_id": user_id
                },

                line_items=[
                    {
                        "price_data": {
                            "currency": "eur",
                            "product_data": {
                                "name": f"Rapport astrologique ({plan_type})",
                            },
                            "unit_amount": amount_total,
                        },
                        "quantity": 1,
                    }
                ],
                
                success_url=f"{settings.FRONTEND_URL}/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{settings.FRONTEND_URL}/landing",
            )
            return session
        
        except stripe.error.StripeError as e:
            print("STRIPE ERROR FULL =", repr(e))
            print("STRIPE ERROR MESSAGE =", getattr(e, "user_message", None))

            raise HTTPException(
                status_code=400,
                detail=str(e)
            )
        except Exception as e:
            print(f"Erreur interne: {e}")
            raise HTTPException(status_code=500, detail="Erreur serveur interne")
        