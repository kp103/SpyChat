"""Tests for the interactive SpyChatCLI menu loop (driven via scripted input)."""

import builtins

import pytest

from spychat.cli import SpyChatCLI
from spychat.storage import ProfileStore


@pytest.fixture
def feed(monkeypatch):
    """Feed a scripted list of console inputs into input()/getpass()."""
    def _feed(responses, passwords=None):
        inputs = iter(responses)
        pwds = iter(passwords or [])
        monkeypatch.setattr(builtins, "input", lambda *a, **k: next(inputs))
        monkeypatch.setattr("spychat.cli.getpass", lambda *a, **k: next(pwds, ""))
    return _feed


def test_menu_register_add_friend_quit(tmp_path, feed):
    store = ProfileStore(tmp_path / "p.json")
    feed([
        "Bond", "Mr.", "23", "4.0",   # spy identity
        "2", "Q", "Mr.", "40", "5.0",  # add friend
        "6",                            # list friends
        "0",                            # quit
    ])
    assert SpyChatCLI(store).run() == 0

    saved = store.load()
    assert saved.spy.name == "Bond"
    assert saved.friends[0].name == "Q"


def test_menu_continue_as_existing_spy(tmp_path, feed):
    store = ProfileStore(tmp_path / "p.json")
    feed(["Bond", "Mr.", "23", "4.0", "0"])  # create then quit
    SpyChatCLI(store).run()

    # Second run: "Y" to continue as Bond, then quit.
    feed(["Y", "0"])
    assert SpyChatCLI(store).run() == 0


def test_menu_send_and_read_message(tmp_path, feed):
    from PIL import Image

    carrier = tmp_path / "carrier.png"
    Image.new("RGB", (96, 96), (80, 120, 160)).save(carrier)
    out = tmp_path / "secret.png"
    store = ProfileStore(tmp_path / "p.json")

    feed(
        [
            "Bond", "Mr.", "23", "4.0",        # identity
            "2", "Q", "Mr.", "40", "5.0",       # add friend
            "3", "1", str(carrier), str(out), "rendezvous",  # send (friend 1)
            "4", "1", str(out),                 # read (friend 1)
            "0",                                # quit
        ],
        passwords=["secretpw", "secretpw"],     # encrypt then decrypt
    )
    assert SpyChatCLI(store).run() == 0
    assert out.exists()


def test_menu_invalid_choice_then_quit(tmp_path, feed, capsys):
    store = ProfileStore(tmp_path / "p.json")
    feed(["Bond", "Mr.", "23", "4.0", "99", "0"])
    SpyChatCLI(store).run()
    assert "Invalid choice" in capsys.readouterr().out
