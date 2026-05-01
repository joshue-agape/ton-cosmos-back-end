from jose import jwt
from fastapi import Request
from argon2 import PasswordHasher
from app.core.config import settings
from argon2.exceptions import VerifyMismatchError
from datetime import datetime, timedelta, timezone

ph = PasswordHasher()

class PasswordService:
    # HASH PASSWORD
    def hash_password(self, password: str) -> str:
        return ph.hash(password)

    # VERIFY PASSWORD
    def verify_password(self, plain, hashed):
        try:
            return ph.verify(hashed, plain)
        except VerifyMismatchError:
            return False


jwst_secret_key = settings.JWT_SECRET_KEY
class JWTService:
    def __init__(self):
        self.secret_key = jwst_secret_key
        self.algorithm = "HS256"

    # ACCESS TOKEN (15 min)
    def create_access_token(self, user_id: int, email: str, secret_key: str = jwst_secret_key):
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)

        payload = {
            "sub": str(user_id),
            "email": email,
            "type": "access",
            "exp": expire
        }

        return jwt.encode(payload, secret_key, algorithm=self.algorithm)

    # REFRESH TOKEN
    def create_refresh_token(self, user_id: int, email: str, remember: bool = False):
        if remember:
            expire = datetime.now(timezone.utc) + timedelta(days=7)
        else:
            expire = datetime.now(timezone.utc) + timedelta(hours=24)

        payload = {
            "sub": str(user_id),
            "email": email,
            "type": "refresh",
            "exp": expire
        }

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    # NEW REFRESH TOKEN
    def create_new_refresh_token(self, user_id: int, email: str, expire: datetime):
        if expire.tzinfo is None:
            expire = expire.replace(tzinfo=timezone.utc)

        payload = {
            "sub": str(user_id),
            "email": email,
            "type": "refresh",
            "exp": expire,
            "iat": datetime.now(timezone.utc)
        }

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    # DECODE TOKEN
    def decode_token(self, token: str, secret_key: str = jwst_secret_key):
        try:
            return jwt.decode(token, secret_key, algorithms=[self.algorithm])
        except Exception as e:
            print("JWT DECODE ERROR:", str(e))
            return None


class UtilsService:
    def get_device(self, request: Request):
        ip = request.headers.get("x-forwarded-for")
        if ip:
            ip = ip.split(",")[0]
        else:
            ip = request.client.host

        print("Device IP =", ip)
        user_agent = request.headers.get("user-agent")
        print("Device info =", user_agent)

        return { "device": user_agent, "IP": ip }
