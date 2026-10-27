# vision-ocr-server

**Apple's on-device OCR, as a tiny HTTP API for your home network.**

Send it a PDF or an image, get back the text of every page — read by the same
[Vision](https://developer.apple.com/documentation/vision/recognizing-text-in-images) engine that
powers Live Text on your Mac. No cloud, no API keys, no GPU, no model downloads: a Mac you already
own becomes an OCR box for everything else on your LAN (a NAS, a Docker container, a Raspberry Pi,
a script on your laptop).

```sh
curl --data-binary @invoice.pdf http://my-mac.local:11500/ocr
```

```json
{"pages": ["ACME SUPPLIES, SL\nInvoice 16645 ...\nTOTAL 138,47"], "engine": "apple-vision",
 "version": "0.1.0", "seconds": 1.12}
```

---

> [!WARNING]
> ## It's open, on purpose. Keep it on your LAN.
>
> vision-ocr-server has **no authentication by default**. That is a deliberate choice, not an
> oversight: it is meant to sit on a trusted home or office network, next to the machines that use it,
> the same way a local Ollama or a network printer does.
>
> - **Never expose it to the internet.** No port forwarding, no reverse proxy, no tunnel.
> - **Stateless**: it stores nothing. Documents live in memory for the length of one request and are
>   gone. The worst a stranger on your LAN can do is borrow your Mac's CPU to read their own files.
> - It listens on `127.0.0.1` unless you say otherwise; `--host 0.0.0.0` opens it to the LAN and
>   prints a reminder.
> - Want a lock anyway (shared office, guest Wi-Fi)? Set `VISION_OCR_TOKEN` and every `/ocr` call
>   must send `Authorization: Bearer <token>`. Plain HTTP still means the token travels in the
>   clear, so it keeps out the curious, not a determined attacker on your network.

---

## Why

Tesseract (what most self-hosted tools use, including Paperless-ngx via OCRmyPDF) struggles with
light-grey print, small type and shaded tables. Apple Vision reads them. On 342 real supplier
invoices, adding Apple Vision's reading next to Tesseract's let a deterministic parser recover
34 of 40 invoices it had been getting wrong, without breaking any it got right.

Existing Vision wrappers are command-line tools or take images only. This one takes **PDFs**
(every page, rendered at 300 dpi) and images, lets you choose languages and accuracy, and is
small enough to read in five minutes.

## Requirements

- macOS (Apple Silicon or Intel) — Vision is a macOS framework; there is no Linux/Windows version.
- Python 3.12+ via [uv](https://docs.astral.sh/uv/).

## Run it

```sh
uv tool install git+https://github.com/polamatvalls91/vision-ocr-server@v0.1.0
vision-ocr-server                                    # localhost only, port 11500
vision-ocr-server --host 0.0.0.0 --languages es-ES,en-US   # your LAN, Spanish first
```

| Option | Default | |
|---|---|---|
| `--host` | `127.0.0.1` | `0.0.0.0` to serve the LAN |
| `--port` | `11500` | |
| `--languages` | `en-US` | comma-separated, in order of preference (`es-ES`, `fr-FR`, `de-DE`, `zh-Hans`…) |
| `--level` | `accurate` | `fast` trades quality for speed |
| `--dpi` | `300` | PDF render resolution |
| `--max-pages` | `20` | longer PDFs: the first 19 pages and the last |
| `VISION_OCR_TOKEN` (env) | unset | optional bearer token, see the warning above |

## API

| | |
|---|---|
| `GET /health` | `{"ok": true, "engine": "apple-vision", "version": "0.1.0"}` |
| `POST /ocr` | body: the raw file (PDF, PNG, JPEG, TIFF, HEIC…). Returns `pages`: one string per page, lines top to bottom, words left to right. `422` if it's neither a PDF nor an image, `401` on a bad token. |

From Python:

```python
import httpx

pages = httpx.post("http://my-mac.local:11500/ocr", content=open("invoice.pdf", "rb").read(),
                   timeout=120).json()["pages"]
```

## Keep it running (launchd)

Vision needs a logged-in user session, so run it as a **LaunchAgent** (not a LaunchDaemon), on a Mac
that logs in automatically and doesn't sleep.

```sh
git clone https://github.com/polamatvalls91/vision-ocr-server && cd vision-ocr-server
./launchd/install.sh --host 0.0.0.0 --languages es-ES,en-US
```

The script installs the tool with `uv tool`, writes `~/Library/LaunchAgents/io.github.polamatvalls91.vision-ocr-server.plist`
with your options, starts it and checks `/health`. Run it again to update or change options.
Logs: `~/Library/Logs/vision-ocr-server.log`.

| | |
|---|---|
| Restart | `launchctl kickstart -k gui/$(id -u)/io.github.polamatvalls91.vision-ocr-server` |
| Stop | `launchctl bootout gui/$(id -u)/io.github.polamatvalls91.vision-ocr-server` |

If other machines can't connect, the macOS firewall may be blocking Python: System Settings →
Network → Firewall → Options. Clients on the same Mac that can't reach other LAN machines need
*Local Network* permission (Privacy & Security), which is a different setting.

## Develop

```sh
uv sync
uv run pytest        # one test runs real Apple Vision on macOS; the rest fake it
```

## Credits

The OCR is Apple's; [ocrmac](https://github.com/straussmaximilian/ocrmac) does the heavy lifting of
calling it from Python, and [pypdfium2](https://github.com/pypdfium2-team/pypdfium2) renders PDFs.

## License

[MIT](LICENSE) — use it, change it, ship it, commercially or not. The one condition: keep the
copyright notice (credit to Pol Amat) in copies and substantial portions of the code.
