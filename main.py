"""
Batch label printer — FastAPI app for printing ZPL labels to a Zebra network printer.
Fill in the form, preview the label, and send it to the printer.
"""

import asyncio
import base64
import os
import socket
import tempfile

import httpx
import zpl as zpl_lib
from dotenv import load_dotenv
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse

load_dotenv()

app = FastAPI()

PRINTER_HOST = os.getenv("PRINTER_HOST", "192.168.1.100")
PRINTER_PORT = int(os.getenv("PRINTER_PORT", "9100"))
LABEL_WIDTH   = float(os.getenv("LABEL_WIDTH", "2.76"))   # 70mm
LABEL_HEIGHT  = float(os.getenv("LABEL_HEIGHT", "1.42"))  # 36mm
LABEL_DPI     = int(os.getenv("LABEL_DPI", "203"))
# 0=scalable (use any size), A=9pt, B=11pt, D=18pt, E=28pt, F=26pt bold, G=60pt, H=21pt bold
SKU_LABEL_FONT    = os.getenv("SKU_LABEL_FONT", "G")
BATCH_LABEL_FONT  = os.getenv("SKU_LABEL_FONT", "1")

SKU_CHAR_HEIGHT   = float(os.getenv("SKU_CHAR_HEIGHT",   "18"))  # mm
SKU_CHAR_WIDTH    = float(os.getenv("SKU_CHAR_WIDTH",    "12"))  # mm
BATCH_CHAR_HEIGHT = float(os.getenv("BATCH_CHAR_HEIGHT",  "7"))  # mm
BATCH_CHAR_WIDTH  = float(os.getenv("BATCH_CHAR_WIDTH",   "4"))  # mm

SKU_PADDING_LEFT   = float(os.getenv("SKU_PADDING_LEFT",   "5"))  # mm from left edge
SKU_PADDING_TOP    = float(os.getenv("SKU_PADDING_TOP",    "5"))  # mm from top edge
BATCH_PADDING_BOTTOM = float(os.getenv("BATCH_PADDING_BOTTOM", "6"))  # mm from bottom edge
BATCH_PADDING_RIGHT  = float(os.getenv("BATCH_PADDING_RIGHT",  "5"))  # mm from right edge


def build_zpl(sku: str, batch: str) -> str:
    """Return ZPL for a 70×36mm landscape label."""
    dpmm = LABEL_DPI / 25.4
    sku_h   = round(SKU_CHAR_HEIGHT   * dpmm)
    sku_w   = round(SKU_CHAR_WIDTH    * dpmm)
    batch_h = round(BATCH_CHAR_HEIGHT * dpmm)
    batch_w = round(BATCH_CHAR_WIDTH  * dpmm)
    sku_x       = round(SKU_PADDING_LEFT * dpmm)
    sku_y       = round(SKU_PADDING_TOP  * dpmm)
    batch_y     = round((LABEL_HEIGHT * 25.4 - BATCH_CHAR_HEIGHT - BATCH_PADDING_BOTTOM) * dpmm)
    batch_field = round((LABEL_WIDTH  * 25.4 - SKU_PADDING_LEFT  - BATCH_PADDING_RIGHT)  * dpmm)
    return (
        "^XA"
        f"^FO{sku_x},{sku_y}^A{SKU_LABEL_FONT}N,{sku_h},{sku_w}^FD{sku}^FS"
        f"^FO{sku_x},{batch_y}^A{BATCH_LABEL_FONT}N,{batch_h},{batch_w}^FB{batch_field},1,,R^FD{batch}^FS"
        "^XZ"
    )


def build_label(sku: str, batch: str) -> zpl_lib.Label:
    """Return a zpl.Label matching the same 70×36mm design."""
    dpmm = round(LABEL_DPI / 25.4)  # 203 DPI → 8 dpmm
    label_w_mm = LABEL_WIDTH  * 25.4
    label_h_mm = LABEL_HEIGHT * 25.4
    batch_origin_y = label_h_mm - BATCH_CHAR_HEIGHT - BATCH_PADDING_BOTTOM
    batch_line_w   = label_w_mm - SKU_PADDING_LEFT - BATCH_PADDING_RIGHT
    label = zpl_lib.Label(label_h_mm, label_w_mm, dpmm)
    label.origin(SKU_PADDING_LEFT, SKU_PADDING_TOP)
    label.write_text(sku, char_height=SKU_CHAR_HEIGHT, char_width=SKU_CHAR_WIDTH, font=SKU_LABEL_FONT)
    label.endorigin()
    label.origin(SKU_PADDING_LEFT, batch_origin_y)
    label.write_text(batch, char_height=BATCH_CHAR_HEIGHT, char_width=BATCH_CHAR_WIDTH, line_width=batch_line_w, justification="R", font=BATCH_LABEL_FONT)
    label.endorigin()
    return label


async def zpl_preview(sku: str, batch: str) -> str:
    """Return a base64 data-URL PNG using zpl.Label.preview(), or empty string on failure."""
    label = build_label(sku, batch)
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: label.preview(outputfile=tmp_path))
        with open(tmp_path, "rb") as f:
            return "data:image/png;base64," + base64.b64encode(f.read()).decode()
    except Exception:
        return ""
    finally:
        if "tmp_path" in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)


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
    .buttons {{ margin-top: 20px; display: flex; gap: 10px; }}
    button  {{ padding: 10px 28px; border: none; cursor: pointer; font-size: 1rem; }}
    button.btn-print   {{ background: #222; color: #fff; }}
    button.btn-print:hover {{ background: #444; }}
    button.btn-preview {{ background: #fff; color: #222; border: 1px solid #222; }}
    button.btn-preview:hover {{ background: #f0f0f0; }}
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
    <input name="sku" value="{sku}" required pattern="[A-Za-z0-9-]+" placeholder="e.g. ToGD">
    <label>Batch</label>
    <input name="batch" value="{batch}" required placeholder="e.g. 12345">
    <label>Quantity</label>
    <input type="number" name="copies" value="{copies}" min="1" max="999" required>
    <div class="buttons">
      <button class="btn-preview" type="submit" formaction="/preview">Preview</button>
      <button class="btn-print"   type="submit">Print Labels</button>
    </div>
  </form>
  {preview_html}
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def index():
    return render_page()


@app.post("/preview", response_class=HTMLResponse)
async def preview_label(
    sku: str = Form(...),
    batch: str = Form(...),
    copies: int = Form(...),
):
    preview_src = await zpl_preview(sku, batch)
    return render_page(sku=sku, batch=batch, copies=copies, preview_src=preview_src)


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
