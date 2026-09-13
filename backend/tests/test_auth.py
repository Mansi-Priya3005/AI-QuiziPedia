def test_signup_creates_user_and_returns_token(client):
    r = client.post(
        "/auth/signup", json={"email": "new@example.com", "password": "password123"}
    )
    assert r.status_code == 201
    body = r.json()
    assert body["access_token"]
    assert body["user"]["email"] == "new@example.com"
    assert "password" not in body["user"]
    assert "hashed_password" not in body["user"]


def test_signup_rejects_short_password(client):
    r = client.post(
        "/auth/signup", json={"email": "new@example.com", "password": "short"}
    )
    assert r.status_code == 422


def test_signup_rejects_invalid_email(client):
    r = client.post(
        "/auth/signup", json={"email": "not-an-email", "password": "password123"}
    )
    assert r.status_code == 422


def test_signup_rejects_duplicate_email(client):
    client.post(
        "/auth/signup", json={"email": "dup@example.com", "password": "password123"}
    )
    r = client.post(
        "/auth/signup", json={"email": "dup@example.com", "password": "anotherpassword"}
    )
    assert r.status_code == 409


def test_signup_email_is_case_insensitive_for_duplicates(client):
    client.post(
        "/auth/signup", json={"email": "Case@Example.com", "password": "password123"}
    )
    r = client.post(
        "/auth/signup", json={"email": "case@example.com", "password": "password123"}
    )
    assert r.status_code == 409


def test_login_with_correct_credentials_succeeds(client):
    client.post(
        "/auth/signup", json={"email": "login@example.com", "password": "password123"}
    )
    r = client.post(
        "/auth/login", json={"email": "login@example.com", "password": "password123"}
    )
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_login_with_wrong_password_fails(client):
    client.post(
        "/auth/signup", json={"email": "login2@example.com", "password": "password123"}
    )
    r = client.post(
        "/auth/login", json={"email": "login2@example.com", "password": "wrongpassword"}
    )
    assert r.status_code == 401


def test_login_with_nonexistent_email_fails(client):
    r = client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": "password123"}
    )
    assert r.status_code == 401


def test_me_endpoint_requires_valid_token(client):
    r = client.get("/auth/me")
    assert r.status_code == 401

    r2 = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert r2.status_code == 401


def test_me_endpoint_returns_current_user(client, auth_headers):
    r = client.get("/auth/me", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["email"] == "quiztaker@example.com"
