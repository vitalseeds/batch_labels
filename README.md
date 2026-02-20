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

### Printer

| Variable       | Default         | Description                   |
|----------------|-----------------|-------------------------------|
| `PRINTER_HOST` | `192.168.1.100` | Printer IP address            |
| `PRINTER_PORT` | `9100`          | RAW TCP port (Zebra standard) |

### Label dimensions

| Variable       | Default | Description                   |
|----------------|---------|-------------------------------|
| `LABEL_WIDTH`  | `2.76`  | Label width in inches (70 mm) |
| `LABEL_HEIGHT` | `1.42`  | Label height in inches (36 mm)|
| `LABEL_DPI`    | `203`   | Printer DPI (GK420D = 203)    |

### Fonts

ZPL built-in fonts: `0`=scalable (any size), `A`=9 pt, `B`=11 pt, `D`=18 pt, `E`=28 pt, `F`=26 pt bold, `G`=60 pt, `H`=21 pt bold

| Variable           | Default | Description             |
|--------------------|---------|-------------------------|
| `SKU_LABEL_FONT`   | `G`     | ZPL font for SKU text   |
| `BATCH_LABEL_FONT` | `1`     | ZPL font for batch text |

### Text size (mm)

| Variable            | Default | Description                 |
|---------------------|---------|-----------------------------|
| `SKU_CHAR_HEIGHT`   | `18`    | SKU character height (mm)   |
| `SKU_CHAR_WIDTH`    | `12`    | SKU character width (mm)    |
| `BATCH_CHAR_HEIGHT` | `7`     | Batch character height (mm) |
| `BATCH_CHAR_WIDTH`  | `4`     | Batch character width (mm)  |

### Padding (mm)

| Variable               | Default | Description                          |
|------------------------|---------|--------------------------------------|
| `SKU_PADDING_LEFT`     | `5`     | SKU distance from left edge (mm)     |
| `SKU_PADDING_TOP`      | `5`     | SKU distance from top edge (mm)      |
| `BATCH_PADDING_BOTTOM` | `6`     | Batch distance from bottom edge (mm) |
| `BATCH_PADDING_RIGHT`  | `5`     | Batch distance from right edge (mm)  |

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
