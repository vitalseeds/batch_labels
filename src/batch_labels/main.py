"""
Batch label printer — FastAPI app for printing ZPL labels to a Zebra network printer.
Fill in the form, preview the label, and send it to the printer.
"""

import asyncio
import base64
import csv
import json
import os
import socket
import tempfile
from contextlib import asynccontextmanager
from dataclasses import dataclass
from difflib import get_close_matches

import httpx
import zpl as zpl_lib
from dotenv import load_dotenv
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
from pathlib import Path
from platformdirs import user_data_dir

# Standalone: reads config from platform app-data dir (e.g. %LOCALAPPDATA%\batch-labels\.env)
# Dev: local .env overrides via the second load_dotenv call
CONFIG_DIR = Path(user_data_dir("batch-labels", False))
load_dotenv(CONFIG_DIR / ".env")
load_dotenv(override=True)  # local .env wins in dev

SKU_LIST: set[str] = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global SKU_LIST
    env_app   = CONFIG_DIR / ".env"
    env_local = Path(".env")
    if env_app.exists():
        print(f"Config:  {env_app}")
    if env_local.exists():
        print(f"Config:  {env_local.resolve()}")
    if not env_app.exists() and not env_local.exists():
        print(f"Config:  no .env found — expected {env_app}")
    sku_file = os.getenv("SKU_LIST_FILE")
    if sku_file:
        try:
            with open(sku_file, newline="") as f:
                reader = csv.DictReader(f)
                col = (reader.fieldnames or ["SKU"])[0]
                SKU_LIST = {row[col].strip() for row in reader if row[col].strip()}
            print(f"Loaded {len(SKU_LIST)} SKUs from {sku_file!r} (column: {col!r})")
        except OSError as e:
            print(f"Warning: could not load SKU_LIST_FILE {sku_file!r}: {e}")
    yield


app = FastAPI(lifespan=lifespan)

PRINTER_HOST = os.getenv("PRINTER_HOST", "192.168.1.100")
PRINTER_PORT = int(os.getenv("PRINTER_PORT", "9100"))
LABEL_WIDTH   = float(os.getenv("LABEL_WIDTH", "70"))   # mm
LABEL_HEIGHT  = float(os.getenv("LABEL_HEIGHT", "36"))  # mm
LABEL_DPI     = int(os.getenv("LABEL_DPI", "203"))
# 0=scalable (use any size), A=9pt, B=11pt, D=18pt, E=28pt, F=26pt bold, G=60pt, H=21pt bold
SKU_LABEL_FONT    = os.getenv("SKU_LABEL_FONT", "G")
BATCH_LABEL_FONT  = os.getenv("BATCH_LABEL_FONT", "1")

SKU_CHAR_HEIGHT   = float(os.getenv("SKU_CHAR_HEIGHT",   "0"))  # mm; 0 = use font's own size
SKU_CHAR_WIDTH    = float(os.getenv("SKU_CHAR_WIDTH",    "0"))  # mm; 0 = use font's own size
BATCH_CHAR_HEIGHT = float(os.getenv("BATCH_CHAR_HEIGHT", "0"))  # mm; 0 = use font's own size
BATCH_CHAR_WIDTH  = float(os.getenv("BATCH_CHAR_WIDTH",  "0"))  # mm; 0 = use font's own size

SKU_PADDING_LEFT   = float(os.getenv("SKU_PADDING_LEFT",   "5"))  # mm from left edge
SKU_PADDING_TOP    = float(os.getenv("SKU_PADDING_TOP",    "5"))  # mm from top edge
BATCH_PADDING_BOTTOM = float(os.getenv("BATCH_PADDING_BOTTOM", "4"))  # mm from bottom edge
BATCH_PADDING_RIGHT  = float(os.getenv("BATCH_PADDING_RIGHT",  "4"))  # mm from right edge


@dataclass
class LabelConfig:
    label_width: float = 0.0
    label_height: float = 0.0
    label_dpi: int = 0
    sku_label_font: str = ""
    batch_label_font: str = ""
    sku_char_height: float = 0.0
    sku_char_width: float = 0.0
    batch_char_height: float = 0.0
    batch_char_width: float = 0.0
    sku_padding_left: float = 0.0
    sku_padding_top: float = 0.0
    batch_padding_bottom: float = 0.0
    batch_padding_right: float = 0.0

    def __post_init__(self):
        if not self.label_width:
            self.label_width = LABEL_WIDTH
        if not self.label_height:
            self.label_height = LABEL_HEIGHT
        if not self.label_dpi:
            self.label_dpi = LABEL_DPI
        if not self.sku_label_font:
            self.sku_label_font = SKU_LABEL_FONT
        if not self.batch_label_font:
            self.batch_label_font = BATCH_LABEL_FONT
        if not self.sku_char_height:
            self.sku_char_height = SKU_CHAR_HEIGHT
        if not self.sku_char_width:
            self.sku_char_width = SKU_CHAR_WIDTH
        if not self.batch_char_height:
            self.batch_char_height = BATCH_CHAR_HEIGHT
        if not self.batch_char_width:
            self.batch_char_width = BATCH_CHAR_WIDTH
        if not self.sku_padding_left:
            self.sku_padding_left = SKU_PADDING_LEFT
        if not self.sku_padding_top:
            self.sku_padding_top = SKU_PADDING_TOP
        if not self.batch_padding_bottom:
            self.batch_padding_bottom = BATCH_PADDING_BOTTOM
        if not self.batch_padding_right:
            self.batch_padding_right = BATCH_PADDING_RIGHT


def find_similar_skus(sku: str) -> list[str] | None:
    """Return None if SKU is valid (or no list loaded), else a list of close matches."""
    if not SKU_LIST or sku in SKU_LIST:
        return None
    return get_close_matches(sku, SKU_LIST, n=5, cutoff=0.4)


def build_zpl(sku: str, batch: str, cfg: LabelConfig) -> str:
    """Return ZPL for a landscape label."""
    dpmm = cfg.label_dpi / 25.4
    sku_x       = round(cfg.sku_padding_left * dpmm)
    sku_y       = round(cfg.sku_padding_top  * dpmm)
    batch_y     = round((cfg.label_height - cfg.batch_char_height - cfg.batch_padding_bottom) * dpmm)
    batch_field = round((cfg.label_width  - cfg.sku_padding_left  - cfg.batch_padding_right)  * dpmm)
    sku_size   = f",{round(cfg.sku_char_height * dpmm)},{round(cfg.sku_char_width * dpmm)}" if cfg.sku_char_height and cfg.sku_char_width else ""
    batch_size = f",{round(cfg.batch_char_height * dpmm)},{round(cfg.batch_char_width * dpmm)}" if cfg.batch_char_height and cfg.batch_char_width else ""
    return (
        "^XA"
        f"^FO{sku_x},{sku_y}^A{cfg.sku_label_font}N{sku_size}^FD{sku}^FS"
        f"^FO{sku_x},{batch_y}^A{cfg.batch_label_font}N{batch_size}^FB{batch_field},1,,R^FD{batch}^FS"
        "^XZ"
    )


def build_label(sku: str, batch: str, cfg: LabelConfig) -> zpl_lib.Label:
    """Return a zpl.Label for the given config."""
    dpmm = round(cfg.label_dpi / 25.4)
    batch_origin_y = cfg.label_height - cfg.batch_char_height - cfg.batch_padding_bottom
    batch_line_w   = cfg.label_width  - cfg.sku_padding_left  - cfg.batch_padding_right
    label = zpl_lib.Label(cfg.label_height, cfg.label_width, dpmm)
    label.origin(cfg.sku_padding_left, cfg.sku_padding_top)
    sku_size   = {"char_height": cfg.sku_char_height,   "char_width": cfg.sku_char_width}   if cfg.sku_char_height   and cfg.sku_char_width   else {}
    batch_size = {"char_height": cfg.batch_char_height, "char_width": cfg.batch_char_width} if cfg.batch_char_height and cfg.batch_char_width else {}
    label.write_text(sku, font=cfg.sku_label_font, **sku_size)
    label.endorigin()
    label.origin(cfg.sku_padding_left, batch_origin_y)
    label.write_text(batch, font=cfg.batch_label_font, line_width=batch_line_w, justification="R", **batch_size)
    label.endorigin()
    return label


async def zpl_preview(sku: str, batch: str, cfg: LabelConfig) -> str:
    """Return a base64 data-URL PNG using zpl.Label.preview(), or empty string on failure."""
    label = build_label(sku, batch, cfg)
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


async def labelary_preview(zpl: str, cfg: LabelConfig) -> str:
    """Return a base64 data-URL PNG from the Labelary API, or empty string on failure."""
    url = (
        f"http://api.labelary.com/v1/printers/{cfg.label_dpi}"
        f"/labels/{cfg.label_width / 25.4:.4f}x{cfg.label_height / 25.4:.4f}/0/"
    )
    async with httpx.AsyncClient(timeout=5) as client:
        r = await client.post(url, content=zpl.encode(), headers={"Accept": "image/png"})
    if r.status_code == 200:
        return "data:image/png;base64," + base64.b64encode(r.content).decode()
    return ""


_FONTS = [
    ("0", "0 — scalable"),
    ("A", "A — 9 pt"),
    ("B", "B — 11 pt"),
    ("D", "D — 18 pt"),
    ("E", "E — 28 pt"),
    ("F", "F — 26 pt bold"),
    ("G", "G — 60 pt"),
    ("H", "H — 21 pt bold"),
]


_ENV_FIELDS = [
    ("label_width",        "LABEL_WIDTH"),
    ("label_height",       "LABEL_HEIGHT"),
    ("label_dpi",          "LABEL_DPI"),
    ("sku_label_font",     "SKU_LABEL_FONT"),
    ("batch_label_font",   "BATCH_LABEL_FONT"),
    ("sku_char_height",    "SKU_CHAR_HEIGHT"),
    ("sku_char_width",     "SKU_CHAR_WIDTH"),
    ("batch_char_height",  "BATCH_CHAR_HEIGHT"),
    ("batch_char_width",   "BATCH_CHAR_WIDTH"),
    ("sku_padding_left",   "SKU_PADDING_LEFT"),
    ("sku_padding_top",    "SKU_PADDING_TOP"),
    ("batch_padding_bottom", "BATCH_PADDING_BOTTOM"),
    ("batch_padding_right",  "BATCH_PADDING_RIGHT"),
]


def _env_text(cfg: LabelConfig) -> str:
    vals = {
        "label_width": cfg.label_width, "label_height": cfg.label_height,
        "label_dpi": cfg.label_dpi, "sku_label_font": cfg.sku_label_font,
        "batch_label_font": cfg.batch_label_font, "sku_char_height": cfg.sku_char_height,
        "sku_char_width": cfg.sku_char_width, "batch_char_height": cfg.batch_char_height,
        "batch_char_width": cfg.batch_char_width, "sku_padding_left": cfg.sku_padding_left,
        "sku_padding_top": cfg.sku_padding_top, "batch_padding_bottom": cfg.batch_padding_bottom,
        "batch_padding_right": cfg.batch_padding_right,
    }
    return "\n".join(f"{env}={vals[field]}" for field, env in _ENV_FIELDS)


def _font_select(name: str, selected: str) -> str:
    options = "".join(
        f'<option value="{v}"{" selected" if v == selected else ""}>{label}</option>'
        for v, label in _FONTS
    )
    return f'<select name="{name}" class="font-select">{options}</select>'


def render_page(
    sku: str = "",
    batch: str = "",
    copies: int = 1,
    message: str = "",
    message_class: str = "",
    preview_src: str = "",
    similar_skus: list[str] | None = None,
    cfg: LabelConfig | None = None,
) -> str:
    """Build the full HTML page as a string."""
    if cfg is None:
        cfg = LabelConfig()
    msg_html = f'<p class="msg {message_class}">{message}</p>' if message else ""
    preview_style = "" if preview_src else ' style="display:none"'
    preview_html = f'<div class="preview" id="preview-box"{preview_style}><img id="preview-img" src="{preview_src}" alt="Label preview"></div>'
    sku_script = ""
    if SKU_LIST:
        sku_json = json.dumps(sorted(SKU_LIST))
        sku_script = f"""<script>
(function() {{
  var SKUS = {sku_json};
  var input = document.querySelector('[name=sku]');
  var list = document.getElementById('sku-ac');
  var sel = -1;

  function items() {{ return list.querySelectorAll('li'); }}

  function highlight(idx) {{
    items().forEach(function(li, i) {{ li.classList.toggle('active', i === idx); }});
    sel = idx;
  }}

  function pick(li) {{
    input.value = li.textContent;
    list.innerHTML = '';
    sel = -1;
  }}

  function update() {{
    sel = -1;
    var q = input.value.toLowerCase();
    if (!q) {{ list.innerHTML = ''; return; }}
    list.innerHTML = SKUS
      .filter(function(s) {{ return s.toLowerCase().includes(q); }})
      .slice(0, 5)
      .map(function(s) {{ return '<li>' + s + '</li>'; }})
      .join('');
  }}

  input.addEventListener('input', update);
  input.addEventListener('blur', function() {{ list.innerHTML = ''; sel = -1; }});

  input.addEventListener('keydown', function(e) {{
    var lis = items();
    if (!lis.length) return;
    if (e.key === 'ArrowDown') {{ e.preventDefault(); highlight(Math.min(sel + 1, lis.length - 1)); }}
    else if (e.key === 'ArrowUp') {{ e.preventDefault(); highlight(Math.max(sel - 1, 0)); }}
    else if (e.key === 'Enter') {{ var t = lis[sel >= 0 ? sel : 0]; if (t) {{ e.preventDefault(); pick(t); }} }}
    else if (e.key === 'Escape') {{ list.innerHTML = ''; sel = -1; }}
  }});

  list.addEventListener('mousedown', function(e) {{
    if (e.target.tagName !== 'LI') return;
    e.preventDefault();
    pick(e.target);
  }});
}})();
</script>"""

    warn_html = ""
    if similar_skus is not None:
        note = ""
        if similar_skus:
            links = []
            for s in similar_skus:
                onclick = f"document.querySelector('[name=sku]').value='{s}';return false;"
                links.append(f'<a href="#" onclick="{onclick}">{s}</a>')
            note = f'<br>Did you mean: {", ".join(links)}?'
        warn_html = f'<p class="msg warn">Unknown SKU: <strong>{sku}</strong>.{note}</p>'

    env_fields_js = json.dumps([[f, e] for f, e in _ENV_FIELDS])
    env_html = f"""<details class="env-details">
  <summary>Copy to .env</summary>
  <textarea id="env-text" class="env-text" readonly rows="{len(_ENV_FIELDS)}">{_env_text(cfg)}</textarea>
</details>"""

    layout_html = f"""
  <details class="layout-details">
    <summary>Label layout</summary>
    <div class="layout-grid">
      <span class="layout-section">Dimensions</span>
      <label>Width (mm)</label><input type="number" step="0.5" name="label_width" value="{cfg.label_width}">
      <label>Height (mm)</label><input type="number" step="0.5" name="label_height" value="{cfg.label_height}">
      <label>DPI</label><input type="number" name="label_dpi" value="{cfg.label_dpi}">
      <span class="layout-section">Fonts</span>
      <label>SKU font</label>{_font_select("sku_label_font", cfg.sku_label_font)}
      <label>Batch font</label>{_font_select("batch_label_font", cfg.batch_label_font)}
      <span class="layout-section">SKU text size (mm)</span>
      <label>Height</label><input type="number" step="0.5" name="sku_char_height" value="{cfg.sku_char_height}">
      <label>Width</label><input type="number" step="0.5" name="sku_char_width" value="{cfg.sku_char_width}">
      <span class="layout-section">Batch text size (mm)</span>
      <label>Height</label><input type="number" step="0.5" name="batch_char_height" value="{cfg.batch_char_height}">
      <label>Width</label><input type="number" step="0.5" name="batch_char_width" value="{cfg.batch_char_width}">
      <span class="layout-section">SKU padding (mm)</span>
      <label>Left</label><input type="number" step="0.5" name="sku_padding_left" value="{cfg.sku_padding_left}">
      <label>Top</label><input type="number" step="0.5" name="sku_padding_top" value="{cfg.sku_padding_top}">
      <span class="layout-section">Batch padding (mm)</span>
      <label>Bottom</label><input type="number" step="0.5" name="batch_padding_bottom" value="{cfg.batch_padding_bottom}">
      <label>Right</label><input type="number" step="0.5" name="batch_padding_right" value="{cfg.batch_padding_right}">
    </div>
  </details>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Batch Label Printer</title>
  <style>
    body    {{ font-family: sans-serif; max-width: 480px; margin: 60px auto; padding: 0 16px; }}
    label   {{ display: block; margin-top: 14px; font-weight: bold; }}
    input   {{ width: 100%; padding: 8px; margin-top: 4px; box-sizing: border-box; font-size: 1rem; }}
    .buttons {{ margin-top: 20px; display: flex; gap: 10px; flex-wrap: wrap; }}
    button  {{ padding: 10px 28px; border: none; cursor: pointer; font-size: 1rem; }}
    button.btn-print   {{ background: #222; color: #fff; }}
    button.btn-print:hover {{ background: #444; }}
    button.btn-preview {{ background: #fff; color: #222; border: 1px solid #222; }}
    button.btn-preview:hover {{ background: #f0f0f0; }}
    button.btn-force   {{ background: #fff; color: #b71c1c; border: 1px solid #b71c1c; }}
    button.btn-force:hover {{ background: #fdecea; }}
    .msg    {{ margin-top: 16px; padding: 10px 14px; border-radius: 4px; }}
    .ok     {{ background: #e8f5e9; border: 1px solid #4caf50; }}
    .err    {{ background: #fdecea; border: 1px solid #f44336; }}
    .warn   {{ background: #fff8e1; border: 1px solid #ffc107; }}
    .warn a {{ color: #b45309; font-weight: bold; }}
    .ac-wrap {{ position: relative; }}
    .ac-list {{ position: absolute; width: 100%; border: 1px solid #ccc; background: #fff;
                list-style: none; margin: 0; padding: 0; z-index: 10;
                box-shadow: 0 2px 4px rgba(0,0,0,.15); }}
    .ac-list:empty {{ display: none; }}
    .ac-list li {{ padding: 8px 10px; cursor: pointer; }}
    .ac-list li:hover, .ac-list li.active {{ background: #f0f0f0; }}
    .preview     {{ margin-top: 24px; }}
    .preview img {{ max-width: 100%; border: 1px solid #ccc; }}
    .layout-details {{ margin-top: 20px; border: 1px solid #ddd; border-radius: 4px; padding: 8px 12px; }}
    .layout-details summary {{ cursor: pointer; font-weight: bold; padding: 4px 0; user-select: none; }}
    .layout-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 4px 12px; margin-top: 10px; align-items: center; }}
    .layout-grid label {{ font-weight: normal; margin: 0; font-size: 0.875rem; }}
    .layout-grid input, .layout-grid .font-select {{ font-size: 0.875rem; padding: 4px 6px; margin: 0; width: 100%; box-sizing: border-box; }}
    .layout-section {{ grid-column: 1 / -1; font-size: 0.7rem; font-weight: bold; text-transform: uppercase;
                       letter-spacing: 0.05em; color: #888; margin-top: 10px; padding-top: 6px;
                       border-top: 1px solid #eee; }}
    .layout-section:first-child {{ margin-top: 0; border-top: none; }}
    .env-details {{ margin-top: 16px; }}
    .env-details summary {{ cursor: pointer; font-weight: bold; padding: 4px 0; user-select: none; }}
    .env-text {{ width: 100%; font-family: monospace; font-size: 0.8rem; padding: 8px; box-sizing: border-box;
                 border: 1px solid #ddd; background: #f8f8f8; resize: none; margin-top: 8px; }}
  </style>
</head>
<body>
  <h1>Batch Label Printer</h1>
  {msg_html}
  {warn_html}
  <form method="post" action="/print">
    <label>SKU</label>
    <div class="ac-wrap">
      <input name="sku" value="{sku}" required pattern="[A-Za-z0-9-]+" placeholder="e.g. ToGD" autocomplete="off">
      <ul id="sku-ac" class="ac-list"></ul>
    </div>
    <label>Batch</label>
    <input name="batch" value="{batch}" required placeholder="e.g. 12345">
    <label>Quantity</label>
    <input type="number" name="copies" value="{copies}" min="1" max="999" required>
    {layout_html}
    <div class="buttons">
      <button class="btn-preview" type="submit" formaction="/preview">Preview</button>
      <button class="btn-print"   type="submit">Print Labels</button>
      <button class="btn-force"   type="submit" name="force" value="1">Print Anyway</button>
    </div>
  </form>
  {preview_html}
  {env_html}
  {sku_script}
  <script>
(function() {{
  var form    = document.querySelector('form');
  var box     = document.getElementById('preview-box');
  var img     = document.getElementById('preview-img');
  var envText = document.getElementById('env-text');
  var timer;
  var ENV_FIELDS = {env_fields_js};

  function refresh() {{
    var sku   = form.querySelector('[name=sku]').value.trim();
    var batch = form.querySelector('[name=batch]').value.trim();
    if (!sku || !batch) return;
    fetch('/preview-img', {{ method: 'POST', body: new FormData(form) }})
      .then(function(r) {{ return r.json(); }})
      .then(function(j) {{
        if (j.src) {{ img.src = j.src; box.style.display = ''; }}
        else        {{ box.style.display = 'none'; }}
      }})
      .catch(function() {{}});
  }}

  function updateEnv() {{
    envText.value = ENV_FIELDS.map(function(p) {{
      var el = form.querySelector('[name=' + p[0] + ']');
      return p[1] + '=' + (el ? el.value : '');
    }}).join('\n');
  }}

  function schedule() {{ clearTimeout(timer); timer = setTimeout(refresh, 500); }}

  form.addEventListener('input',  function() {{ schedule(); updateEnv(); }});
  form.addEventListener('change', function() {{ schedule(); updateEnv(); }});
}})();
  </script>
</body>
</html>"""


def _cfg_from_form(
    label_width: float,
    label_height: float,
    label_dpi: int,
    sku_label_font: str,
    batch_label_font: str,
    sku_char_height: float,
    sku_char_width: float,
    batch_char_height: float,
    batch_char_width: float,
    sku_padding_left: float,
    sku_padding_top: float,
    batch_padding_bottom: float,
    batch_padding_right: float,
) -> LabelConfig:
    return LabelConfig(
        label_width=label_width,
        label_height=label_height,
        label_dpi=label_dpi,
        sku_label_font=sku_label_font,
        batch_label_font=batch_label_font,
        sku_char_height=sku_char_height,
        sku_char_width=sku_char_width,
        batch_char_height=batch_char_height,
        batch_char_width=batch_char_width,
        sku_padding_left=sku_padding_left,
        sku_padding_top=sku_padding_top,
        batch_padding_bottom=batch_padding_bottom,
        batch_padding_right=batch_padding_right,
    )


@app.get("/", response_class=HTMLResponse)
async def index():
    return render_page()


@app.post("/preview", response_class=HTMLResponse)
async def preview_label(
    sku: str = Form(...),
    batch: str = Form(...),
    copies: int = Form(...),
    label_width: float = Form(0.0),
    label_height: float = Form(0.0),
    label_dpi: int = Form(0),
    sku_label_font: str = Form(""),
    batch_label_font: str = Form(""),
    sku_char_height: float = Form(0.0),
    sku_char_width: float = Form(0.0),
    batch_char_height: float = Form(0.0),
    batch_char_width: float = Form(0.0),
    sku_padding_left: float = Form(0.0),
    sku_padding_top: float = Form(0.0),
    batch_padding_bottom: float = Form(0.0),
    batch_padding_right: float = Form(0.0),
):
    cfg = _cfg_from_form(
        label_width, label_height, label_dpi,
        sku_label_font, batch_label_font,
        sku_char_height, sku_char_width,
        batch_char_height, batch_char_width,
        sku_padding_left, sku_padding_top,
        batch_padding_bottom, batch_padding_right,
    )
    similar = find_similar_skus(sku)
    preview_src = await zpl_preview(sku, batch, cfg)
    return render_page(sku=sku, batch=batch, copies=copies, preview_src=preview_src, similar_skus=similar, cfg=cfg)


@app.post("/preview-img")
async def preview_img(
    sku: str = Form(""),
    batch: str = Form(""),
    label_width: float = Form(0.0),
    label_height: float = Form(0.0),
    label_dpi: int = Form(0),
    sku_label_font: str = Form(""),
    batch_label_font: str = Form(""),
    sku_char_height: float = Form(0.0),
    sku_char_width: float = Form(0.0),
    batch_char_height: float = Form(0.0),
    batch_char_width: float = Form(0.0),
    sku_padding_left: float = Form(0.0),
    sku_padding_top: float = Form(0.0),
    batch_padding_bottom: float = Form(0.0),
    batch_padding_right: float = Form(0.0),
):
    if not sku or not batch:
        return {"src": ""}
    cfg = _cfg_from_form(
        label_width, label_height, label_dpi,
        sku_label_font, batch_label_font,
        sku_char_height, sku_char_width,
        batch_char_height, batch_char_width,
        sku_padding_left, sku_padding_top,
        batch_padding_bottom, batch_padding_right,
    )
    return {"src": await zpl_preview(sku, batch, cfg)}


@app.post("/print", response_class=HTMLResponse)
async def print_labels(
    sku: str = Form(...),
    batch: str = Form(...),
    copies: int = Form(...),
    force: bool = Form(False),
    label_width: float = Form(0.0),
    label_height: float = Form(0.0),
    label_dpi: int = Form(0),
    sku_label_font: str = Form(""),
    batch_label_font: str = Form(""),
    sku_char_height: float = Form(0.0),
    sku_char_width: float = Form(0.0),
    batch_char_height: float = Form(0.0),
    batch_char_width: float = Form(0.0),
    sku_padding_left: float = Form(0.0),
    sku_padding_top: float = Form(0.0),
    batch_padding_bottom: float = Form(0.0),
    batch_padding_right: float = Form(0.0),
):
    cfg = _cfg_from_form(
        label_width, label_height, label_dpi,
        sku_label_font, batch_label_font,
        sku_char_height, sku_char_width,
        batch_char_height, batch_char_width,
        sku_padding_left, sku_padding_top,
        batch_padding_bottom, batch_padding_right,
    )

    if not force:
        similar = find_similar_skus(sku)
        if similar is not None:
            return render_page(sku=sku, batch=batch, copies=copies, similar_skus=similar, cfg=cfg)

    zpl = build_zpl(sku, batch, cfg)
    preview_src = await labelary_preview(zpl, cfg)

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
        preview_src=preview_src, cfg=cfg,
    )
