import io
import sys

import pypdfium2
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

from vision_ocr_server import __version__, server

ONE_WORD = [("138,47", 1.0, (0.8, 0.1, 0.1, 0.01))]


def pdf(pages: int) -> bytes:
    document = pypdfium2.PdfDocument.new()
    for _ in range(pages):
        document.new_page(595, 842)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (100, 50), "white").save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("VISION_OCR_TOKEN", raising=False)
    monkeypatch.setattr(server, "recognize", lambda image: ONE_WORD)
    return TestClient(server.app)


def test_health(client):
    assert client.get("/health").json() == {"ok": True, "engine": "apple-vision", "version": __version__}


def test_one_text_per_pdf_page(client):
    answer = client.post("/ocr", content=pdf(2), headers={"Content-Type": "application/pdf"}).json()
    assert answer["pages"] == ["138,47", "138,47"] and answer["engine"] == "apple-vision"


def test_an_image_is_one_page(client):
    assert client.post("/ocr", content=png()).json()["pages"] == ["138,47"]


def test_long_pdfs_keep_the_first_pages_and_the_last(client, monkeypatch):
    seen = []
    monkeypatch.setattr(server, "recognize", lambda image: seen.append(image) or [])
    client.post("/ocr", content=pdf(server.settings.max_pages + 5))
    assert len(seen) == server.settings.max_pages


@pytest.mark.parametrize("body", [b"hello", b"%PDF-broken"])
def test_neither_pdf_nor_image(client, body):
    assert client.post("/ocr", content=body).status_code == 422


def test_token_required_when_set(client, monkeypatch):
    monkeypatch.setenv("VISION_OCR_TOKEN", "s3cret")
    assert client.post("/ocr", content=pdf(1)).status_code == 401
    assert client.post("/ocr", content=pdf(1), headers={"Authorization": "Bearer s3cret"}).status_code == 200
    assert client.get("/health").status_code == 200  # health never needs it


@pytest.mark.skipif(sys.platform != "darwin", reason="Apple Vision is macOS only")
def test_real_apple_vision_reads_a_rendered_pdf(monkeypatch):
    """No fakes: a PDF page with a printed amount comes back with that amount."""
    monkeypatch.delenv("VISION_OCR_TOKEN", raising=False)
    image = Image.new("RGB", (1240, 1754), "white")
    ImageDraw.Draw(image).text((200, 800), "TOTAL 138,47", fill="black", font=ImageFont.load_default(size=60))
    buffer = io.BytesIO()
    image.save(buffer, format="PDF", resolution=150)
    answer = TestClient(server.app).post("/ocr", content=buffer.getvalue()).json()
    assert "138,47" in answer["pages"][0]
