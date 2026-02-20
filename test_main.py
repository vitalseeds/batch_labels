"""Tests for the batch label printer."""

import pytest
import httpx
from unittest.mock import patch, AsyncMock

import main
from main import app, build_zpl, find_similar_skus


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


# --- SKU validation ---

def test_find_similar_skus_no_list():
    """No SKU_LIST loaded → always returns None (skip validation)."""
    with patch.object(main, "SKU_LIST", set()):
        assert find_similar_skus("ANYTHING") is None


def test_find_similar_skus_valid():
    with patch.object(main, "SKU_LIST", {"ToGD", "ToML", "ToBC"}):
        assert find_similar_skus("ToGD") is None


def test_find_similar_skus_invalid_with_suggestions():
    with patch.object(main, "SKU_LIST", {"ToGD", "ToML", "ToBC"}):
        result = find_similar_skus("ToGX")
        assert result is not None
        assert "ToGD" in result


def test_find_similar_skus_invalid_no_suggestions():
    with patch.object(main, "SKU_LIST", {"ToGD", "ToML", "ToBC"}):
        result = find_similar_skus("ZZZZZZ")
        assert result == []


@pytest.mark.asyncio
async def test_print_invalid_sku_shows_warning(client):
    with patch.object(main, "SKU_LIST", {"ToGD", "ToML"}):
        r = await client.post("/print", data={"sku": "BOGUS", "batch": "B1", "copies": "1"})
    assert r.status_code == 200
    assert "warn" in r.text
    assert "BOGUS" in r.text
    assert "Sent" not in r.text


@pytest.mark.asyncio
async def test_print_invalid_sku_shows_suggestions(client):
    with patch.object(main, "SKU_LIST", {"ToGD", "ToML", "ToBC"}):
        r = await client.post("/print", data={"sku": "ToGX", "batch": "B1", "copies": "1"})
    assert r.status_code == 200
    assert "ToGD" in r.text


@pytest.mark.asyncio
async def test_print_force_bypasses_validation(client):
    with (
        patch.object(main, "SKU_LIST", {"ToGD", "ToML"}),
        patch("main.send_to_printer"),
        patch("main.labelary_preview", new_callable=AsyncMock, return_value=""),
    ):
        r = await client.post("/print", data={"sku": "BOGUS", "batch": "B1", "copies": "1", "force": "1"})
    assert r.status_code == 200
    assert "Sent" in r.text


@pytest.mark.asyncio
async def test_preview_invalid_sku_shows_warning(client):
    with (
        patch.object(main, "SKU_LIST", {"ToGD", "ToML"}),
        patch("main.zpl_preview", new_callable=AsyncMock, return_value=""),
    ):
        r = await client.post("/preview", data={"sku": "BOGUS", "batch": "B1", "copies": "1"})
    assert r.status_code == 200
    assert "warn" in r.text
    assert "BOGUS" in r.text
