from pathlib import Path
from unittest.mock import MagicMock, patch

from epubgen import images


def test_is_available_false_without_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert images.is_available() is False


def test_generate_image_skips_when_unavailable(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    out = tmp_path / "x.png"
    assert images.generate_image("a thing", out) is False
    assert not out.exists()


def test_generate_image_writes_decoded_bytes(monkeypatch, tmp_path: Path):
    import base64

    payload = b"\x89PNG\r\n\x1a\nfake"
    b64 = base64.b64encode(payload).decode()

    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")

    fake_response = MagicMock()
    fake_response.data = [MagicMock(b64_json=b64)]
    fake_client = MagicMock()
    fake_client.images.generate.return_value = fake_response

    with patch("openai.OpenAI", return_value=fake_client):
        out = tmp_path / "x.png"
        ok = images.generate_image("a prompt", out)
    assert ok is True
    assert out.read_bytes() == payload
