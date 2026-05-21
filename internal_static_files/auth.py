from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from urllib.parse import urlencode

import jwt
from authlib.integrations.httpx_client import AsyncOAuth2Client
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session, select

from internal_static_files.config import Settings, get_settings
from internal_static_files.database import get_db
from internal_static_files.models import User, normalize_email, split_email_domain, utc_now


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/google/callback")
router = APIRouter()


def create_access_token(user: User, settings: Settings) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user.id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_expires_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings) -> int:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token") from exc


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    user_id = decode_access_token(token, settings)
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found")
    return user


def upsert_google_user(db: Session, identity: dict[str, Any]) -> User:
    email = normalize_email(str(identity["email"]))
    google_sub = str(identity["sub"])
    user = db.exec(select(User).where(User.google_sub == google_sub)).first()
    if user is None:
        user = db.exec(select(User).where(User.email == email)).first()
    if user is None:
        user = User(google_sub=google_sub, email=email, email_domain=split_email_domain(email))
        db.add(user)
    user.google_sub = google_sub
    user.email = email
    user.email_domain = split_email_domain(email)
    user.display_name = identity.get("name")
    user.avatar_url = identity.get("picture")
    user.last_login_at = utc_now()
    db.commit()
    db.refresh(user)
    return user


async def fetch_google_identity(_code: str) -> dict[str, Any]:
    settings = get_settings()
    client = AsyncOAuth2Client(
        settings.google_client_id,
        settings.google_client_secret,
        redirect_uri=settings.google_redirect_uri,
        scope="openid email profile",
    )
    try:
        token = await client.fetch_token("https://oauth2.googleapis.com/token", code=_code)
        response = await client.get("https://openidconnect.googleapis.com/v1/userinfo", token=token)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Google identity fetch failed") from exc


@router.get("/auth/google/login")
def google_login(settings: Annotated[Settings, Depends(get_settings)]) -> RedirectResponse:
    params = urlencode(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": settings.google_redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "offline",
            "prompt": "consent",
        }
    )
    return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{params}")


@router.get("/auth/google/callback")
async def google_callback(
    code: Annotated[str, Query(min_length=1)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    identity = await fetch_google_identity(code)
    user = upsert_google_user(db, identity)
    return {"access_token": create_access_token(user, settings), "token_type": "bearer"}


@router.get("/me")
def read_me(current_user: Annotated[User, Depends(get_current_user)]) -> dict[str, Any]:
    return {
        "id": current_user.id,
        "email": current_user.email,
        "email_domain": current_user.email_domain,
        "display_name": current_user.display_name,
        "avatar_url": current_user.avatar_url,
    }
