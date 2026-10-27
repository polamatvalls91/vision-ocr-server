"""vision-ocr-server [--host 127.0.0.1] [--port 11500] [--languages es-ES,en-US] [--dpi 300] [--level accurate]"""
import argparse
import ipaddress
import os
import sys

import uvicorn

from vision_ocr_server import __version__
from vision_ocr_server.server import app, settings


def _loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="vision-ocr-server", description="Apple Vision OCR as an HTTP API.")
    parser.add_argument("--host", default="127.0.0.1", help="listen address (default 127.0.0.1; 0.0.0.0 for the LAN)")
    parser.add_argument("--port", type=int, default=11500)
    parser.add_argument("--languages", default="en-US", help="comma-separated, in order, e.g. es-ES,en-US")
    parser.add_argument("--dpi", type=int, default=300, help="PDF render resolution")
    parser.add_argument("--max-pages", type=int, default=20)
    parser.add_argument("--level", choices=["accurate", "fast"], default="accurate")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)

    if sys.platform != "darwin":
        parser.exit(1, "vision-ocr-server needs macOS (Apple Vision).\n")
    if not _loopback(args.host) and not os.environ.get("VISION_OCR_TOKEN"):
        # Open by design (README: LAN only, never the internet); the token is an optional extra.
        print(f"vision-ocr-server: listening on {args.host} with no auth -- keep it on a trusted LAN.",
              file=sys.stderr)

    settings.dpi, settings.max_pages, settings.level = args.dpi, args.max_pages, args.level
    settings.languages = [lang.strip() for lang in args.languages.split(",") if lang.strip()]
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
