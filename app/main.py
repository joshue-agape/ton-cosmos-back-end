from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from contextlib import asynccontextmanager

from app.api.v1.router import api_router
from app.core.config import settings
from app.database.session import engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()

# Création de l'instance principale
app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    debug=settings.debug,
    lifespan=lifespan
)

# Middleware de session
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET,
    same_site="lax",
    https_only=settings.ENV != "development"
)

# Configuration du CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["POST", "GET", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
)

# Inclusion des routes
app.include_router(api_router, prefix="/api/v1")

# Middleware d'Authentification personnalisé
# app.add_middleware(
#     AuthMiddleware,
#     public_paths=["/api/v1/auth/login", "/api/v1/docs", "/api/v1/openapi.json"],
# )

@app.get("/")
async def root():
    return {
        "status": "online",
        "message": f"Welcome to {settings.app_name} API",
        "version": settings.version
    }
