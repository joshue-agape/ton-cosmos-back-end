import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

# --- IMPORT DE VOS PARAMÈTRES ET MODÈLES ---
from app.models import *  # Importe tous les modèles pour l'autogénération
from app.core.config import settings
from app.database.base import Base

# Configuration de l'objet Alembic Config
config = context.config

# On force l'URL de la base de données à partir de vos réglages applicatifs
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Mise en place du logging (défini dans alembic.ini)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Cible pour l'autogénération (indispensable pour --autogenerate)
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Mode 'offline' : génère des scripts SQL sans se connecter à la DB."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection):
    """Effectue les migrations dans un contexte synchrone."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online() -> None:
    """Mode 'online' : connecte une base de données asynchrone."""
    
    # Configuration spécifique pour asyncpg
    # On désactive le cache pour éviter l'erreur 'DuplicatePreparedStatementError'
    connectable = create_async_engine(
        settings.DATABASE_URL,
        poolclass=pool.NullPool,
        connect_args={
            "prepared_statement_cache_size": 0,
            "statement_cache_size": 0
        }
    )

    async with connectable.connect() as connection:
        # On utilise run_sync pour exécuter le code synchrone d'Alembic
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()

# --- LOGIQUE D'EXÉCUTION PRINCIPALE ---
if context.is_offline_mode():
    run_migrations_offline()
else:
    try:
        asyncio.run(run_migrations_online())
    except (KeyboardInterrupt, SystemExit):
        pass