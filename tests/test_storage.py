from spychat.app import SpyChatApp
from spychat.models import Profile
from spychat.storage import ProfileStore


def test_save_and_load_roundtrip(tmp_path):
    store = ProfileStore(tmp_path / "profile.json")
    app = SpyChatApp()
    app.register_spy("Bond", "Mr.", 23, 4.0)
    app.add_friend("Q", "Mr.", 40, 5.0)
    app.add_status_message("on a mission")
    store.save(app.profile)

    loaded = store.load()
    assert loaded.spy.name == "Bond"
    assert loaded.friends[0].name == "Q"
    assert "on a mission" in loaded.status_messages


def test_load_missing_returns_empty(tmp_path):
    store = ProfileStore(tmp_path / "nope.json")
    profile = store.load()
    assert isinstance(profile, Profile)
    assert profile.spy is None


def test_save_is_atomic_no_partial_file(tmp_path):
    store = ProfileStore(tmp_path / "profile.json")
    app = SpyChatApp()
    app.register_spy("Bond", "Mr.", 23, 4.0)
    store.save(app.profile)
    # No leftover temp files in the directory.
    assert [p.name for p in tmp_path.iterdir()] == ["profile.json"]
