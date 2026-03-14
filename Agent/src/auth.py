"""
Authentication utilities for PenangLens.
Handles password hashing, JWT token creation/verification, and user registration/login.
"""

import os
from datetime import datetime, timezone, timedelta
from passlib.context import CryptContext
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.db_models import User

# ===========================================================================
# Config
# ===========================================================================
SECRET_KEY = os.getenv("JWT_SECRET", "penanglens-dev-secret-change-in-prod")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ===========================================================================
# Password Hashing
# ===========================================================================
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ===========================================================================
# JWT Tokens
# ===========================================================================
def create_token(user_id: str, email: str) -> str:
    """Create a JWT token for an authenticated user."""
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict | None:
    """Decode and verify a JWT token. Returns payload or None."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


# ===========================================================================
# User Operations
# ===========================================================================
async def register_user(db: AsyncSession, email: str, password: str, display_name: str = None, interests: list = None) -> User:
    """Create a new user. Raises ValueError if email already exists."""
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise ValueError("Email already registered")

    user = User(
        email=email,
        password_hash=hash_password(password),
        display_name=display_name,
        interests=interests or [],
    )
    db.add(user)
    await db.flush()
    return user


async def login_user(db: AsyncSession, email: str, password: str) -> tuple[User, str]:
    """Authenticate a user. Returns (user, token) or raises ValueError."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.password_hash):
        raise ValueError("Invalid email or password")

    token = create_token(user.id, user.email)
    return user, token
