import io

import pytest
from PIL import Image

from spychat.server import create_app

CSRF = {"X-Requested-With": "SpyChat"}


@pytest.fixture
def app(tmp_path):
    app = create_app(tmp_path)
    app.config.update(TESTING=True)
    return app


@pytest.fixture
def client(app):
    with app.test_client() as c:
        yield c


@pytest.fixture
def auth_client(app):
    """A client with a registered, logged-in user."""
    with app.test_client() as c:
        c.post("/api/register", json={"username": "bond", "password": "shaken-not-stirred"},
               headers=CSRF)
        yield c


def _png(size=(96, 96), color=(90, 140, 60)):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    buf.seek(0)
    return buf


def _form(client, path, **fields):
    data = {k: v for k, v in fields.items() if v is not None}
    return client.post(path, data=data, content_type="multipart/form-data", headers=CSRF)


# -- health & pages ----------------------------------------------------------

def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200 and r.get_json()["status"] == "ok"


def test_index_served(client):
    r = client.get("/")
    assert r.status_code == 200 and b"SpyChat" in r.data


# -- auth --------------------------------------------------------------------

def test_register_login_logout(client):
    assert client.post("/api/register", json={"username": "neo", "password": "matrix1999"},
                       headers=CSRF).status_code == 200
    assert client.post("/api/logout", headers=CSRF).status_code == 200
    assert client.get("/api/me").get_json()["username"] is None
    r = client.post("/api/login", json={"username": "neo", "password": "matrix1999"}, headers=CSRF)
    assert r.status_code == 200 and r.get_json()["username"] == "neo"


def test_register_rejects_short_password(client):
    r = client.post("/api/register", json={"username": "bob", "password": "short"}, headers=CSRF)
    assert r.status_code == 400


def test_register_rejects_bad_username(client):
    r = client.post("/api/register", json={"username": "a b!", "password": "longenough1"}, headers=CSRF)
    assert r.status_code == 400


def test_duplicate_registration_rejected(client):
    body = {"username": "dup", "password": "password12"}
    assert client.post("/api/register", json=body, headers=CSRF).status_code == 200
    client.post("/api/logout", headers=CSRF)
    assert client.post("/api/register", json=body, headers=CSRF).status_code == 400


def test_login_wrong_password(client):
    client.post("/api/register", json={"username": "x", "password": "password12"}, headers=CSRF)
    client.post("/api/logout", headers=CSRF)
    r = client.post("/api/login", json={"username": "x", "password": "wrongpass1"}, headers=CSRF)
    assert r.status_code == 401


def test_protected_endpoint_requires_auth(client):
    assert client.get("/api/profile").status_code == 401


# -- CSRF --------------------------------------------------------------------

def test_csrf_header_required(client):
    # No X-Requested-With header => rejected even with valid JSON.
    r = client.post("/api/register", json={"username": "noheader", "password": "password12"})
    assert r.status_code == 403


# -- per-user isolation ------------------------------------------------------

def test_profiles_are_isolated_per_user(app):
    with app.test_client() as a:
        a.post("/api/register", json={"username": "alice", "password": "password12"}, headers=CSRF)
        a.post("/api/spy", json={"name": "Alice", "salutation": "Ms.", "age": 30, "rating": 4.0},
               headers=CSRF)
    with app.test_client() as b:
        b.post("/api/register", json={"username": "bobby", "password": "password12"}, headers=CSRF)
        prof = b.get("/api/profile").get_json()
        assert prof["spy"] is None  # bobby cannot see alice's spy


# -- profile / friends -------------------------------------------------------

def test_register_spy_and_profile(auth_client):
    r = auth_client.post("/api/spy", json={"name": "Bond", "salutation": "Mr.", "age": 23, "rating": 4.0},
                         headers=CSRF)
    assert r.status_code == 200 and r.get_json()["spy"]["display_name"] == "Mr. Bond"


def test_register_spy_validation_error(auth_client):
    r = auth_client.post("/api/spy", json={"name": "", "salutation": "Mr.", "age": 23, "rating": 4.0},
                         headers=CSRF)
    assert r.status_code == 400


def test_add_and_remove_friend(auth_client):
    auth_client.post("/api/spy", json={"name": "Bond", "salutation": "Mr.", "age": 23, "rating": 4.0},
                     headers=CSRF)
    r = auth_client.post("/api/friends", json={"name": "Q", "salutation": "Mr.", "age": 40, "rating": 5.0},
                         headers=CSRF)
    assert len(r.get_json()["friends"]) == 1
    assert auth_client.delete("/api/friends/0", headers=CSRF).get_json()["friends"] == []


# -- steganography -----------------------------------------------------------

def test_capacity_endpoint(auth_client):
    r = _form(auth_client, "/api/capacity", image=(_png((10, 10)), "c.png"))
    assert r.status_code == 200 and r.get_json()["capacity_bytes"] == 29


def test_encode_then_decode_roundtrip(auth_client):
    enc = _form(auth_client, "/api/encode", image=(_png(), "c.png"), message="meet at noon")
    assert enc.status_code == 200 and enc.mimetype == "image/png"
    dec = _form(auth_client, "/api/decode", image=(io.BytesIO(enc.data), "s.png"))
    body = dec.get_json()
    assert body["text"] == "meet at noon" and body["was_encrypted"] is False


def test_encrypted_roundtrip_via_api(auth_client):
    enc = _form(auth_client, "/api/encode", image=(_png(), "c.png"),
                message="classified", passphrase="s3cretpw")
    stego = enc.data
    bad = _form(auth_client, "/api/decode", image=(io.BytesIO(stego), "s.png"))
    assert bad.status_code == 400
    ok = _form(auth_client, "/api/decode", image=(io.BytesIO(stego), "s.png"), passphrase="s3cretpw")
    assert ok.get_json()["text"] == "classified" and ok.get_json()["was_encrypted"] is True


def test_decode_plain_image_errors(auth_client):
    r = _form(auth_client, "/api/decode", image=(_png(), "plain.png"))
    assert r.status_code == 400


def test_decode_rejects_non_image(auth_client):
    r = _form(auth_client, "/api/decode", image=(io.BytesIO(b"not an image"), "x.png"))
    assert r.status_code == 400
    assert "valid image" in r.get_json()["error"]


def test_encode_logs_against_friend(auth_client):
    auth_client.post("/api/spy", json={"name": "Bond", "salutation": "Mr.", "age": 23, "rating": 4.0},
                     headers=CSRF)
    auth_client.post("/api/friends", json={"name": "Q", "salutation": "Mr.", "age": 40, "rating": 5.0},
                     headers=CSRF)
    _form(auth_client, "/api/encode", image=(_png(), "c.png"), message="hi Q", friend_index="0")
    prof = auth_client.get("/api/profile").get_json()
    assert prof["friends"][0]["chats"][-1]["message"] == "hi Q"


# -- upload size limit -------------------------------------------------------

def test_upload_too_large_returns_413(app):
    app.config["MAX_CONTENT_LENGTH"] = 1024  # 1 KB cap for the test
    with app.test_client() as c:
        c.post("/api/register", json={"username": "big", "password": "password12"}, headers=CSRF)
        big = io.BytesIO(b"\x00" * 5000)
        r = _form(c, "/api/capacity", image=(big, "big.png"))
        assert r.status_code == 413
