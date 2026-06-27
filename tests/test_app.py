import pytest
from PIL import Image

from spychat.app import SpyChatApp, ValidationError


@pytest.fixture
def app():
    a = SpyChatApp()
    a.register_spy("Bond", "Mr.", 23, 4.0)
    return a


@pytest.fixture
def carrier(tmp_path):
    path = tmp_path / "carrier.png"
    Image.new("RGB", (64, 64), (100, 100, 100)).save(path)
    return path


def test_register_spy_age_bounds():
    app = SpyChatApp()
    with pytest.raises(ValidationError):
        app.register_spy("Kid", "Mr.", 10, 4.0)
    with pytest.raises(ValidationError):
        app.register_spy("Old", "Mr.", 60, 4.0)


def test_register_spy_requires_name():
    app = SpyChatApp()
    with pytest.raises(ValidationError):
        app.register_spy("   ", "Mr.", 30, 4.0)


def test_add_friend_rating_gate(app):
    with pytest.raises(ValidationError):
        app.add_friend("Weak", "Mr.", 30, 1.0)  # below spy's 4.0
    friend = app.add_friend("Strong", "Ms.", 30, 4.5)
    assert friend in app.friends


def test_add_friend_age_gate(app):
    with pytest.raises(ValidationError):
        app.add_friend("Tiny", "Mr.", 12, 5.0)


def test_send_and_read_roundtrip(app, carrier, tmp_path):
    app.add_friend("Q", "Mr.", 40, 5.0)
    out = tmp_path / "secret.png"
    app.send_message(0, carrier, out, "meet at noon")
    assert app.friends[0].chats[-1].message == "meet at noon"
    assert app.friends[0].chats[-1].is_sent_by_me is True

    result = app.read_message(0, out)
    assert result["text"] == "meet at noon"
    # "#"-prefixed => recognised as sent by me on read-back.
    assert app.friends[0].chats[-1].is_sent_by_me is True


def test_special_message_detected(app, carrier, tmp_path):
    app.add_friend("Q", "Mr.", 40, 5.0)
    out = tmp_path / "s.png"
    app.send_message(0, carrier, out, "Hi all")
    result = app.read_message(0, out)
    assert result["is_special"] is True


def test_long_message_terminates_friend(app, tmp_path):
    from PIL import Image as _Image

    big = tmp_path / "big.png"
    _Image.new("RGB", (256, 256), (50, 50, 50)).save(big)
    app.add_friend("Chatty", "Mr.", 40, 5.0)
    out = tmp_path / "long.png"
    app.send_message(0, big, out, "word " * 150)
    result = app.read_message(0, out)
    assert result["terminated"] is True
    assert not app.friends  # friend removed


def test_remove_friend_bad_index(app):
    with pytest.raises(ValidationError):
        app.remove_friend(5)


def test_send_empty_message_rejected(app, carrier, tmp_path):
    app.add_friend("Q", "Mr.", 40, 5.0)
    with pytest.raises(ValidationError):
        app.send_message(0, carrier, tmp_path / "o.png", "   ")
