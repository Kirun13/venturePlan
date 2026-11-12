import asyncio
import hashlib
import hmac
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from app.config import get_settings
from app.db.models import User, UserSession
from app.db.session import Session

router = APIRouter(prefix="/auth", tags=["auth"])
COOKIE = "ventureplan_session"


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600000).hex()
    return f"pbkdf2_sha256$600000$"+salt+"$"+digest


def verify_password(password: str, encoded: str) -> bool:
    try:
        _, iterations, salt, digest = encoded.split("$")
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations)).hex()
        return hmac.compare_digest(actual, digest)
    except (ValueError, TypeError):
        return False


DUMMY_HASH = hash_password("dummy-password-not-an-account")


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("email")
    @classmethod
    def email_valid(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address")
        return value


class UserOut(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    email: str


def digest_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def current_user(request: Request) -> User:
    token = request.cookies.get(COOKIE)
    if not token:
        raise HTTPException(401, "Sign in to continue")
    async with Session() as session:
        result = await session.execute(select(User).join(UserSession).where(
            UserSession.token_hash == digest_token(token),
            UserSession.expires_at > datetime.now(timezone.utc)))
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(401, "Your session expired. Please sign in again")
        return user


async def set_session(response: Response, user: User):
    settings = get_settings()
    token = secrets.token_urlsafe(32)
    async with Session.begin() as session:
        # Expired sessions have no value and can be removed during normal traffic.
        await session.execute(delete(UserSession).where(UserSession.expires_at < datetime.now(timezone.utc)))
        session.add(UserSession(token_hash=digest_token(token), user_id=user.id,
                    expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.session_hours)))
    response.set_cookie(COOKIE, token, max_age=settings.session_hours * 3600,
                        httponly=True, secure=settings.cookie_secure, samesite="lax", path="/")


async def check_auth_limit(request: Request):
    from sqlalchemy.dialects.postgresql import insert
    from app.db.models import AuthLimit
    key = digest_token("auth:" + (request.client.host if request.client else "unknown"))
    now = datetime.now(timezone.utc)
    async with Session.begin() as session:
        await session.execute(insert(AuthLimit).values(key=key, window_start=now, attempts=0)
                              .on_conflict_do_nothing())
        row = await session.get(AuthLimit, key, with_for_update=True)
        if row.window_start < now - timedelta(minutes=15):
            row.window_start, row.attempts = now, 0
        if row.attempts >= 30:
            raise HTTPException(429, "Too many sign-in attempts. Try again in 15 minutes")
        row.attempts += 1


@router.post("/register", response_model=UserOut, status_code=201)
async def register(data: Credentials, request: Request, response: Response):
    await check_auth_limit(request)
    encoded = await asyncio.to_thread(hash_password, data.password)
    try:
        async with Session.begin() as session:
            user = User(email=data.email, password_hash=encoded)
            session.add(user)
            await session.flush()
    except IntegrityError:
        raise HTTPException(409, "This email is already registered")
    await set_session(response, user)
    return user


@router.post("/login", response_model=UserOut)
async def login(data: Credentials, request: Request, response: Response):
    await check_auth_limit(request)
    async with Session() as session:
        user = await session.scalar(select(User).where(User.email == data.email))
    valid = await asyncio.to_thread(verify_password, data.password, user.password_hash if user else DUMMY_HASH)
    if not user or not valid:
        raise HTTPException(401, "Incorrect email or password")
    await set_session(response, user)
    return user


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(current_user)):
    return user


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response):
    token = request.cookies.get(COOKIE)
    if token:
        async with Session.begin() as session:
            await session.execute(delete(UserSession).where(UserSession.token_hash == digest_token(token)))
    response.delete_cookie(COOKIE, path="/", secure=get_settings().cookie_secure, httponly=True, samesite="lax")
