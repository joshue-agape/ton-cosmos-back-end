import secrets
import logging
from math import ceil
from fastapi.responses import JSONResponse
from jose import jwt, JWTError, ExpiredSignatureError
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

service = UtilsService()
jwt_service = JWTService()
email_service = EmailService()
password_service = PasswordService()

MAX_FAILED_ATTEMPTS = 5
LOCK_TIME_MINUTES = 15

@router.post("/login")
async def login(body: LoginPayload, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    admin_repo = AdminRepository(db)
    
    device = service.get_device(request=request)
    current_ip = device.get("IP") or request.client.host
    admin = await admin_repo.get_by_email(body.email)
    
    if not admin:
        return ServiceResponse.error(message="Email invalide", status_code=401, data={"error": "email"})
    
    now = datetime.now(timezone.utc) if admin.locked_until and admin.locked_until.tzinfo else datetime.now()
    if admin.locked_until and admin.locked_until > now:
        remaining_time = ceil((admin.locked_until - now).total_seconds() / 60)
        return ServiceResponse.error(
            message=f"Compte temporairement bloqué (Origine: {admin.failed_attempts_ip}). Réessaie dans {remaining_time} minute(s).", 
            status_code=423, 
            data={"error": "locked"}
        )
        
    if not password_service.verify_password(body.password, admin.hashed_password):
        await admin_repo.increment_failed_attempts(body.email)
        current_attempts = admin.failed_attempts + 1
        if current_attempts >= MAX_FAILED_ATTEMPTS:
            lock_target = now + timedelta(minutes=LOCK_TIME_MINUTES)
            
            await admin_repo.lock_account(admin.id, lock_target, current_ip)
            await db.commit()
            
            logger.warning(f"CRITICAL: Compte {body.email} BLOQUÉ pour {LOCK_TIME_MINUTES}min. Cause: 5 échecs depuis l'IP {current_ip}")
            
            return ServiceResponse.error(
                message=f"Trop de tentatives. Compte bloqué pour {LOCK_TIME_MINUTES} minutes.", 
                status_code=423, 
                data={"error": "locked"}
            )
            
        await db.commit()
        return ServiceResponse.error(message="Mot de passe incorrect", status_code=401, data={"error": "password"})
    
    # Mise à jour des stats de login
    await admin_repo.update_login_stats(
        admin_id=admin.id,
        device=device.get("device"),
        ip=device.get("IP")
    )
    await db.commit()

    access_token = jwt_service.create_access_token(
        user_id=admin.id,
        email=admin.email
    )
    
    refresh_token = jwt_service.create_refresh_token(
        user_id=admin.id, 
        email=admin.email,
        secret_key=admin.client_secret,
        remember=body.remember_me if body.remember_me else False
    )
    
    response = JSONResponse(
        content={
            "status_code": 200,
            "success": True,
            "message": "Connexion réussie",
            "data": {
                "access_token": access_token,
                "token_type": "bearer"
            }
        }
    )
    
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.ENV == "production",
        samesite="lax" if settings.ENV == "development" else "none",
        max_age=7 * 24 * 60 * 60 if body.remember_me else 24 * 60 * 60,
        path="/"
    )
    
    return response


@router.post("/logout")
async def logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    token_repo = TokenRepository(db)
    token_service = TokenService(token_repo)
    admin_repo = AdminRepository(db)

    def clear_cookie():
        response.delete_cookie(
            key="refresh_token",
            path="/",
            httponly=True,
            samesite="lax" if settings.ENV == "development" else "none",
        )

    auth_header = request.headers.get("Authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        clear_cookie()
        return ServiceResponse.error("Missing access token", 401)

    access_token = auth_header.split(" ")[1]

    access_payload = None

    try:
        access_payload = jwt.decode(
            access_token,
            settings.JWT_SECRET_KEY,
            algorithms=["HS256"]
        )
    except (ExpiredSignatureError, JWTError):
        access_payload = None

    if access_payload and access_payload.get("type") == "access":
        exp = datetime.fromtimestamp(access_payload["exp"], tz=timezone.utc)

        await token_service.revoke_token(
            user_id=int(access_payload["sub"]),
            token=access_token,
            token_type="access",
            exp=exp
        )

    refresh_token = request.cookies.get("refresh_token")

    if not refresh_token:
        clear_cookie()
        return ServiceResponse.success(
            message="Already logged out",
            status_code=200
        )

    try:
        refresh_payload = jwt.decode(
            refresh_token,
            settings.JWT_SECRET_KEY,
            algorithms=["HS256"],
            options={"verify_signature": False}
        )
    except Exception:
        clear_cookie()
        return ServiceResponse.success("Logged out")

    if refresh_payload.get("type") != "refresh":
        clear_cookie()
        return ServiceResponse.error("Invalid token type", 401)

    user_id = int(refresh_payload.get("sub"))
    exp = datetime.fromtimestamp(refresh_payload.get("exp"), tz=timezone.utc)

    user = await admin_repo.get_by_id(user_id)

    if not user:
        clear_cookie()
        return ServiceResponse.success("Logged out")

    try:
        jwt.decode(
            refresh_token,
            user.client_secret,
            algorithms=["HS256"]
        )
    except (JWTError, ExpiredSignatureError):
        clear_cookie()
        return ServiceResponse.success("Logged out")

    is_revoked = await token_service.is_token_revoked(refresh_token)

    if not is_revoked:
        await token_service.revoke_token(
            user_id=user.id,
            token=refresh_token,
            token_type="refresh",
            exp=exp
        )

    clear_cookie()

    return {
        "success": True,
        "status_code": 200,
        "message": "Logout successful"
    }


@router.post("/refresh-token")
async def refresh_token_route(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    admin_repo = AdminRepository(db)
    token_repo = TokenRepository(db)
    token_service = TokenService(token_repo)

    auth_header = request.headers.get("Authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        return ServiceResponse.error("Missing access token", 401)

    access_token = auth_header.split(" ")[1]

    access_payload = None
    access_expired = False

    try:
        access_payload = jwt.decode(
            access_token,
            settings.JWT_SECRET_KEY,
            algorithms=["HS256"]
        )
    except ExpiredSignatureError:
        access_expired = True
    except JWTError:
        access_expired = True

    if access_payload and not access_expired:
        return ServiceResponse.success(
            message="Access token still valid",
            data={"access_token": access_token}
        )

    refresh_token = request.cookies.get("refresh_token")

    if not refresh_token:
        return ServiceResponse.error("Refresh token missing", 401)

    try:
        refresh_payload = jwt.decode(
            refresh_token,
            settings.JWT_SECRET_KEY,
            algorithms=["HS256"],
            options={"verify_signature": False}
        )
    except Exception:
        return ServiceResponse.error("Invalid refresh token", 401)

    if refresh_payload.get("type") != "refresh":
        return ServiceResponse.error("Invalid token type", 401)

    user_id = int(refresh_payload.get("sub"))

    user = await admin_repo.get_by_id(user_id)

    if not user:
        return ServiceResponse.error("User not found", 404)

    try:
        refresh_payload = jwt.decode(
            refresh_token,
            user.client_secret,
            algorithms=["HS256"]
        )
    except ExpiredSignatureError:
        return ServiceResponse.error("Session expired (refresh token)", 401)
    except JWTError:
        return ServiceResponse.error("Invalid refresh token", 401)

    is_revoked = await token_service.is_token_revoked(refresh_token)
    if is_revoked:
        response.delete_cookie("refresh_token", path="/")
        return ServiceResponse.error("Session revoked", 401)

    new_access = jwt_service.create_access_token(
        user_id=user.id,
        email=user.email
    )

    new_refresh = jwt_service.create_new_refresh_token(
        user_id=user.id,
        email=user.email,
        secret_key=user.client_secret,
        expire=datetime.fromtimestamp(refresh_payload["exp"], tz=timezone.utc)
    )

    await token_service.revoke_token(
        user_id=user.id,
        token=refresh_token,
        token_type="refresh",
        exp=datetime.fromtimestamp(refresh_payload["exp"], tz=timezone.utc)
    )
    
    expire_dt = datetime.fromtimestamp(refresh_payload["exp"], tz=timezone.utc)
    max_age = int((expire_dt - datetime.now(timezone.utc)).total_seconds())

    response.set_cookie(
        key="refresh_token",
        value=new_refresh,
        httponly=True,
        secure=settings.ENV == "production",
        samesite="lax" if settings.ENV == "development" else "none",
        max_age=max_age,
        expires=expire_dt,
        path="/"
    )

    return {
        "success": True,
        "message": "Token refreshed",
        "data": {
            "access_token": new_access,
            "token_type": "bearer"
        }
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

    reset_link = f"{settings.FRONTEND_URL}/administrator/reset-password?token={fp_token}"
    
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
    user_id = request.state.user_id
    
    admin = await admin_repo.get_by_id(user_id)

    if not admin:
        return ServiceResponse.error("Utilisateur non trouvé", 404)
    
    if not password_service.verify_password(body.old_password, admin.hashed_password):
        return ServiceResponse.error("Ancien mot de passe incorrect.", 401)
    
    new_hashed = password_service.hash_password(body.new_password)
    await admin_repo.update_password(admin_id=admin.id, new_hashed_password=new_hashed)
    
    return ServiceResponse.success("Mot de passe mis à jour avec succès.")


@router.get("/data")
async def get_admin_data(request: Request, db: AsyncSession = Depends(get_db)):
    admin_repo = AdminRepository(db)
    user_id = request.state.user_id
    admin = await admin_repo.get_by_id(user_id)
    if not admin:
        return ServiceResponse.error("Admin non trouvé", 404)
    
    return ServiceResponse.success(
        message="Données sensibles accessibles uniquement aux admins authentifiés.", 
        data={
            "email": admin.email,
            "last_device_logged": admin.last_device_logged,
            "last_ip_logged": admin.last_ip_logged,
            "updated_at": admin.updated_at
        }
    )
    
    
@router.put("/update-data")
async def update_admin_email(body: ForgotPayload, request: Request, db: AsyncSession = Depends(get_db)):
    admin_repo = AdminRepository(db)
    user_id = request.state.user_id
    admin = await admin_repo.get_by_id(user_id)
    if not admin:
        return ServiceResponse.error("Admin non trouvé", 404)
    
    await admin_repo.update_email(admin_id=admin.id, new_email=body.email)
    
    return ServiceResponse.success(
        message="Email mis à jour pour l'admin connecté.",
        data={"new_email": body.email}
    )
    