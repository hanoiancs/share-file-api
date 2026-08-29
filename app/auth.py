from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import jwt
from authlib.integrations.httpx_client import AsyncOAuth2Client
from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse, Response
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session, select

from app.config import Settings, get_settings
from app.database import get_db
from app.models import User, UserAuth, normalize_email, split_email_domain, utc_now

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/google/callback", auto_error=False)
router = APIRouter()
OAUTH_STATE_AUDIENCE = "google-oauth-state"


def create_access_token(user: User, settings: Settings) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user.id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_expires_minutes)).timestamp()),
    }
    return jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )


def decode_access_token(token: str, settings: Settings) -> int:
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token"
        ) from exc


def encode_oauth_state(handle_url: str, settings: Settings) -> str:
    payload = {
        "handle_url": handle_url,
        "aud": OAUTH_STATE_AUDIENCE,
        "iat": int(datetime.now(UTC).timestamp()),
    }
    return jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )


def decode_oauth_state(state: str, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    try:
        payload = jwt.decode(
            state,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            audience=OAUTH_STATE_AUDIENCE,
        )
        handle_url = payload["handle_url"]
    except (jwt.PyJWTError, KeyError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid oauth state"
        ) from exc
    if not isinstance(handle_url, str) or not handle_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid oauth state"
        )
    return handle_url


def set_access_token_cookie(
    response: Response, access_token: str, settings: Settings
) -> None:
    response.set_cookie(
        "access_token",
        access_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=settings.jwt_expires_minutes * 60,
    )


def clear_access_token_cookie(response: Response) -> None:
    response.delete_cookie(
        "access_token",
        httponly=True,
        secure=False,
        samesite="lax",
    )


def redirect_with_access_token_cookie(
    url: str, access_token: str, settings: Settings
) -> RedirectResponse:
    response = RedirectResponse(url)
    set_access_token_cookie(response, access_token, settings)
    return response


def append_access_token(url: str, access_token: str) -> str:
    parts = urlsplit(url)
    query = parse_qsl(parts.query, keep_blank_values=True)
    query.append(("access_token", access_token))
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )


def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    bearer_token: Annotated[str | None, Depends(oauth2_scheme)] = None,
    access_token: Annotated[str | None, Cookie()] = None,
) -> User:
    token = bearer_token or access_token
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="missing token"
        )
    user_id = decode_access_token(token, settings)
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found"
        )

    if len(settings.allowed_users) > 0 and user.email not in settings.allowed_users:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="user not allowed"
        )

    return user


def upsert_google_user(db: Session, identity: dict[str, Any]) -> User:
    email = normalize_email(str(identity["email"]))
    oauth_id = str(identity["sub"])
    auth = db.exec(
        select(UserAuth)
        .where(UserAuth.oauth_provider == "google")
        .where(UserAuth.oauth_id == oauth_id)
    ).first()
    if auth is not None:
        user = db.get(User, auth.user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="orphaned user auth",
            )
    else:
        user = db.exec(select(User).where(User.email == email)).first()
    if user is None:
        user = User(email=email, email_domain=split_email_domain(email))
        db.add(user)
        db.flush()
    if auth is None:
        auth = UserAuth(user_id=user.id, oauth_provider="google", oauth_id=oauth_id)
        db.add(auth)
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
        await client.fetch_token("https://oauth2.googleapis.com/token", code=_code)
        response = await client.get("https://openidconnect.googleapis.com/v1/userinfo")
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google identity fetch failed",
        ) from exc


@router.get("/auth/google/login", name="auth_google_login")
def google_login(
    settings: Annotated[Settings, Depends(get_settings)],
    handle_url: Annotated[str | None, Query()] = None,
) -> RedirectResponse:
    redirect_url = handle_url or settings.client_default_redirect_url
    params = urlencode(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": settings.google_redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "offline",
            "prompt": "consent",
            "state": encode_oauth_state(redirect_url, settings),
        }
    )
    return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{params}")


@router.get("/auth/google/callback")
async def google_callback(
    code: Annotated[str, Query(min_length=1)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    state: Annotated[str | None, Query()] = None,
) -> RedirectResponse:
    identity = await fetch_google_identity(code)
    user = upsert_google_user(db, identity)
    access_token = create_access_token(user, settings)
    handle_url = (
        decode_oauth_state(state, settings)
        if state
        else settings.client_default_redirect_url
    )
    return redirect_with_access_token_cookie(
        append_access_token(handle_url, access_token), access_token, settings
    )


@router.post("/auth/logout")
def logout() -> Response:
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_access_token_cookie(response)
    return response


@router.get("/me")
def read_me(current_user: Annotated[User, Depends(get_current_user)]) -> dict[str, Any]:
    return {
        "id": current_user.id,
        "email": current_user.email,
        "email_domain": current_user.email_domain,
        "display_name": current_user.display_name,
        "avatar_url": current_user.avatar_url,
    }
