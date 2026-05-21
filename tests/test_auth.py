from fastapi.testclient import TestClient


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


def test_google_callback_upserts_user_and_returns_token(client: TestClient, monkeypatch) -> None:
    async def fake_identity(_code: str) -> dict[str, str]:
        return {
            "sub": "google-bob",
            "email": "Bob@Example.com",
            "name": "Bob Example",
            "picture": "https://example.com/bob.png",
        }

    monkeypatch.setattr("internal_static_files.auth.fetch_google_identity", fake_identity)

    response = client.get("/auth/google/callback?code=abc")

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]

    me = client.get("/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == "bob@example.com"
