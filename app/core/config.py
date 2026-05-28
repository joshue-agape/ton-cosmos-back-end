import json
from typing import List, Union
from pydantic import computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # --- Infos Application ---
    app_name: str = "FastAPI Async App"
    ENV: str = "development"
    debug: bool = True
    version: str = "1.0.0"

    # --- Sécurité & Auth ---
    SESSION_SECRET: str
    JWT_SECRET_KEY: str
    CORS_ORIGINS: Union[List[str], str]
    FRONTEND_URL: str

    # --- Configuration Database (PostgreSQL) ---
    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str
    
    # --- Admin Initial ---
    ADMIN_USERNAME: str
    ADMIN_EMAIL: str
    ADMIN_PASSWORD: str
    
    # --- Service Mail (SMTP) ---
    MAIL_HOST: str
    MAIL_PORT: int
    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    MAIL_FROM: str
    MAIL_FROM_NAME: str
    MAIL_STARTTLS: bool = True
    MAIL_SSL: bool = False
    
    RESEND_API_KEY: str
    RESEND_API_FROM: str
    
    # --- Intégrations Tierces ---
    STRIPE_SECRET_KEY: str
    STRIPE_WEBHOOK_SECRET: str
    STRIPE_PRICE_ID_ESSENTIAL: str
    STRIPE_PRICE_ID_PREMIUM: str
    
    STRIPE_PRICE_CENTS_ESSENTIAL: int
    STRIPE_PRICE_CENTS_PREMIUM: int
    
    ANTHROPIC_API_KEY: str

    # Configuration du chargement des variables d'environnement
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_json_list(cls, v):
        """
        Permet de transformer une chaîne JSON dans le .env en liste Python.
        Exemple dans .env: CORS_ORIGINS='["http://localhost:3000"]'
        """
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                # Si ce n'est pas du JSON, on sépare par des virgules
                return [i.strip() for i in v.split(",")]
        return v

    # ---------------------------------------------------------
    # DATABASE_URL ASYNC (Utilise asyncpg)
    # ---------------------------------------------------------
    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        """
        Génère l'URL de connexion asynchrone pour SQLAlchemy.
        Note l'utilisation de 'postgresql+asyncpg' au lieu de 'psycopg2'.
        """
        return (
            f"postgresql+asyncpg://"
            f"{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

# Instance unique pour toute l'application
settings = Settings()