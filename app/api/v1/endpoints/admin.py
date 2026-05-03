import secrets
from sqlalchemy.orm import Session
from app.database.deps import get_db
from app.core.config import settings
from fastapi import APIRouter, BackgroundTasks, Depends, Response, Request

from app.schemas.admin import *
from app.services.email_service import *
from app.services.utility_service import *
from app.services.token_service import TokenService
from app.repositories.admin_repository import *
from app.repositories.token_repository import *
from app.services.response_service import ServiceResponse


router = APIRouter()

service = UtilsService()
jwt_service = JWTService()
email_service = EmailService()
password_service = PasswordService()

jwst_secret_key = settings.JWT_SECRET_KEY


@router.post("/login")
def login(body: LoginPayload, request: Request, response: Response, db: Session = Depends(get_db)):
    admin_repo = AdminRepository(db)
    
    device = service.get_device(request=request)
    
    admin = admin_repo.get_by_email(body.email)
    if not admin:
        return ServiceResponse.error(
            message="Invalid email",
            status_code=401,
            data={ "error": "email" }
        )
        
    if not password_service.verify_password(body.password, admin.hashed_password):
        return ServiceResponse.error(
            message="Password incorrect",
            status_code=401,
            data={"error": "password"}
        )
    
    admin_repo.update_login_stats(
        admin_id=admin.id,
        device=device.get("device"),
        ip=device.get("IP")
    )

    access_token = jwt_service.create_access_token(
        user_id=admin.id,
        email=admin.email
    )
    
    refresh_token = jwt_service.create_refresh_token(
        user_id=admin.id,
        email=admin.email,
        remember=body.remember_me if body.remember_me else False
    )
    
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.ENV == 'production',
        samesite="lax",
        max_age=7 * 24 * 60 * 60 if body.remember_me else 24 * 60 * 60
    )

    return {
        "status_code": 200,
        "success": True,
        "message": "Login successful",
        "data": {
            "access_token": access_token,
            "token_type": "bearer"
        }
    }


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    admin_repo = AdminRepository(db)
    token_repo = TokenRepository(db)
    token_service = TokenService(token_repo)
    
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        return ServiceResponse.error("Missing refresh token", 401)
    
    refresh_payload = jwt_service.decode_token(refresh_token)
    if not refresh_payload or refresh_payload.get("type") != "refresh":
        return ServiceResponse.error("Invalid refresh token", 401)
    
    try:
        refresh_user_id = int(refresh_payload.get("sub"))
        refresh_expire = datetime.fromtimestamp(
            refresh_payload.get("exp"), tz=timezone.utc
        )
    except (TypeError, ValueError):
        return ServiceResponse.error("Invalid refresh token payload", 401)

    user = admin_repo.get_by_id(refresh_user_id)
    if not user:
        return ServiceResponse.error("Invalid refresh token payload", 401)

    if settings.ENV == "production":
        token_service.revoque_token(
            user_id=user.id,
            token=refresh_token,
            token_type="refresh",
            exp=refresh_expire
        )

    response.delete_cookie("refresh_token")

    return {
        "success": True,
        "status_code": 200,
        "message": "Logout successfully",
        "data": None
    }


@router.post("/refresh-token")
def refreshToken(token: str, request: Request, response: Response, db: Session = Depends(get_db)):
    admin_repo = AdminRepository(db)
    token_repo = TokenRepository(db)
    token_service = TokenService(token_repo)
    
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        return ServiceResponse.error("Missing refresh token", 401)
    
    refresh_payload = jwt_service.decode_token(refresh_token)
    
    if not refresh_payload or refresh_payload.get("type") != "refresh":
        return ServiceResponse.error(message="Invalid refresh token", status_code=401)

    exp_timestamp = refresh_payload.get("exp")

    if not exp_timestamp:
        return ServiceResponse.error(message="Invalid expiration", status_code=401)
    
    expire = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
    now = datetime.now(timezone.utc)

    if expire <= now:
        response.delete_cookie("refresh_token")
        return ServiceResponse.error(message="Refresh token expired", status_code=401)
    
    user_id = refresh_payload.get("sub")

    if not user_id:
        return ServiceResponse.error(message="Invalid token payload", status_code=401)
    
    try:
        user_id = int(user_id)
    except ValueError:
        return ServiceResponse.error(message="Invalid user ID", status_code=401)
    
    existing_user = admin_repo.get_by_id(user_id)

    if not existing_user:
        return ServiceResponse.error(message="User not found", status_code=404)

    if settings.ENV == 'production':
        token_service.revoque_token(
            user_id=user_id,
            token=refresh_token,
            token_type="refresh",
            exp=expire
        )
        token_service.revoque_token(
            user_id=user_id,
            token=token,
            token_type="access",
            exp=now
        )
        
    new_access_token = jwt_service.create_access_token(
        user_id=existing_user.id,
        email=existing_user.email,
        secret_key=existing_user.client_secret
    )

    new_refresh_token = jwt_service.create_new_refresh_token(
        user_id=existing_user.id,
        email=existing_user.email,
        expire=expire
    )
    
    max_age = int((expire - now).total_seconds())
    if max_age <= 0:
        response.delete_cookie("refresh_token")
        return ServiceResponse.error(message="Refresh token expired", status_code=404)
        
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=settings.ENV == 'production',
        samesite="lax",
        max_age=max_age,
        path="/"
    )

    return {
        "success": True,
        "status_code": 200,
        "message": "Token refreshed",
        "data": {
            "access_token": new_access_token,
            "token_type": "bearer"
        }
    }


@router.post("/forgot-password")
def reset_password(body: ForgotPayload, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    admin_repo = AdminRepository(db)
    
    admin = admin_repo.get_by_email(body.email)
    if not admin:
        return ServiceResponse.success(
            message="Si un compte avec cet email existe, un lien de réinitialisation a été envoyé.",
            status_code=200
        )
    
    fp_token = secrets.token_urlsafe(32)
    fp_expire = datetime.now(timezone.utc) + timedelta(minutes=15)

    admin_repo.set_reset_token(
        email=body.email,
        token=fp_token,
        expires_at=fp_expire
    )

    reset_password_link = f"{settings.FRONTEND_URL}/eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9/YXV0aC9yZXNldC1wYXNzd29yZA?token={fp_token}"
    
    background_tasks.add_task(
        email_service.send_email,
        to=admin.email,
        subject="Réinitialisation de votre mot de passe - Ton Cosmos",
        template_name="reset_password",
        data={
            "full_name": "Système JVN Lab - Ton Cosmos",
            "reset_link": reset_password_link,
            "current_year": datetime.now().year
        }
    )
    
    return ServiceResponse.success(
        message="Si un compte avec cet email existe, un lien de réinitialisation a été envoyé.",
        status_code=200
    )


@router.get("/verify-reset-token")
def verifyToken(token: str, db: Session = Depends(get_db)):
    admin_repo = AdminRepository(db)
    
    admin = admin_repo.get_by_reset_token(token)
    
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
    
    return ServiceResponse.success(
        message="Le jeton est valide.",
        status_code=200,
        data=None
    )


@router.put("/reset-password")
def reset_password(body: ResetPayload, db: Session = Depends(get_db)):
    admin_repo = AdminRepository(db)
    
    admin = admin_repo.get_by_reset_token(body.token)
    
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
    
    hashed_password = password_service.hash_password(body.new_password)
    admin_repo.update_password(admin_id=admin.id, new_hashed_password=hashed_password)
    
    return ServiceResponse.success(
        message="Ton mot de passe a été mis à jour avec succès.",
        status_code=200,
        data=None
    )


@router.patch("/update-password")
def reset_password(body: UpdatePasswordPayload, request: Request, response: Response, db: Session = Depends(get_db)):
    admin_repo = AdminRepository(db)
    
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        return ServiceResponse.error("Missing refresh token", 401)
    
    refresh_payload = jwt_service.decode_token(refresh_token)
    
    if not refresh_payload or refresh_payload.get("type") != "refresh":
        return ServiceResponse.error(message="Invalid refresh token", status_code=401)

    exp_timestamp = refresh_payload.get("exp")

    if not exp_timestamp:
        return ServiceResponse.error(message="Invalid expiration", status_code=401)
    
    expire = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
    now = datetime.now(timezone.utc)

    if expire <= now:
        response.delete_cookie("refresh_token")
        return ServiceResponse.error(message="Refresh token expired", status_code=401)
    
    user_id = refresh_payload.get("sub")

    if not user_id:
        return ServiceResponse.error(message="Invalid token payload", status_code=401)
    
    try:
        user_id = int(user_id)
    except ValueError:
        return ServiceResponse.error(message="Invalid user ID", status_code=401)
    
    admin = admin_repo.get_by_id(user_id)

    if not admin:
        return ServiceResponse.error(message="User not found", status_code=404)
    
    if not password_service.verify_password(body.old_password, admin.hashed_password):
        return ServiceResponse.error(
            message="L'ancien mot de passe est incorrect.",
            status_code=401,
            data={"error": "password"}
        )
    
    hashed_password = password_service.hash_password(body.new_password)
    admin_repo.update_password(admin_id=admin.id, new_hashed_password=hashed_password)
    
    return ServiceResponse.success(
        message="Ton mot de passe a été mis à jour avec succès.",
        status_code=200,
        data=None
    )
