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

Edit the constants at the top of `main.py`:

| Constant        | Default         | Description                   |
|-----------------|-----------------|-------------------------------|
| `PRINTER_HOST`  | `192.168.1.100` | Printer IP address             |
| `PRINTER_PORT`  | `9100`          | RAW TCP port (Zebra standard)  |
| `LABEL_WIDTH`   | `4`             | Label width in inches          |
| `LABEL_HEIGHT`  | `2`             | Label height in inches         |
| `LABEL_DPI`     | `203`           | Printer DPI (GK420D = 203)     |
| `LABEL_FONT`    | `0`             | ZPL font (`0`=scalable, `A`–`Z`=bitmap) |

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