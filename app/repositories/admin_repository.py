from typing import Optional
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
            admin.failed_login_attempts = 0
            await self.db.commit()


    async def increment_failed_attempts(self, email: str) -> int:
        admin = await self.get_by_email(email)
        if admin:
            admin.failed_login_attempts += 1
            await self.db.commit()
            await self.db.refresh(admin)
            return admin.failed_login_attempts
        return 0


    async def set_reset_token(self, email: str, token: str, expires_at) -> bool:
        admin = await self.get_by_email(email)
        if admin:
            admin.reset_password_token = token
            admin.reset_password_token_expires_at = expires_at
            await self.db.commit()
            return True
        return False


    async def update_password(self, admin_id: int, new_hashed_password: str) -> None:
        admin = await self.get_by_id(admin_id)
        if admin:
            admin.hashed_password = new_hashed_password
            admin.reset_password_token = None
            admin.reset_password_token_expires_at = None
            await self.db.commit()
            
    async def update_email(self, admin_id: int, new_email: str) -> None:
        admin = await self.get_by_id(admin_id)
        if admin:
            admin.email = new_email
            await self.db.commit()
            
            await self.db.commit()
            