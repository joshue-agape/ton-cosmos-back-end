from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.services.response_service import ServiceResponse
from app.repositories.admin_repository import AdminRepository
from app.database.session import SessionLocal

class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, jwt_service, public_paths: list[str] = None):
        super().__init__(app)
        self.jwt_service = jwt_service
        self.public_paths = public_paths or []

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        refresh_token = request.cookies.get("refresh_token")

        if request.method == "OPTIONS":
            return await call_next(request)

        if path in self.public_paths:
            return await call_next(request)

        if path.startswith(("/docs", "/redoc", "/openapi.json")):
            return await call_next(request)

        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return ServiceResponse.error(
                message="Missing Authorization header",
                status_code=401
            )

        if not auth_header.startswith("Bearer "):
            return ServiceResponse.error(
                message="Invalid authorization scheme",
                status_code=401
            )

        token = auth_header.split(" ")[1]

        refresh_payload = self.jwt_service.decode_token(token=refresh_token)
        if not refresh_payload:
            return ServiceResponse.error(
                message="Invalid or expired token",
                status_code=401
            )

        user_id = refresh_payload.get("sub")

        db = SessionLocal()

        try:
            user_repo = AdminRepository(db)

            try:
                user_id = int(user_id)
            except Exception:
                return ServiceResponse.error("Invalid or expired token", 401)

            user = user_repo.get_by_id(user_id)

            if not user:
                return ServiceResponse.error("Invalid or expired token", 401)

            verified_payload = self.jwt_service.decode_token(
                token,
                secret_key=user.client_secret
            )

            if not verified_payload:
                return ServiceResponse.error("Invalid or expired token", 401)

            request.state.user = verified_payload
        finally:
            db.close()

        return await call_next(request)