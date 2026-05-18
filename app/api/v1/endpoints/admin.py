import secrets
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, BackgroundTasks, Depends, Response, Request

from app.database.deps import get_db
from app.core.config import settings
from app.schemas.admin import LoginPayload, ForgotPayload, ResetPayload, UpdatePasswordPayload
from app.services.email_service import EmailService
from app.services.utility_service import UtilsService, PasswordService
from app.services.utility_service import JWTService
from app.services.token_service import TokenService
from app.repositories.admin_repository import AdminRepository
from app.repositories.token_repository import TokenRepository
from app.services.response_service import ServiceResponse


router = APIRouter()
logger = logging.getLogger(__name__)

# Initialisation des services
service = UtilsService()
jwt_service = JWTService()
email_service = EmailService()
password_service = PasswordService()


@router.post("/login")
async def login(body: LoginPayload, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    admin_repo = AdminRepository(db)
    
    device = service.get_device(request=request)
    admin = await admin_repo.get_by_email(body.email)
    
    if not admin:
        return ServiceResponse.error(message="Email invalide", status_code=401, data={"error": "email"})
        
    if not password_service.verify_password(body.password, admin.hashed_password):
        return ServiceResponse.error(message="Mot de passe incorrect", status_code=401, data={"error": "password"})
    
    # Mise à jour des stats de login
    await admin_repo.update_login_stats(
        admin_id=admin.id,
        device=device.get("device"),
        ip=device.get("IP")
    )

    access_token = jwt_service.create_access_token(
        user_id=admin.id,
        email=admin.email,
        secret_key=admin.client_secret
    )
    
    refresh_token = jwt_service.create_refresh_token(
        user_id=admin.id, 
        email=admin.email, 
        remember=body.remember_me if body.remember_me else False
    )
    
    # Configuration du Cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.ENV == 'production',
        samesite="none",
        max_age=7 * 24 * 60 * 60 if body.remember_me else 24 * 60 * 60,
    )

    return {
        "status_code": 200,
        "success": True,
        "message": "Connexion réussie",
        "data": {
            "access_token": access_token,
            "token_type": "bearer"
        }
    }


@router.post("/logout")
async def logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    admin_repo = AdminRepository(db)
    token_repo = TokenRepository(db)
    token_service = TokenService(token_repo)
    
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        return ServiceResponse.error("Refresh token manquant", 401)
    
    refresh_payload = jwt_service.decode_token(refresh_token)
    if not refresh_payload or refresh_payload.get("type") != "refresh":
        response.delete_cookie("refresh_token", path="/")
        return ServiceResponse.error("Token invalide", 401)
    
    try:
        user_id = int(refresh_payload.get("sub"))
        expire_at = datetime.fromtimestamp(refresh_payload.get("exp"), tz=timezone.utc)
        
        if settings.ENV == "production":
            await token_service.revoque_token(
                user_id=user_id,
                token=refresh_token,
                token_type="refresh",
                exp=expire_at
            )
    except Exception as e:
        logger.error(f"Erreur lors du logout : {e}")

    response.delete_cookie("refresh_token", path="/")
    return {"success": True, "status_code": 200, "message": "Déconnexion réussie"}


@router.post("/refresh-token")
async def refresh_token_route(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    admin_repo = AdminRepository(db)
    token_repo = TokenRepository(db)
    token_service = TokenService(token_repo)
    
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        return ServiceResponse.error("Refresh token manquant", 401)
    
    payload = jwt_service.decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        return ServiceResponse.error("Token invalide", 401)

    user_id = int(payload.get("sub"))
    expire_ts = payload.get("exp")
    expire_dt = datetime.fromtimestamp(expire_ts, tz=timezone.utc)
    
    if expire_dt <= datetime.now(timezone.utc):
        response.delete_cookie("refresh_token", path="/")
        return ServiceResponse.error("Token expiré", 401)
    
    user = await admin_repo.get_by_id(user_id)
    if not user:
        return ServiceResponse.error("Utilisateur non trouvé", 404)
        
    # Création des nouveaux tokens
    new_access = jwt_service.create_access_token(user_id=user.id, email=user.email, secret_key=user.client_secret)
    new_refresh = jwt_service.create_new_refresh_token(user_id=user.id, email=user.email, expire=expire_dt)
    
    max_age = int((expire_dt - datetime.now(timezone.utc)).total_seconds())
    
    response.set_cookie(
        key="refresh_token",
        value=new_refresh,
        httponly=True,
        secure=settings.ENV == 'production',
        samesite="lax",
        max_age=max_age,
        path="/"
    )

    return {
        "success": True,
        "message": "Token actualisé",
        "data": {"access_token": new_access, "token_type": "bearer"}
    }


@router.post("/forgot-password")
async def forgot_password(body: ForgotPayload, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    admin_repo = AdminRepository(db)
    admin = await admin_repo.get_by_email(body.email)
    
    msg = "Si un compte avec cet email existe, un lien de réinitialisation a été envoyé."
    
    if not admin:
        return ServiceResponse.success(message=msg)
    
    fp_token = secrets.token_urlsafe(32)
    fp_expire = datetime.now(timezone.utc) + timedelta(minutes=15)

    await admin_repo.set_reset_token(email=body.email, token=fp_token, expires_at=fp_expire)

    reset_link = f"{settings.FRONTEND_URL}/eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9/YXV0aC9yZXNldC1wYXNzd29yZA?token={fp_token}"
    
    background_tasks.add_task(
        email_service.send_email,
        to=admin.email,
        subject="Réinitialisation de votre mot de passe",
        template_name="reset_password",
        data={
            "full_name": "Système JVN Lab - Ton Cosmos",
            "reset_link": reset_link,
            "current_year": datetime.now().year
        }
    )
    
    return ServiceResponse.success(message=msg)


@router.get("/verify-reset-token")
async def verify_reset_token(token: str, db: AsyncSession = Depends(get_db)):
    admin_repo = AdminRepository(db)
    admin = await admin_repo.get_by_reset_token(token)
    
    if not admin:
        return ServiceResponse.error(
            message="Ce lien de réinitialisation est invalide ou a déjà été utilisé.",
            status_code=404
        )
    
    if admin.reset_password_token_expires_at < datetime.now(timezone.utc):
        return ServiceResponse.error(
            message="Ce lien a expiré. Merci de renouveler votre demande.",
            status_code=400
        )
    
    return ServiceResponse.success("Jeton valide.")


@router.put("/reset-password")
async def reset_password_finish(body: ResetPayload, db: AsyncSession = Depends(get_db)):
    admin_repo = AdminRepository(db)
    admin = await admin_repo.get_by_reset_token(body.token)
    
    if not admin:
        return ServiceResponse.error(
            message="Ce lien de réinitialisation est invalide ou a déjà été utilisé.",
            status_code=400
        )
    
    if admin.reset_password_token_expires_at < datetime.now(timezone.utc):
        return ServiceResponse.error(
            message="Ce lien a expiré. Merci de renouveler votre demande.",
            status_code=400
        )
    
    new_hashed = password_service.hash_password(body.new_password)
    await admin_repo.update_password(admin_id=admin.id, new_hashed_password=new_hashed)
    
    return ServiceResponse.success("Mot de passe mis à jour.")


@router.patch("/update-password")
async def update_password(body: UpdatePasswordPayload, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    admin_repo = AdminRepository(db)
    
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        return ServiceResponse.error("Non autorisé", 401)
    
    payload = jwt_service.decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        return ServiceResponse.error("Session invalide", 401)

    user_id = int(payload.get("sub"))
    expire_ts = payload.get("exp")
    expire_dt = datetime.fromtimestamp(expire_ts, tz=timezone.utc)
    
    if expire_dt <= datetime.now(timezone.utc):
        response.delete_cookie("refresh_token", path="/")
        return ServiceResponse.error("Token expiré", 401)
    
    admin = await admin_repo.get_by_id(user_id)

    if not admin:
        return ServiceResponse.error("Utilisateur non trouvé", 404)
    
    if not password_service.verify_password(body.old_password, admin.hashed_password):
        return ServiceResponse.error("Ancien mot de passe incorrect.", 401)
    
    new_hashed = password_service.hash_password(body.new_password)
    await admin_repo.update_password(admin_id=admin.id, new_hashed_password=new_hashed)
    
    return ServiceResponse.success("Mot de passe mis à jour avec succès.")
