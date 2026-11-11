"""The HTTP API. Settings come from the CLI (cli.py) through `settings`.

GET  /health -> {"ok": true, "engine": "apple-vision", "version": ...}
POST /ocr    -> body: a PDF or an image (PNG, JPEG, TIFF, HEIC...); ?correction=false turns off
                Vision's language correction for this request (default: the server's setting);
                {"pages": ["text of page 1", ...], "engine", "version", "seconds"}
                401 bad token, 422 neither a PDF nor an image.
"""
import io
import os
import time
from dataclasses import dataclass, field

import pypdfium2
from fastapi import FastAPI, Header, HTTPException, Request
from PIL import Image, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool

from vision_ocr_server import __version__
from vision_ocr_server.lines import to_lines


@dataclass
class Settings:
    dpi: int = 300
    """PDF pages are rendered at this resolution before OCR."""
    max_pages: int = 20
    """Longer PDFs: the first max_pages - 1 pages and the last."""
    languages: list[str] = field(default_factory=lambda: ["en-US"])
    """Vision's language preference, in order (e.g. es-ES, en-US)."""
    level: str = "accurate"
    """accurate or fast."""
    correction: bool = True
    """Vision's language correction: fixes words against a dictionary. Off for codes, IDs, amounts."""


settings = Settings()
app = FastAPI(title="vision-ocr-server", version=__version__)


def recognize(image: Image.Image, correction: bool) -> list:
    """(text, confidence, (x, y, w, h)) per recognised text run. Imported here: macOS only.

    A VNRecognizeTextRequest built here rather than through ocrmac.OCR, which has no switch for
    language correction."""
    import objc
    import Vision
    from ocrmac.ocrmac import pil2buf

    with objc.autorelease_pool():
        request = Vision.VNRecognizeTextRequest.alloc().init()
        request.setRecognitionLevel_(1 if settings.level == "fast" else 0)
        request.setUsesLanguageCorrection_(correction)
        supported = request.supportedRecognitionLanguagesAndReturnError_(None)[0]
        if not set(settings.languages) <= set(supported):
            raise ValueError(f"unsupported languages {settings.languages}; Vision supports {list(supported)}")
        request.setRecognitionLanguages_(settings.languages)
        handler = Vision.VNImageRequestHandler.alloc().initWithData_options_(pil2buf(image), None)
        ok = handler.performRequests_error_([request], None)
        ok, error = ok if isinstance(ok, tuple) else (bool(ok), None)
        if not ok or error is not None:
            return []
        runs = []
        for result in request.results():
            box = result.boundingBox()
            runs.append((result.text(), result.confidence(),
                         (box.origin.x, box.origin.y, box.size.width, box.size.height)))
        return runs


def _pdf_pages(body: bytes, correction: bool) -> list[str]:
    document = pypdfium2.PdfDocument(body)
    try:
        count = len(document)
        limit = settings.max_pages
        indexes = list(range(count)) if count <= limit else [*range(limit - 1), count - 1]
        return [to_lines(recognize(document[i].render(scale=settings.dpi / 72).to_pil(), correction))
                for i in indexes]
    finally:
        document.close()


def _pages(body: bytes, correction: bool) -> list[str]:
    if body.startswith(b"%PDF"):
        try:
            return _pdf_pages(body, correction)
        except pypdfium2.PdfiumError as e:
            raise HTTPException(422, f"unreadable PDF: {e}") from e
    try:
        image = Image.open(io.BytesIO(body))
        image.load()
    except (UnidentifiedImageError, OSError) as e:
        raise HTTPException(422, "neither a PDF nor an image") from e
    return [to_lines(recognize(image.convert("RGB"), correction))]


@app.get("/health")
def health() -> dict:
    return {"ok": True, "engine": "apple-vision", "version": __version__}


@app.post("/ocr")
async def ocr(request: Request, authorization: str | None = Header(default=None),
              correction: bool | None = None) -> dict:
    token = os.environ.get("VISION_OCR_TOKEN")
    if token and authorization != f"Bearer {token}":
        raise HTTPException(401, "bad token")
    started = time.monotonic()
    use_correction = settings.correction if correction is None else correction
    pages = await run_in_threadpool(_pages, await request.body(), use_correction)
    return {"pages": pages, "engine": "apple-vision", "version": __version__,
            "seconds": round(time.monotonic() - started, 2)}
