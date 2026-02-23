# Batch Label Printer

Prints ZPL labels in batches to a Zebra network printer.

## Install (Windows — standalone exe)

1. Download `sku-labels.exe` from the [latest release](../../releases/latest)
2. Create a `.env` config file at `%LOCALAPPDATA%\batch-labels\.env`
   (e.g. `C:\Users\you\AppData\Local\batch-labels\.env`)
3. Double-click `sku-labels.exe` — the app starts on `http://localhost:8765`

## Install (from source)

Requires Python 3.14+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run uvicorn batch_labels.main:app --reload
```

## Configuration

Config is read from a `.env` file. Copy `.env.example` to the appropriate location:

| Platform | Path |
|----------|------|
| Windows (standalone) | `%LOCALAPPDATA%\batch-labels\.env` |
| macOS (standalone) | `~/Library/Application Support/batch-labels/.env` |
| Dev (any platform) | `.env` in the project root |

```ini
PRINTER_HOST=192.168.1.100   # Printer IP
PRINTER_PORT=9100            # RAW TCP port (Zebra default)
LABEL_WIDTH=70               # mm
LABEL_HEIGHT=36              # mm
LABEL_DPI=203                # GK420D = 203
SKU_LIST_FILE=skus.csv       # Optional: path to CSV of valid SKUs
UPDATE_ON_START=true         # Optional: auto-update exe on startup (standalone only)
```

Label layout (fonts, text size, padding) can also be set in `.env` — or adjusted live in the **Label layout** panel in the UI and copied out.

## Use

Open [http://localhost:8765](http://localhost:8765), fill in **SKU**, **Batch**, and **Quantity**, then:

- **Preview** — renders a label image without printing
- **Print Labels** — sends ZPL to the printer
- **Print Anyway** — bypasses SKU validation

## Development

```bash
uv run pytest                          # tests (no hardware needed)
uv run ruff check . --fix              # lint
uv run python deploy/build.py --clean  # build standalone exe
```
