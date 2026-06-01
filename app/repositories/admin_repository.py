from typing import Optional
from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.admin import Admin

class AdminRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_email(self, email: str) -> Optional[Admin]:
        query = select(Admin).filter(Admin.email == email)
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_by_id(self, admin_id: int) -> Optional[Admin]:
        query = select(Admin).filter(Admin.id == admin_id)
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_by_reset_token(self, token: str) -> Optional[Admin]:
        query = select(Admin).filter(Admin.reset_password_token == token)
        result = await self.db.execute(query)
        return result.scalars().first()

    async def update_login_stats(self, admin_id: int, ip: str, device: str) -> None:
        admin = await self.get_by_id(admin_id)
        if admin:
            admin.last_ip_logged = ip
            admin.last_device_logged = device
            admin.failed_attempts = 0
            admin.locked_until = None
            admin.failed_attempts_ip = None

    async def increment_failed_attempts(self, email: str) -> None:
        query = (
            update(Admin)
            .where(Admin.email == email)
            .values(failed_attempts=Admin.failed_attempts + 1)
        )
        await self.db.execute(query)

    async def set_reset_token(self, email: str, token: str, expires_at: datetime) -> bool:
        admin = await self.get_by_email(email)
        if admin:
            admin.reset_password_token = token
            admin.reset_password_token_expires_at = expires_at
            return True
        return False

    async def update_password(self, admin_id: int, new_hashed_password: str) -> None:
        admin = await self.get_by_id(admin_id)
        if admin:
            admin.hashed_password = new_hashed_password
            admin.reset_password_token = None
            admin.reset_password_token_expires_at = None
            
    async def update_email(self, admin_id: int, new_email: str) -> None:
        admin = await self.get_by_id(admin_id)
        if admin:
            admin.email = new_email
            
    async def lock_account(self, admin_id: int, lock_until: datetime, ip: str | None) -> None:
        query = (
            update(Admin)
            .where(Admin.id == admin_id)
            .values(
                locked_until=lock_until,
                failed_attempts_ip=ip
            )
        )
        await self.db.execute(query)

    async def reset_failed_attempts(self, admin_id: int) -> None:
        query = (
            update(Admin)
            .where(Admin.id == admin_id)
            .values(
                failed_attempts=0, 
                locked_until=None,
                failed_attempts_ip=None
            )
        )
        await self.db.execute(query)