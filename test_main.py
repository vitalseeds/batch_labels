"""Tests for the batch label printer."""

import pytest
import httpx
from unittest.mock import patch, AsyncMock

from main import app, build_zpl


def test_build_zpl_contains_sku_and_batch():
    zpl = build_zpl("ABC123", "B001")
    assert "ABC123" in zpl
    assert "B001" in zpl
    assert zpl.startswith("^XA")
    assert zpl.endswith("^XZ")


@pytest.fixture
def client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_index_returns_form(client):
    r = await client.get("/")
    assert r.status_code == 200
    assert "<form" in r.text
    assert 'name="sku"' in r.text


@pytest.mark.asyncio
async def test_print_success(client):
    with (
        patch("main.send_to_printer") as mock_print,
        patch("main.labelary_preview", new_callable=AsyncMock, return_value=""),
    ):
        r = await client.post("/print", data={"sku": "SKU01", "batch": "B1", "copies": "3"})

    assert r.status_code == 200
    assert "Sent 3 label" in r.text
    assert "ok" in r.text
    mock_print.assert_called_once()


@pytest.mark.asyncio
async def test_print_printer_error(client):
    with (
        patch("main.send_to_printer", side_effect=OSError("Connection refused")),
        patch("main.labelary_preview", new_callable=AsyncMock, return_value=""),
    ):
        r = await client.post("/print", data={"sku": "SKU01", "batch": "B1", "copies": "1"})

    assert r.status_code == 200
    assert "Print failed" in r.text
    assert "err" in r.text


@pytest.mark.asyncio
async def test_print_shows_preview_image(client):
    fake_data_url = "data:image/png;base64,ABC"
    with (
        patch("main.send_to_printer"),
        patch("main.labelary_preview", new_callable=AsyncMock, return_value=fake_data_url),
    ):
        r = await client.post("/print", data={"sku": "SKU99", "batch": "B9", "copies": "1"})

    assert r.status_code == 200
    assert fake_data_url in r.text
