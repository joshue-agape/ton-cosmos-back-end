from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.middleware.auth_middleware import AuthMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.api.v1.router import api_router
from app.core.config import settings

# Création de l'instance principale de l'application FastAPI
app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    debug=settings.debug
)

# Configuration du middleware de session (Starlette)
# Indispensable pour gérer des données persistantes côté serveur via un cookie signé
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET,                 # Clé pour signer les cookies de session
    same_site="lax",                                    # Protection contre les attaques CSRF
    https_only=settings.ENV != "development"            # True si l'environnement n'est pas "development"
)

# Configuration du CORS (Cross-Origin Resource Sharing)
# Permet de définir quels domaines externes sont autorisés à communiquer avec cette API
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,                # Liste des domaines autorisés (ex: localhost:3000)
    allow_credentials=True,                             # Autorise l'envoi de cookies et headers d'auth
    allow_methods=["POST","GET","PUT","PATCH"],         # Verbes HTTP autorisés
    allow_headers=["*"],                                # Accepte tous les types de headers
)

# Inclusion des routes de l'API (version 1)
# Toutes les routes seront préfixées par "/api/v1"
app.include_router(api_router, prefix="/api/v1")

# Middleware d'Authentification personnalisé
# Ce middleware intercepte les requêtes pour vérifier la validité des tokens
# Note : Il est ajouté en dernier car l'ordre d'exécution des middlewares est LIFO (Last In, First Out)
app.add_middleware(
    AuthMiddleware,
    public_paths=[],
)
