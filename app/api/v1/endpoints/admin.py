from fastapi import APIRouter
from sqlalchemy.orm import Session
from app.database.deps import get_db
from fastapi import APIRouter, Depends, Response, Request
from app.core.config import settings

from app.schemas.admin import *
from app.services.utility_service import *
from app.repositories.admin_repository import *
from app.services.response_service import ServiceResponse


router = APIRouter()

service = UtilsService()
jwt_service = JWTService()
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
        print("Revoke refresh token")

    response.delete_cookie("refresh_token")

    return {
        "success": True,
        "status_code": 200,
        "message": "Logout successfully",
        "data": None
    }


@router.get("/refresh-token")
def refreshToken(db: Session = Depends(get_db)):
    return


@router.post("/forgot-password")
def reset_password(db: Session = Depends(get_db)):
    return


@router.put("/reset-password")
def reset_password(db: Session = Depends(get_db)):
    return


@router.patch("/update-password")
def reset_password(db: Session = Depends(get_db)):
    return
