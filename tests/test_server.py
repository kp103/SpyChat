import io

import pytest
from PIL import Image

from spychat.server import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path / "profile.json")
    app.config.update(TESTING=True)
    with app.test_client() as c:
        yield c


def _png_bytes(size=(96, 96), color=(90, 140, 60)):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    buf.seek(0)
    return buf


def test_register_spy_and_profile(client):
    r = client.post("/api/spy", json={"name": "Bond", "salutation": "Mr.", "age": 23, "rating": 4.0})
    assert r.status_code == 200
    assert r.get_json()["spy"]["name"] == "Bond"

    r = client.get("/api/profile")
    assert r.get_json()["spy"]["display_name"] == "Mr. Bond"


def test_register_spy_validation_error(client):
    r = client.post("/api/spy", json={"name": "", "salutation": "Mr.", "age": 23, "rating": 4.0})
    assert r.status_code == 400
    assert "error" in r.get_json()


def test_add_and_remove_friend(client):
    client.post("/api/spy", json={"name": "Bond", "salutation": "Mr.", "age": 23, "rating": 4.0})
    r = client.post("/api/friends", json={"name": "Q", "salutation": "Mr.", "age": 40, "rating": 5.0})
    assert len(r.get_json()["friends"]) == 1
    r = client.delete("/api/friends/0")
    assert r.get_json()["friends"] == []


def test_capacity_endpoint(client):
    r = client.post("/api/capacity", data={"image": (_png_bytes((10, 10)), "c.png")},
                    content_type="multipart/form-data")
    assert r.status_code == 200
    assert r.get_json()["capacity_bytes"] == 29


def test_encode_then_decode_roundtrip(client):
    enc = client.post("/api/encode", data={"image": (_png_bytes(), "c.png"), "message": "meet at noon"},
                      content_type="multipart/form-data")
    assert enc.status_code == 200
    assert enc.mimetype == "image/png"

    dec = client.post("/api/decode", data={"image": (io.BytesIO(enc.data), "s.png")},
                      content_type="multipart/form-data")
    body = dec.get_json()
    assert body["text"] == "meet at noon"
    assert body["was_encrypted"] is False


def test_encrypted_roundtrip_via_api(client):
    enc = client.post("/api/encode", data={
        "image": (_png_bytes(), "c.png"), "message": "classified", "passphrase": "s3cret",
    }, content_type="multipart/form-data")
    stego_bytes = enc.data

    # Wrong / missing passphrase fails.
    bad = client.post("/api/decode", data={"image": (io.BytesIO(stego_bytes), "s.png")},
                      content_type="multipart/form-data")
    assert bad.status_code == 400

    ok = client.post("/api/decode",
                     data={"image": (io.BytesIO(stego_bytes), "s.png"), "passphrase": "s3cret"},
                     content_type="multipart/form-data")
    assert ok.get_json()["text"] == "classified"
    assert ok.get_json()["was_encrypted"] is True


def test_decode_plain_image_errors(client):
    r = client.post("/api/decode", data={"image": (_png_bytes(), "plain.png")},
                    content_type="multipart/form-data")
    assert r.status_code == 400


def test_index_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"SpyChat" in r.data


def test_encode_logs_against_friend(client):
    client.post("/api/spy", json={"name": "Bond", "salutation": "Mr.", "age": 23, "rating": 4.0})
    client.post("/api/friends", json={"name": "Q", "salutation": "Mr.", "age": 40, "rating": 5.0})
    client.post("/api/encode", data={
        "image": (_png_bytes(), "c.png"), "message": "hi Q", "friend_index": "0",
    }, content_type="multipart/form-data")
    prof = client.get("/api/profile").get_json()
    assert prof["friends"][0]["chats"][-1]["message"] == "hi Q"
