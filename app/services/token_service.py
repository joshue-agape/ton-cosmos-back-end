from app.models.token import Token
from datetime import datetime, timezone
from app.repositories.token_repository import TokenRepository

class TokenService:
    def __init__(self, repo: TokenRepository):
        self.repo = repo

    def revoque_token(self, user_id: int, token: str, token_type: str, exp: datetime):
        token = Token(
            token_hash=token,
            token_type=token_type,
            user_id=user_id,
            exp=exp
        )

        return self.repo.create_token(token)

    def find_by_token(self, token: str):
        return self.repo.get_by_hash(token)