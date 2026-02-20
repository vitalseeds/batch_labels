# Batch Label Printer

A minimal FastAPI app for printing ZPL labels in batches to a Zebra network printer.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- A Zebra printer reachable over the network (tested on GK420D)

## Setup

```bash
uv sync
```

## Configuration

Copy `.env.example` to `.env` and edit to match your printer:

```bash
cp .env.example .env
```

```ini
PRINTER_HOST=192.168.1.100   # printer IP
PRINTER_PORT=9100            # RAW TCP port (Zebra standard)
LABEL_WIDTH=4                # inches
LABEL_HEIGHT=2               # inches
LABEL_DPI=203                # GK420D native DPI
```

## Running

```bash
uv run uvicorn main:app --reload
```

Then open [http://localhost:8000](http://localhost:8000).

Fill in the **SKU**, **Batch**, and **Quantity** fields and click **Print Labels**.
A preview of the label is shown below the form (via the [Labelary API](https://labelary.com/)).

## Label format

Each label contains:
- SKU as large text
- SKU as a Code-128 barcode
- Batch number

## Testing

```bash
uv run pytest
```

Tests mock both the printer socket and the Labelary API call — no hardware needed.
