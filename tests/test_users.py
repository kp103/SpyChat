import pytest

from spychat.users import UserError, UserStore, normalize_username


def test_register_and_verify(tmp_path):
    store = UserStore(tmp_path)
    store.register("Agent_007", "password12")
    assert store.verify("agent_007", "password12") is True  # case-insensitive
    assert store.verify("agent_007", "wrongpass1") is False


def test_username_normalized(tmp_path):
    assert normalize_username("  BOND  ") == "bond"


def test_duplicate_rejected(tmp_path):
    store = UserStore(tmp_path)
    store.register("bond", "password12")
    with pytest.raises(UserError):
        store.register("BOND", "password12")


@pytest.mark.parametrize("name", ["ab", "has space", "UPPER!", "x" * 33, ""])
def test_invalid_usernames(tmp_path, name):
    store = UserStore(tmp_path)
    with pytest.raises(UserError):
        store.register(name, "password12")


def test_short_password_rejected(tmp_path):
    store = UserStore(tmp_path)
    with pytest.raises(UserError):
        store.register("valid", "short")


def test_verify_unknown_user_is_false(tmp_path):
    store = UserStore(tmp_path)
    assert store.verify("ghost", "whatever12") is False


def test_per_user_profile_stores_are_distinct(tmp_path):
    store = UserStore(tmp_path)
    a = store.profile_store("alice")
    b = store.profile_store("bob")
    assert a.path != b.path


def test_password_hash_not_plaintext(tmp_path):
    store = UserStore(tmp_path)
    store.register("bond", "supersecret1")
    raw = (tmp_path / "users.json").read_text()
    assert "supersecret1" not in raw
