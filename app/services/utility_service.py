from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

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

