"""
Tests d'intégration LN (API live). Nécessite .env + config/.ionapi.

    INTEGRATION=1 pytest tests/test_api.py -v

Optionnel : INTEGRATION_PO_ID, INTEGRATION_WAREHOUSE_CODE
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

import pytest

from infor_mcp.auth import IONAuthManager
from infor_mcp.client import LNSoapClient
from infor_mcp.services_registry import get_service
from infor_mcp.soap_builder import build_show_envelope

REPO_ROOT = Path(__file__).resolve().parents[1]
KNOWN_ITEMS = ("XALK01", "VTHI880", "VTHG12130")

pytestmark = pytest.mark.integration


def _integration_enabled() -> bool:
    if os.environ.get("INTEGRATION") != "1":
        return False
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")
    ionapi = REPO_ROOT / os.environ.get("IONAPI_PATH", "config/.ionapi")
    return ionapi.is_file() and bool(os.environ.get("INFOR_ION_TENANT_ID"))


def _assert_soap(
    post: dict[str, Any],
    *,
    service: str,
    tenant_id: str,
    company: str | int,
    soap_operation: str,
    inner_request_tag: str,
    must_contain: tuple[str, ...] = (),
) -> None:
    envelope = post["envelope"]
    if isinstance(envelope, bytes):
        envelope = envelope.decode("utf-8")
    assert post["url"].endswith(f"/{tenant_id}/LN/c4ws/services/{service}")
    assert f'xmlns:bo="http://www.infor.com/businessinterface/{service}"' in envelope
    assert f"<company>{company}</company>" in envelope
    assert f"<bo:{soap_operation}>" in envelope
    assert f"<{inner_request_tag}>" in envelope
    for snippet in must_contain:
        assert snippet in envelope


def _records(parsed: dict, entity: str) -> list[dict]:
    data_area = parsed.get("ListResponse", {}).get("DataArea") or parsed.get("DataArea")
    if not data_area:
        return []
    rows = data_area.get(entity)
    if rows is None:
        return []
    return rows if isinstance(rows, list) else [rows]


@pytest.fixture
def api():
    if not _integration_enabled():
        pytest.skip("INTEGRATION=1 + .env + config/.ionapi requis")

    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")
    auth = IONAuthManager(os.environ.get("IONAPI_PATH", "config/.ionapi"))
    client = LNSoapClient(
        auth,
        company=os.environ.get("INFOR_LN_COMPANY", "100"),
        tenant_id=os.environ["INFOR_ION_TENANT_ID"],
    )
    posts: list[dict[str, Any]] = []
    _call = client.call_operation

    async def _record(service: str, envelope: str) -> str:
        posts.append({"url": client._build_url(service), "envelope": envelope, "service": service})
        return await _call(service, envelope)

    client.call_operation = _record  # type: ignore[method-assign]
    client.posts = posts  # type: ignore[attr-defined]
    yield client
    posts.clear()


def _run(coro):
    return asyncio.run(coro)


def _last(api) -> dict[str, Any]:
    assert api.posts
    return api.posts[-1]


# --- Item_v3 ---


@pytest.mark.parametrize("code", KNOWN_ITEMS)
def test_item_list(api, code: str):
    async def go():
        api.posts.clear()
        raw = await api.list_records(
            "Item_v3", fields="itemCode,description",
            filters={"itemCode": code}, limit=5, filter_operator="eq",
        )
        row = _records(json.loads(raw), "Item_v3")[0]
        assert row["itemCode"] == code
        _assert_soap(
            _last(api), service="Item_v3", tenant_id=api.tenant_id, company=api.company,
            soap_operation="List", inner_request_tag="ListRequest",
            must_contain=(f"%{code}%", "<comparisonOperator>like</comparisonOperator>"),
        )

    _run(go())


@pytest.mark.parametrize("code", KNOWN_ITEMS)
def test_item_show(api, code: str):
    async def go():
        api.posts.clear()
        raw = await api.show_record("Item_v3", {"itemCode": code}, fields="itemCode,description")
        parsed = json.loads(raw)
        assert parsed["ShowResponse"]["DataArea"]["Item_v3"]["itemCode"] == code
        assert "<bo:List>" in _last(api)["envelope"]
        assert "<bo:Show>" not in _last(api)["envelope"]

    _run(go())


# --- PurchaseOrder_v3 ---


def test_po_list(api):
    async def go():
        api.posts.clear()
        raw = await api.list_records(
            "PurchaseOrder_v3", fields="orderIdentifier,buyFromSupplierCode,status", limit=3,
        )
        assert _records(json.loads(raw), "PurchaseOrder_v3")
        svc = get_service("PurchaseOrder_v3")
        _assert_soap(
            _last(api), service="PurchaseOrder_v3", tenant_id=api.tenant_id, company=api.company,
            soap_operation=svc.list_operation or "List",
            inner_request_tag=svc.list_request_element or "ListRequest",
            must_contain=("<selectionAttribute>PurchaseOrder_v3.orderIdentifier</selectionAttribute>",),
        )

    _run(go())


def test_po_list_filter(api):
    async def go():
        api.posts.clear()
        await api.list_records(
            "PurchaseOrder_v3", fields="orderIdentifier,status",
            filters={"status": "open"}, limit=5, filter_operator="eq",
        )
        _assert_soap(
            _last(api), service="PurchaseOrder_v3", tenant_id=api.tenant_id, company=api.company,
            soap_operation="List", inner_request_tag="ListRequest",
            must_contain=(
                "<attributeName>PurchaseOrder_v3.status</attributeName>",
                "<instanceValue>open</instanceValue>",
            ),
        )

    _run(go())


def test_po_show(api):
    async def go():
        po_id = _records(
            json.loads(await api.list_records("PurchaseOrder_v3", fields="orderIdentifier", limit=1)),
            "PurchaseOrder_v3",
        )[0]["orderIdentifier"]
        api.posts.clear()
        raw = await api.show_record(
            "PurchaseOrder_v3", {"orderIdentifier": po_id},
            fields="orderIdentifier,status,buyFromSupplierCode",
        )
        assert json.loads(raw)["ShowResponse"]["DataArea"]["PurchaseOrder_v3"]["orderIdentifier"] == po_id
        _assert_soap(
            _last(api), service="PurchaseOrder_v3", tenant_id=api.tenant_id, company=api.company,
            soap_operation="Show", inner_request_tag="ShowRequest",
            must_contain=(f"<orderIdentifier>{po_id}</orderIdentifier>", "<bo:Show>"),
        )

    _run(go())


# --- Warehouse_v2 ---


def test_warehouse_list(api):
    async def go():
        api.posts.clear()
        raw = await api.list_records(
            "Warehouse_v2", fields="warehouse,warehouseDescription", limit=3,
        )
        assert _records(json.loads(raw), "Warehouse_v2")
        _assert_soap(
            _last(api), service="Warehouse_v2", tenant_id=api.tenant_id, company=api.company,
            soap_operation="List", inner_request_tag="ListRequest",
            must_contain=("<selectionAttribute>Warehouse_v2.warehouse</selectionAttribute>",),
        )

    _run(go())


def test_warehouse_show(api):
    async def go():
        code = _records(
            json.loads(await api.list_records("Warehouse_v2", fields="warehouse", limit=1)),
            "Warehouse_v2",
        )[0]["warehouse"]
        api.posts.clear()
        raw = await api.show_record(
            "Warehouse_v2", {"warehouse": code}, fields="warehouse,warehouseDescription",
        )
        assert json.loads(raw)["ShowResponse"]["DataArea"]["Warehouse_v2"]["warehouse"] == code
        _assert_soap(
            _last(api), service="Warehouse_v2", tenant_id=api.tenant_id, company=api.company,
            soap_operation="Show", inner_request_tag="ShowRequest",
            must_contain=(f"<warehouse>{code}</warehouse>", "<bo:Show>"),
        )

    _run(go())
