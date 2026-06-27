from PIL import Image

from spychat.cli import main


def _make_image(path):
    Image.new("RGB", (64, 64), (120, 90, 200)).save(path)
    return str(path)


def test_cli_encode_decode_roundtrip(tmp_path, capsys):
    src = _make_image(tmp_path / "in.png")
    out = tmp_path / "out.png"
    assert main(["encode", src, str(out), "hello spy"]) == 0
    assert main(["decode", str(out)]) == 0
    assert "hello spy" in capsys.readouterr().out


def test_cli_encrypted_roundtrip(tmp_path, capsys):
    src = _make_image(tmp_path / "in.png")
    out = tmp_path / "out.png"
    assert main(["encode", src, str(out), "classified", "-p", "pw123"]) == 0

    # Without passphrase => error exit.
    assert main(["decode", str(out)]) == 1
    # With passphrase => prints plaintext.
    assert main(["decode", str(out), "-p", "pw123"]) == 0
    assert "classified" in capsys.readouterr().out


def test_cli_decode_wrong_passphrase(tmp_path):
    src = _make_image(tmp_path / "in.png")
    out = tmp_path / "out.png"
    main(["encode", src, str(out), "secret", "-p", "right"])
    assert main(["decode", str(out), "-p", "wrong"]) == 1


def test_cli_encode_rejects_jpeg_output(tmp_path, capsys):
    src = _make_image(tmp_path / "in.png")
    assert main(["encode", src, str(tmp_path / "out.jpg"), "hi"]) == 1
    assert "lossless" in capsys.readouterr().err
