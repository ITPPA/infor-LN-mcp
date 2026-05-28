"""Tests for LNSoapClient."""

import asyncio
import json

import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from infor_mcp.auth import IONAuthManager
from infor_mcp.client import LNSoapClient


SAMPLE_TENANT_ID = "TENANT_PRD"
SAMPLE_SOAP_RESPONSE = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">
  <soapenv:Body>
    <ListResponse>
      <DataArea>
        <PurchaseOrder_v3>
          <orderIdentifier>PO001</orderIdentifier>
          <buyFromSupplierCode>POWERSUR</buyFromSupplierCode>
        </PurchaseOrder_v3>
      </DataArea>
    </ListResponse>
  </soapenv:Body>
</soapenv:Envelope>
"""


def _make_auth():
    auth = MagicMock(spec=IONAuthManager)
    auth.base_url = "https://mingle-ionapi.eu1.inforcloudsuite.com"
    auth.tenant_id = "SHOULD_NOT_BE_USED"
    auth.get_token = AsyncMock(return_value="test-token")
    return auth


def _make_client(tenant_id: str = SAMPLE_TENANT_ID):
    return LNSoapClient(_make_auth(), company=100, tenant_id=tenant_id)


def test_tenant_id_required():
    auth = _make_auth()
    with pytest.raises(ValueError, match="INFOR_ION_TENANT_ID"):
        LNSoapClient(auth, company=100, tenant_id=None)


def test_call_operation_posts_soap():
    client = _make_client()
    mock_response = httpx.Response(
        200,
        text=SAMPLE_SOAP_RESPONSE,
        request=httpx.Request("POST", "http://test"),
    )

    async def run():
        with patch.object(client, "_get_http") as mock_get_http:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_get_http.return_value = mock_http

            envelope = (
                '<?xml version="1.0"?><soapenv:Envelope '
                'xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">'
                "<soapenv:Body><bo:List/></soapenv:Body></soapenv:Envelope>"
            )
            result = await client.call_operation("PurchaseOrder_v3", envelope)

            mock_http.post.assert_called_once()
            call_kwargs = mock_http.post.call_args
            assert call_kwargs[0][0] == (
                f"https://mingle-ionapi.eu1.inforcloudsuite.com/{SAMPLE_TENANT_ID}"
                "/LN/c4ws/services/PurchaseOrder_v3"
            )
            assert call_kwargs[1]["headers"]["Authorization"] == "Bearer test-token"
            assert call_kwargs[1]["headers"]["Content-Type"] == "text/xml; charset=utf-8"

            parsed = json.loads(result)
            assert "ListResponse" in parsed or "DataArea" in str(parsed)

    asyncio.run(run())


def test_tenant_id_from_env_not_ionapi():
    auth = _make_auth()
    env_tenant = "ENV_TENANT_PRD"

    client = LNSoapClient(auth, company=100, tenant_id=env_tenant)
    url = client._build_url("PurchaseOrder_v3")

    assert env_tenant in url
    assert auth.tenant_id not in url


def test_list_records_builds_envelope_with_company():
    client = _make_client()
    mock_response = httpx.Response(
        200,
        text=SAMPLE_SOAP_RESPONSE,
        request=httpx.Request("POST", "http://test"),
    )

    async def run():
        with patch.object(client, "_get_http") as mock_get_http:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_get_http.return_value = mock_http

            await client.list_records(
                "PurchaseOrder_v3",
                filters={"buyFromSupplierCode": "POWERSUR"},
                limit=20,
            )

            posted_xml = mock_http.post.call_args[1]["content"]
            if isinstance(posted_xml, bytes):
                posted_xml = posted_xml.decode("utf-8")
            assert "<company>100</company>" in posted_xml
            assert "POWERSUR" in posted_xml
            assert "<maxNumberOfObjects>20</maxNumberOfObjects>" in posted_xml

    asyncio.run(run())


SOAP_FAULT_NOT_FOUND = """<?xml version="1.0" ?>
<S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/">
  <S:Body>
    <S:Fault>
      <faultcode>S:Server</faultcode>
      <faultstring>Object not found.</faultstring>
      <detail>
        <Result xmlns="http://www.infor.com/businessinterface/Item_v3">
          <messageCode>tlbctsb0026</messageCode>
          <messageType>Error</messageType>
          <messageText>Object not found.</messageText>
          <messageSource>Public Layer</messageSource>
        </Result>
      </detail>
    </S:Fault>
  </S:Body>
</S:Envelope>
"""


def test_soap_fault_500_returns_json_without_retry():
    client = _make_client()
    mock_response = httpx.Response(
        500,
        text=SOAP_FAULT_NOT_FOUND,
        request=httpx.Request("POST", "http://test"),
    )

    async def run():
        with patch.object(client, "_get_http") as mock_get_http:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_get_http.return_value = mock_http

            result = await client.call_operation("Item_v3", "<xml/>")
            parsed = json.loads(result)

            assert mock_http.post.call_count == 1
            assert parsed["error"] is True
            assert parsed["status"] == 500
            assert parsed["message"] == "Object not found."
            assert parsed["messageCode"] == "tlbctsb0026"
            assert "not found" in parsed["hint"].lower()

    asyncio.run(run())


def test_item_v3_show_uses_list_only():
    """Item_v3 show_record must not POST Show SOAP — only List."""
    client = _make_client()
    list_ok = httpx.Response(
        200,
        text="""<?xml version="1.0"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">
  <soapenv:Body>
    <ListResponse>
      <DataArea>
        <Item_v3>
          <itemCode>XALK01</itemCode>
          <description>Test item</description>
        </Item_v3>
      </DataArea>
    </ListResponse>
  </soapenv:Body>
</soapenv:Envelope>""",
        request=httpx.Request("POST", "http://test"),
    )

    async def run():
        with patch.object(client, "_get_http") as mock_get_http:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=list_ok)
            mock_get_http.return_value = mock_http

            result = await client.show_record(
                "Item_v3", {"itemCode": "XALK01"}, fields="itemCode,description"
            )
            parsed = json.loads(result)
            assert parsed["ShowResponse"]["DataArea"]["Item_v3"]["itemCode"] == "XALK01"
            assert "_show_fallback" not in parsed
            assert mock_http.post.call_count == 1
            posted = mock_http.post.call_args[1]["content"]
            if isinstance(posted, bytes):
                posted = posted.decode()
            assert "<bo:List>" in posted
            assert "<bo:Show>" not in posted
            assert "%XALK01%" in posted

    asyncio.run(run())


def test_http_error_returns_json():
    client = _make_client()
    mock_response = httpx.Response(
        403,
        text="Forbidden",
        request=httpx.Request("POST", "http://test"),
    )

    async def run():
        with patch.object(client, "_get_http") as mock_get_http:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_get_http.return_value = mock_http

            result = await client.call_operation("PurchaseOrder_v3", "<xml/>")
            parsed = json.loads(result)
            assert parsed["error"] is True
            assert parsed["status"] == 403

    asyncio.run(run())
