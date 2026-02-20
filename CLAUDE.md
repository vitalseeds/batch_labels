# Batch label printer

Super simple FastAPI app to print ZPL labels in batches to a Zebra network printer.

## What it does

- Serves a single HTML form at `http://localhost:8000/`
- Takes a SKU, batch number, and quantity
- Generates a ZPL label (SKU text + Code-128 barcode + batch number)
- Sends the label to a Zebra printer over TCP (raw port 9100)
- Previews the label using the [Labelary API](https://labelary.com/)

## Stack

- **FastAPI** — web framework
- **httpx** — async HTTP client for Labelary preview
- **uvicorn** — ASGI server
- Raw ZPL strings (no external ZPL library)

## Key files

- `main.py` — entire app (ZPL generation, printer comms, HTML, routes)
- `test_main.py` — integration tests (mock printer + Labelary)
- `pyproject.toml` — dependencies

## Config

All constants are read from environment variables (`.env` supported). Defaults are set at the top of `main.py`.

### Printer

| Constant       | Default         | Description                        |
|----------------|-----------------|------------------------------------|
| `PRINTER_HOST` | `192.168.1.100` | Printer IP address                 |
| `PRINTER_PORT` | `9100`          | RAW TCP port (Zebra standard)      |

### Label dimensions

| Constant       | Default  | Description                              |
|----------------|----------|------------------------------------------|
| `LABEL_WIDTH`  | `2.76`   | Label width in inches (70 mm)            |
| `LABEL_HEIGHT` | `1.42`   | Label height in inches (36 mm)           |
| `LABEL_DPI`    | `203`    | Printer DPI (GK420D = 203)               |

### Fonts

ZPL built-in fonts: `0`=scalable (any size), `A`=9 pt, `B`=11 pt, `D`=18 pt, `E`=28 pt, `F`=26 pt bold, `G`=60 pt, `H`=21 pt bold

| Constant          | Default | Description              |
|-------------------|---------|--------------------------|
| `SKU_LABEL_FONT`  | `G`     | ZPL font for SKU text    |
| `BATCH_LABEL_FONT`| `1`     | ZPL font for batch text  |

### Text size (mm)

| Constant           | Default | Description                  |
|--------------------|---------|------------------------------|
| `SKU_CHAR_HEIGHT`  | `18`    | SKU character height (mm)    |
| `SKU_CHAR_WIDTH`   | `12`    | SKU character width (mm)     |
| `BATCH_CHAR_HEIGHT`| `7`     | Batch character height (mm)  |
| `BATCH_CHAR_WIDTH` | `4`     | Batch character width (mm)   |

### Padding (mm)

| Constant              | Default | Description                         |
|-----------------------|---------|-------------------------------------|
| `SKU_PADDING_LEFT`    | `5`     | SKU distance from left edge (mm)    |
| `SKU_PADDING_TOP`     | `5`     | SKU distance from top edge (mm)     |
| `BATCH_PADDING_BOTTOM`| `6`     | Batch distance from bottom edge (mm)|
| `BATCH_PADDING_RIGHT` | `5`     | Batch distance from right edge (mm) |

## Running

```bash
uv run uvicorn main:app --reload
```

## Testing

```bash
uv run pytest
```

## Linting

```bashuv
uv run ruff check . --fix
```