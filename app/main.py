import secrets
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html

from app.core.config import settings
from app.database.session import engine
from app.api.v1.router import api_router
from app.middleware.auth_middleware import AuthMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()

# Création de l'instance principale
app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    debug=settings.debug,
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    json_url=None
)

security = HTTPBasic()

# Middleware de session
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET,
    same_site="none",
    https_only=settings.ENV != "development"
)

# Inclusion des routes
app.include_router(api_router, prefix="/api/v1")

# Middleware d'Authentification personnalisé
app.add_middleware(
    AuthMiddleware,
    public_paths=[
        "/",
        "/api/v1/admin/login",
        "/api/v1/admin/refresh-token",
        "/api/v1/admin/reset-password",
        "/api/v1/stripe/stripe/webhook",
        "/api/v1/admin/forgot-password",
        "/api/v1/admin/verify-reset-token",
        "/api/v1/order/create",
        "/api/v1/stripe/create-checkout-session",
        "/api/v1/order/find-all-with-report"
    ],
)

# Configuration du CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["POST", "GET", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "status": "online",
        "message": f"Welcome to {settings.app_name} API",
        "version": settings.version
    }

def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, settings.ADMIN_USERNAME)
    correct_password = secrets.compare_digest(credentials.password, settings.ADMIN_PASSWORD)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants incorrects",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

@app.get("/docs", include_in_schema=False)
async def get_documentation(username: str = Depends(get_current_username)):
    return get_swagger_ui_html(openapi_url="/openapi.json", title="Docs Protégées")

@app.get("/redoc", include_in_schema=False)
async def get_redoc(username: str = Depends(get_current_username)):
    return get_redoc_html(openapi_url="/openapi.json", title="ReDoc Protégée")
