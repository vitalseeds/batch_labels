"""
Batch label printer — FastAPI app for printing ZPL labels to a Zebra network printer.
Fill in the form, preview the label, and send it to the printer.
"""

import base64
import os
import socket

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse

load_dotenv()

app = FastAPI()

PRINTER_HOST = os.getenv("PRINTER_HOST", "192.168.1.100")
PRINTER_PORT = int(os.getenv("PRINTER_PORT", "9100"))
LABEL_WIDTH   = int(os.getenv("LABEL_WIDTH", "4"))
LABEL_HEIGHT  = int(os.getenv("LABEL_HEIGHT", "2"))
LABEL_DPI     = int(os.getenv("LABEL_DPI", "203"))

def build_zpl(sku: str, batch: str) -> str:
    """Return a ZPL string for one label showing the SKU barcode and batch."""
    return (
        "^XA"
        f"^FO40,20^A0N,45,35^FD{sku}^FS"          # SKU text
        f"^FO40,80^BY2^BCN,90,Y,N,N^FD{sku}^FS"   # Code-128 barcode
        f"^FO40,230^A0N,30,25^FDBatch: {batch}^FS" # Batch number
        "^XZ"
    )


def send_to_printer(zpl: str, copies: int) -> None:
    """Send ZPL to the printer over TCP, repeated `copies` times."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(5)
        s.connect((PRINTER_HOST, PRINTER_PORT))
        for _ in range(copies):
            s.sendall(zpl.encode())


async def labelary_preview(zpl: str) -> str:
    """Return a base64 data-URL PNG from the Labelary API, or empty string on failure."""
    url = (
        f"http://api.labelary.com/v1/printers/{LABEL_DPI}"
        f"/labels/{LABEL_WIDTH}x{LABEL_HEIGHT}/0/"
    )
    async with httpx.AsyncClient(timeout=5) as client:
        r = await client.post(url, content=zpl.encode(), headers={"Accept": "image/png"})
    if r.status_code == 200:
        return "data:image/png;base64," + base64.b64encode(r.content).decode()
    return ""


def render_page(
    sku: str = "",
    batch: str = "",
    copies: int = 1,
    message: str = "",
    message_class: str = "",
    preview_src: str = "",
) -> str:
    """Build the full HTML page as a string."""
    msg_html = f'<p class="msg {message_class}">{message}</p>' if message else ""
    preview_html = (
        f'<div class="preview"><img src="{preview_src}" alt="Label preview"></div>'
        if preview_src else ""
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Batch Label Printer</title>
  <style>
    body    {{ font-family: sans-serif; max-width: 480px; margin: 60px auto; padding: 0 16px; }}
    label   {{ display: block; margin-top: 14px; font-weight: bold; }}
    input   {{ width: 100%; padding: 8px; margin-top: 4px; box-sizing: border-box; font-size: 1rem; }}
    button  {{ margin-top: 20px; padding: 10px 28px; background: #222; color: #fff;
               border: none; cursor: pointer; font-size: 1rem; }}
    button:hover {{ background: #444; }}
    .msg    {{ margin-top: 16px; padding: 10px 14px; border-radius: 4px; }}
    .ok     {{ background: #e8f5e9; border: 1px solid #4caf50; }}
    .err    {{ background: #fdecea; border: 1px solid #f44336; }}
    .preview     {{ margin-top: 24px; }}
    .preview img {{ max-width: 100%; border: 1px solid #ccc; }}
  </style>
</head>
<body>
  <h1>Batch Label Printer</h1>
  {msg_html}
  <form method="post" action="/print">
    <label>SKU</label>
    <input name="sku" value="{sku}" required pattern="[A-Za-z0-9-]+" placeholder="e.g. WIDGET-42">
    <label>Batch</label>
    <input name="batch" value="{batch}" required placeholder="e.g. 2024-B01">
    <label>Quantity</label>
    <input type="number" name="copies" value="{copies}" min="1" max="999" required>
    <button type="submit">Print Labels</button>
  </form>
  {preview_html}
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def index():
    return render_page()


@app.post("/print", response_class=HTMLResponse)
async def print_labels(
    sku: str = Form(...),
    batch: str = Form(...),
    copies: int = Form(...),
):
    zpl = build_zpl(sku, batch)
    preview_src = await labelary_preview(zpl)

    try:
        send_to_printer(zpl, copies)
        message = f"Sent {copies} label(s) — SKU: {sku}, Batch: {batch}"
        message_class = "ok"
    except OSError as e:
        message = f"Print failed: {e}"
        message_class = "err"

    return render_page(
        sku=sku, batch=batch, copies=copies,
        message=message, message_class=message_class,
        preview_src=preview_src,
    )
