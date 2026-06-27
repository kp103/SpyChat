import pytest

from spychat.crypto import CryptoError, decrypt, encrypt, is_encrypted


def test_encrypt_decrypt_roundtrip():
    token = encrypt("the eagle lands", "hunter2")
    assert is_encrypted(token)
    assert "the eagle lands" not in token  # ciphertext, not plaintext
    assert decrypt(token, "hunter2") == "the eagle lands"


def test_wrong_passphrase_fails():
    token = encrypt("secret", "correct horse")
    with pytest.raises(CryptoError):
        decrypt(token, "wrong horse")


def test_unicode_roundtrip():
    msg = "rendez-vous à 23h ☕ секрет"
    assert decrypt(encrypt(msg, "pw"), "pw") == msg


def test_empty_passphrase_rejected():
    with pytest.raises(CryptoError):
        encrypt("x", "")


def test_decrypt_non_encrypted_rejected():
    with pytest.raises(CryptoError):
        decrypt("just plain text", "pw")


def test_each_encryption_uses_fresh_salt():
    a = encrypt("same", "pw")
    b = encrypt("same", "pw")
    assert a != b  # random salt => different ciphertext
    assert decrypt(a, "pw") == decrypt(b, "pw") == "same"
