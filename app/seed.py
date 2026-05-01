import secrets
import hashlib
from datetime import datetime
from app.models.admin import Admin
from sqlalchemy.orm import Session
from app.core.config import settings
from app.database.session import SessionLocal
from app.services.utility_service import PasswordService

def seed_db():
    db: Session = SessionLocal()
    password_service = PasswordService()
    
    try:
        print("Début du seeding...")

        admin_email = settings.ADMIN_EMAIL
        admin = db.query(Admin).filter(Admin.email == admin_email).first()
        hashed_password = password_service.hash_password(settings.ADMIN_PASSWORD)
        
        raw_secret = f"{datetime.utcnow().timestamp()}-{secrets.token_hex(16)}"
        client_secret = hashlib.sha256(raw_secret.encode()).hexdigest()
        
        if not admin:
            admin = Admin(
                email=admin_email,
                hashed_password=hashed_password,
                client_secret=client_secret,
                failed_login_attempts=0,
            )
            db.add(admin)
            print(f"Admin '{admin_email}' créé.")
        else:
            print(f"Admin '{admin_email}' existe déjà.")

        db.commit()
        print("Seeding terminé avec succès !")

    except Exception as e:
        print(f"Erreur lors du seeding : {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_db()
    