import stripe
from app.core.config import settings

stripe.api_key = settings.STRIPE_SECRET_KEY


# Service de gestion des paiements Stripe
class StripeService:
    @staticmethod
    def create_checkout_session(order_id: int, customer_email: str, plan_type: str, amount_total: int):
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="payment",

            customer_email=customer_email,

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

            success_url="https://tonsite.com/success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url="https://tonsite.com/cancel",

            metadata={
                "order_id": order_id
            }
        )

        return session