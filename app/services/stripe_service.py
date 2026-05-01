import stripe
from fastapi import HTTPException
from app.core.config import settings

stripe.api_key = settings.STRIPE_SECRET_KEY

class StripeService:
    @staticmethod
    def create_checkout_session(plan_type: str, amount_total: int, user_id: str = None):
        """
        Crée une session de paiement Stripe.
        amount_total doit être en centimes.
        """
        try:
            session = stripe.checkout.Session.create(
                # Les méthodes automatiques sont activées via le Dashboard Stripe
                automatic_payment_methods={"enabled": True},
                mode="payment",
                
                # Metadata : Très utile pour ton Webhook plus tard
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
                
                # Utilise les variables de ton config.settings pour plus de flexibilité
                success_url=f"{settings.FRONTEND_URL}/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{settings.FRONTEND_URL}/cancel",
            )
            return session
            
        except stripe.error.StripeError as e:
            # On log l'erreur et on lève une exception FastAPI
            print(f"Erreur Stripe: {e}")
            raise HTTPException(status_code=400, detail="Erreur lors de la création de la session de paiement")
        except Exception as e:
            print(f"Erreur interne: {e}")
            raise HTTPException(status_code=500, detail="Erreur serveur interne")
        