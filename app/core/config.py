import json
from typing import List
from pydantic import computed_field
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = 'ton_cosmos_api'
    ENV: str = "development"
    debug: bool = True
    version: str = "1.0.0"

    CORS_ORIGINS: List[str]
    FRONTEND_URL: str
    JWT_SECRET_KEY: str

    # ------------------------------
    # Database Configuration
    # ------------------------------
    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str
    
    ADMIN_EMAIL: str
    ADMIN_PASSWORD: str
    
    MAIL_HOST: str
    MAIL_PORT: int
    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    MAIL_FROM: str
    MAIL_FROM_NAME: str
    
    STRIPE_SECRET_KEY: str
    STRIPE_WEBHOOK_SECRET: str
    ANTHROPIC_API_KEY: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_json_list(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v

    # ------------------------------
    # Database Connection URL
    # ------------------------------
    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+psycopg2://"
            f"{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


settings = Settings()
