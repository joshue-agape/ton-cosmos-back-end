from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.models.token import Token


class TokenRepository:
    def __init__(self, db: Session):
        self.db = db

    # CREATE TOKEN
    def create_token(self, token: Token) -> Token:
        self.db.add(token)
        self.db.commit()
        self.db.refresh(token)

        return token

    # GET TOKEN BY HASH
    def get_by_hash(self, token_hash: str) -> Token | None:
        return (
            self.db.query(Token)
            .filter(Token.token_hash == token_hash)
            .first()
        )

    # GET ALL TOKENS FOR USER
    def get_user_tokens(self, user_id: int) -> list[Token]:
        return (
            self.db.query(Token)
            .filter(Token.user_id == user_id)
            .all()
        )

    # GET VALID TOKENS (NOT EXPIRED)
    def get_valid_tokens(self, user_id: int) -> list[Token]:
        now = datetime.now(timezone.utc)

        return (
            self.db.query(Token)
            .filter(
                Token.user_id == user_id,
                Token.exp > now
            )
            .all()
        )

    # DELETE TOKEN (logout single session)
    def delete_token(self, token_hash: str) -> bool:
        token = self.get_by_hash(token_hash)

        if not token:
            return False

        self.db.delete(token)
        self.db.commit()
        return True

    # DELETE ALL TOKENS FOR USER (logout all devices)
    def delete_user_tokens(self, user_id: int):
        (
            self.db.query(Token)
            .filter(Token.user_id == user_id)
            .delete()
        )
        self.db.commit()

    # DELETE EXPIRED TOKENS (cleanup job)
    def delete_expired_tokens(self):
        now = datetime.now(timezone.utc)

        (
            self.db.query(Token)
            .filter(Token.exp <= now)
            .delete()
        )
        self.db.commit()