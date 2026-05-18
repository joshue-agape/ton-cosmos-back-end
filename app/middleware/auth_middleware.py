from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.services.response_service import ServiceResponse
from app.repositories.admin_repository import AdminRepository
from app.database.session import SessionLocal
from app.services.utility_service import JWTService

class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, public_paths: list[str] = None):
        super().__init__(app)
        self.jwt_service = JWTService()
        self.public_paths = public_paths or []

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        refresh_token = request.cookies.get("refresh_token")

        # On laisse passer les requêtes de pré-vérification CORS sans poser de questions
        if request.method == "OPTIONS":
            return await call_next(request)

        # Si le chemin est public, on ne dérange pas l'utilisateur avec l'auth
        if path in self.public_paths:
            return await call_next(request)

        # On évite de bloquer la documentation API (Swagger/Redoc)
        if path.startswith(("/docs", "/redoc", "/openapi.json", "/api/v1/health", "/api/v1/order", "/api/v1/stripe")):
            return await call_next(request)

        auth_header = request.headers.get("Authorization")

        # Pas de badge, pas de chocolat : on vérifie la présence du header Authorization
        if not auth_header:
            return ServiceResponse.error(
                message="Le header d'autorisation est manquant.",
                status_code=401
            )

        # On s'assure que le format est bien "Bearer <token>"
        if not auth_header.startswith("Bearer "):
            return ServiceResponse.error(
                message="Le format du jeton d'authentification est invalide (doit être Bearer).",
                status_code=401
            )

        token = auth_header.split(" ")[1]

        # On tente de décoder le refresh token pour identifier qui frappe à la porte
        refresh_payload = self.jwt_service.decode_token(token=refresh_token)
        
        if not refresh_payload:
            return ServiceResponse.error(
                message="Votre session a expiré ou le jeton est invalide. Veuillez vous reconnecter.",
                status_code=401
            )

        user_id = refresh_payload.get("sub")

        async with SessionLocal() as db:
            try:
                user_repo = AdminRepository(db)
                user_id_int = int(user_id)
                
                user = await user_repo.get_by_id(user_id_int)

                if not user:
                    return self._abort("Administrateur introuvable.", 401, request)

                verified_payload = self.jwt_service.decode_token(
                    token,
                    secret_key=user.client_secret
                )

                if not verified_payload:
                    return self._abort("Jeton d'accès invalide ou expiré.", 401, request)

                request.state.user = verified_payload
                
            except Exception as e:
                return self._abort("Erreur interne d'authentification.", 500, request)

        return await call_next(request)

    def _abort(self, message: str, status_code: int, request: Request):
        response = JSONResponse(
            content={"success": False, "message": message},
            status_code=status_code
        )
        origin = request.headers.get("Origin")
        if origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        return response