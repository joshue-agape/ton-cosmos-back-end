from jose import jwt, JWTError, ExpiredSignatureError
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse

from app.repositories.admin_repository import AdminRepository
from app.repositories.token_repository import TokenRepository
from app.database.session import SessionLocal
from app.services.utility_service import JWTService
from app.services.token_service import TokenService


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, public_paths: list[str] = None):
        super().__init__(app)
        self.jwt_service = JWTService()
        self.public_paths = public_paths or []

    async def dispatch(self, request: Request, call_next):

        path = request.url.path

        if request.method == "OPTIONS":
            return await call_next(request)

        if path in self.public_paths or path.startswith(("/docs", "/redoc", "/openapi.json")):
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return self._error("Missing Authorization header")

        if not auth_header.startswith("Bearer "):
            return self._error("Invalid Bearer format")

        token = auth_header.split(" ")[1]

        try:
            payload = jwt.decode(
                token,
                self.jwt_service.secret_key,
                algorithms=[self.jwt_service.algorithm]
            )

        except ExpiredSignatureError:
            return self._error("Access token expired", 401)

        except JWTError:
            return self._error("Invalid access token", 401)

        if payload.get("type") != "access":
            return self._error("Invalid token type", 401)

        user_id = int(payload.get("sub"))

        try:
            async with SessionLocal() as db:
                user_repo = AdminRepository(db)
                token_repo = TokenRepository(db)
                token_service = TokenService(token_repo)

                user = await user_repo.get_by_id(user_id)

                if not user:
                    return self._error("User not found", 401)

                is_revoked = await token_service.is_token_revoked(token)
                if is_revoked:
                    return self._error("Token revoked", 401)

                refresh_token = request.cookies.get("refresh_token")

                if not refresh_token:
                    return self._error("Missing refresh token")

                try:
                    refresh_payload = jwt.decode(
                        refresh_token,
                        user.client_secret,
                        algorithms=[self.jwt_service.algorithm]
                    )

                    if refresh_payload.get("type") != "refresh":
                        return self._error("Invalid refresh token type")

                    is_refresh_revoked = await token_service.is_token_revoked(refresh_token)
                    if is_refresh_revoked:
                        return self._error("Refresh token revoked")

                except JWTError:
                    return self._error("Invalid refresh token")

                request.state.user = payload
                request.state.user_id = user.id

        except Exception:
            return self._error("Authentication error", 500)

        return await call_next(request)

    def _error(self, message: str, status_code: int = 401):
        return JSONResponse(
            status_code=status_code,
            content={
                "success": False,
                "message": message
            }
        )