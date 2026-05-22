from fastapi.testclient import TestClient
import pytest
from sqlmodel import Session, select
from urllib.parse import parse_qs, urlparse

from internal_static_files.config import Settings
from internal_static_files.auth import decode_oauth_state, fetch_google_identity
from internal_static_files.models import User, UserAuth


def test_me_requires_bearer_token(client: TestClient) -> None:
    response = client.get("/me")

    assert response.status_code == 401


def test_me_returns_authenticated_user(client: TestClient, user_token: str) -> None:
    response = client.get("/me", headers={"Authorization": f"Bearer {user_token}"})

    assert response.status_code == 200
    assert response.json()["email"] == "alice@example.com"


def test_google_login_redirects_to_google(client: TestClient) -> None:
    response = client.get("/auth/google/login", follow_redirects=False)

    assert response.status_code in {302, 307}
    assert response.headers["location"].startswith("https://accounts.google.com/o/oauth2/v2/auth")


def test_google_login_stores_handle_url_in_oauth_state(client: TestClient, settings: Settings) -> None:
    response = client.get(
        "/auth/google/login?handle_url=https%3A%2F%2Fclient.example.com%2Fdone",
        follow_redirects=False,
    )

    location = response.headers["location"]
    state = parse_qs(urlparse(location).query)["state"][0]

    assert decode_oauth_state(state, settings) == "https://client.example.com/done"


def test_google_callback_redirects_to_state_handle_url_and_sets_access_token_cookie(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    async def fake_identity(_code: str) -> dict[str, str]:
        return {
            "sub": "google-bob",
            "email": "Bob@Example.com",
            "name": "Bob Example",
            "picture": "https://example.com/bob.png",
        }

    monkeypatch.setattr("internal_static_files.auth.fetch_google_identity", fake_identity)
    login = client.get(
        "/auth/google/login?handle_url=https%3A%2F%2Fclient.example.com%2Fdone%3Fsource%3Dlogin",
        follow_redirects=False,
    )
    state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]

    response = client.get(f"/auth/google/callback?code=abc&state={state}", follow_redirects=False)

    assert response.status_code in {302, 307}
    redirect = urlparse(response.headers["location"])
    query = parse_qs(redirect.query)
    assert f"{redirect.scheme}://{redirect.netloc}{redirect.path}" == "https://client.example.com/done"
    assert query["source"] == ["login"]
    assert "access_token" not in query
    access_token = response.cookies["access_token"]

    client.cookies.set("access_token", access_token)
    me = client.get("/me")
    assert me.status_code == 200
    assert me.json()["email"] == "bob@example.com"

    user = db_session.exec(select(User).where(User.email == "bob@example.com")).one()
    auth = db_session.get(UserAuth, (user.id, "google"))
    assert auth is not None
    assert auth.oauth_id == "google-bob"


def test_google_callback_uses_default_redirect_url_without_state(
    client: TestClient, monkeypatch
) -> None:
    async def fake_identity(_code: str) -> dict[str, str]:
        return {
            "sub": "google-default",
            "email": "default@example.com",
            "name": "Default Example",
            "picture": "https://example.com/default.png",
        }

    monkeypatch.setattr("internal_static_files.auth.fetch_google_identity", fake_identity)

    response = client.get("/auth/google/callback?code=abc", follow_redirects=False)

    assert response.status_code in {302, 307}
    redirect = urlparse(response.headers["location"])
    query = parse_qs(redirect.query)
    assert f"{redirect.scheme}://{redirect.netloc}{redirect.path}" == "https://client.example.com/auth/complete"
    assert "access_token" not in query
    assert response.cookies["access_token"]


def test_me_accepts_access_token_cookie(client: TestClient, user_token: str) -> None:
    client.cookies.set("access_token", user_token)
    response = client.get("/me")

    assert response.status_code == 200
    assert response.json()["email"] == "alice@example.com"


def test_google_callback_matches_existing_user_by_user_auth(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    async def fake_identity(_code: str) -> dict[str, str]:
        return {
            "sub": "google-bob",
            "email": "renamed@example.com",
            "name": "Bob Renamed",
            "picture": "https://example.com/bob-new.png",
        }

    monkeypatch.setattr("internal_static_files.auth.fetch_google_identity", fake_identity)
    first = client.get("/auth/google/callback?code=abc", follow_redirects=False)
    second = client.get("/auth/google/callback?code=def", follow_redirects=False)

    assert first.status_code in {302, 307}
    assert second.status_code in {302, 307}
    assert len(db_session.exec(select(User)).all()) == 1
    assert len(db_session.exec(select(UserAuth)).all()) == 1


@pytest.mark.anyio
async def test_fetch_google_identity_uses_authlib_client_token_state(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return {"sub": "google-alice", "email": "alice@example.com"}

    class FakeOAuthClient:
        def __init__(self, *args, **kwargs) -> None:
            self.get_kwargs = None

        async def fetch_token(self, url: str, **kwargs) -> dict[str, str]:
            assert url == "https://oauth2.googleapis.com/token"
            assert kwargs["code"] == "oauth-code"
            return {"access_token": "google-access-token"}

        async def get(self, url: str, **kwargs) -> FakeResponse:
            assert url == "https://openidconnect.googleapis.com/v1/userinfo"
            assert "token" not in kwargs
            self.get_kwargs = kwargs
            return FakeResponse()

    monkeypatch.setattr("internal_static_files.auth.AsyncOAuth2Client", FakeOAuthClient)

    identity = await fetch_google_identity("oauth-code")

    assert identity == {"sub": "google-alice", "email": "alice@example.com"}
