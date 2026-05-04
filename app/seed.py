import secrets
import hashlib
from datetime import datetime
from app.models.admin import Admin
from sqlalchemy.orm import Session
from app.core.config import settings
from app.database.session import SessionLocal
from app.services.utility_service import PasswordService

def seed_db():
    """
    Fonction pour initialiser la base de données avec un compte administrateur par défaut.
    Pratique pour le premier déploiement ou pour réinitialiser l'accès.
    """
    db: Session = SessionLocal()
    password_service = PasswordService()
    
    try:
        print("Lancement de la procédure d'initialisation des données...")

        # On récupère les identifiants depuis nos variables d'environnement pour plus de sécurité
        admin_email = settings.ADMIN_EMAIL
        
        # On vérifie si l'admin n'existe pas déjà pour éviter les doublons
        admin = db.query(Admin).filter(Admin.email == admin_email).first()
        
        if not admin:
            # On prépare le mot de passe hashé
            hashed_password = password_service.hash_password(settings.ADMIN_PASSWORD)
            
            # Génération d'un 'client_secret' unique pour cet admin
            # On mélange un timestamp, un token aléatoire et on passe le tout au mixeur SHA-256
            raw_secret = f"{datetime.utcnow().timestamp()}-{secrets.token_hex(16)}"
            client_secret = hashlib.sha256(raw_secret.encode()).hexdigest()
        
            # Si l'admin n'existe pas, on crée son profil complet
            admin = Admin(
                email=admin_email,
                hashed_password=hashed_password,
                client_secret=client_secret,
                failed_login_attempts=0,
            )
            
            db.add(admin)
            
            print(f"Succès : Le compte administrateur '{admin_email}' a été créé.")
            
        else:
            # Petit message informatif si tout est déjà en place
            print(f"Info : L'administrateur '{admin_email}' est déjà présent en base de données.")

        db.commit()
        print("Opération de seeding terminée sans encombre !")

    except Exception as e:
        # En cas de pépin, on annule tout pour ne pas laisser la base dans un état instable
        print(f"Oups, une erreur est survenue pendant le seeding : {e}")
        db.rollback()
        
    finally:
        # On n'oublie jamais de libérer la connexion à la base de données
        db.close()

if __name__ == "__main__":
    seed_db()
    