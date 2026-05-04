from typing import Optional
from sqlalchemy.orm import Session
from app.models.admin import Admin

class AdminRepository:
    def __init__(self, db: Session):
        self.db = db


    def get_by_email(self, email: str) -> Optional[Admin]:
        return self.db.query(Admin).filter(Admin.email == email).first()


    def get_by_id(self, admin_id: int) -> Optional[Admin]:
        return self.db.query(Admin).filter(Admin.id == admin_id).first()


    def get_by_reset_token(self, token: str) -> Optional[Admin]:
        return self.db.query(Admin).filter(Admin.reset_password_token == token).first()


    def update_login_stats(self, admin_id: int, ip: str, device: str) -> None:
        admin = self.get_by_id(admin_id)
        if admin:
            admin.last_ip_logged = ip
            admin.last_device_logged = device
            admin.failed_login_attempts = 0
            self.db.commit()


    def increment_failed_attempts(self, email: str) -> int:
        admin = self.get_by_email(email)
        if admin:
            admin.failed_login_attempts += 1
            self.db.commit()
            return admin.failed_login_attempts
        return 0


    def set_reset_token(self, email: str, token: str, expires_at) -> bool:
        admin = self.get_by_email(email)
        if admin:
            admin.reset_password_token = token
            admin.reset_password_token_expires_at = expires_at
            self.db.commit()
            return True
        return False


    def update_password(self, admin_id: int, new_hashed_password: str) -> None:
        admin = self.get_by_id(admin_id)
        if admin:
            admin.hashed_password = new_hashed_password
            admin.reset_password_token = None
            admin.reset_password_token_expires_at = None
            self.db.commit()
            