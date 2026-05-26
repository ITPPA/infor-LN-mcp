"""
Infor LN c4ws SOAP Client

Async HTTP client for Infor LN Web Services via ION API Gateway.
Handles OAuth authentication, SOAP POST requests, XML parsing, and retries.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import httpx
from defusedxml import ElementTree as DefusedET

from infor_mcp.auth import IONAuthManager
from infor_mcp.soap_builder import build_list_envelope, build_show_envelope

logger = logging.getLogger("infor_mcp.client")

MAX_RETRIES = 3
RETRY_STATUSES = {429, 500, 502, 503, 504}

LN_SERVICES_PATH = "/LN/c4ws/services"


class LNSoapClient:
    """
    Async SOAP client for Infor LN c4ws services through ION API Gateway.

    Usage:
        auth = IONAuthManager("config/.ionapi")
        client = LNSoapClient(auth, company=100, tenant_id="YOUR_TENANT_PRD")
        result = await client.list_records("PurchaseOrder_v3", filters={"buyFromSupplierCode": "POWERSUR"})
    """

    def __init__(
        self,
        auth: IONAuthManager,
        company: int | str = 100,
        tenant_id: Optional[str] = None,
        language: Optional[str] = None,
        timeout: float = 60.0,
    ):
        if not tenant_id:
            raise ValueError(
                "INFOR_ION_TENANT_ID is required (ION API tenant for URL path). "
                "Set it in .env or the MCP server environment."
            )
        self.auth = auth
        self.company = company
        self.tenant_id = tenant_id
        self.language = language
        self.timeout = timeout
        self._http: Optional[httpx.AsyncClient] = None

    async def _get_http(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout, connect=15.0),
                follow_redirects=True,
            )
        return self._http

    def _build_url(self, service: str) -> str:
        """Build full URL: {base}/{tenant}/LN/c4ws/services/{service}"""
        base = self.auth.base_url.rstrip("/")
        tenant = self.tenant_id
        service = service.strip("/")
        return f"{base}/{tenant}{LN_SERVICES_PATH}/{service}"

    async def call_operation(
        self,
        service: str,
        envelope_xml: str,
    ) -> str:
        """
        POST a SOAP envelope to an LN service.

        Returns:
            JSON string formatted for LLM consumption.
        """
        url = self._build_url(service)
        token = await self.auth.get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "text/xml; charset=utf-8",
            "Accept": "text/xml, application/xml, */*",
        }

        last_error: Optional[Exception] = None
        for attempt in range(MAX_RETRIES):
            try:
                http = await self._get_http()
                response = await http.post(url, content=envelope_xml, headers=headers)

                if response.status_code == 401:
                    logger.info("Token expired mid-request, re-authenticating")
                    token = await self.auth.get_token()
                    headers["Authorization"] = f"Bearer {token}"
                    continue

                if response.status_code == 429:
                    import asyncio
                    retry_after = int(response.headers.get("Retry-After", 2 ** attempt))
                    logger.warning(f"Rate limited, waiting {retry_after}s (attempt {attempt + 1})")
                    await asyncio.sleep(retry_after)
                    continue

                if response.status_code in RETRY_STATUSES:
                    import asyncio
                    logger.warning(f"Transient error {response.status_code} (attempt {attempt + 1})")
                    await asyncio.sleep(2 ** attempt)
                    continue

                if response.status_code >= 400:
                    return self._format_http_error(response)

                return self._format_response(response.text)

            except httpx.TimeoutException as e:
                last_error = e
                import asyncio
                logger.warning(f"Request timeout (attempt {attempt + 1}): {e}")
                await asyncio.sleep(2 ** attempt)
            except httpx.ConnectError as e:
                raise LNSoapError(
                    f"Cannot connect to ION API Gateway at {self.auth.base_url}. "
                    "Verify the base URL in your .ionapi file and network connectivity."
                ) from e

        raise LNSoapError(
            f"SOAP request failed after {MAX_RETRIES} attempts. Last error: {last_error}"
        )

    async def list_records(
        self,
        service: str,
        fields: str = "*",
        filters: Optional[dict[str, str]] = None,
        limit: int = 20,
        filter_operator: str = "eq",
    ) -> str:
        """Execute a List (or equivalent) operation on an LN service."""
        envelope, svc, operation = build_list_envelope(
            service_name=service,
            fields=fields,
            filters=filters,
            limit=limit,
            filter_operator=filter_operator,
            company=self.company,
            language_id=self.language,
        )
        logger.info(f"LN List: {svc}/{operation} filters={filters} limit={limit}")
        return await self.call_operation(svc, envelope)

    async def show_record(
        self,
        service: str,
        key_values: dict[str, str],
        fields: str = "*",
    ) -> str:
        """Execute a Show (or equivalent) operation on an LN service."""
        envelope, svc, operation = build_show_envelope(
            service_name=service,
            key_values=key_values,
            fields=fields,
            company=self.company,
            language_id=self.language,
        )
        logger.info(f"LN Show: {svc}/{operation} keys={key_values}")
        return await self.call_operation(svc, envelope)

    def _format_response(self, xml_text: str) -> str:
        """Parse SOAP XML response into clean JSON for the LLM."""
        try:
            data = self._xml_to_dict(xml_text)
            return json.dumps(data, indent=2, default=str, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"XML parse failed, returning raw text: {e}")
            return xml_text

    def _xml_to_dict(self, xml_text: str) -> Any:
        """Convert XML to nested dict, stripping SOAP envelope noise."""
        root = DefusedET.fromstring(xml_text)
        body = self._find_element(root, "{http://schemas.xmlsoap.org/soap/envelope/}Body")
        if body is not None and len(body):
            return self._element_to_dict(body[0])
        return self._element_to_dict(root)

    def _find_element(self, node, tag: str):
        for child in node:
            if child.tag == tag:
                return child
        return None

    def _local_name(self, tag: str) -> str:
        if "}" in tag:
            return tag.rsplit("}", 1)[1]
        return tag

    def _element_to_dict(self, element) -> Any:
        """Recursively convert an XML element to dict/list/scalar."""
        children = list(element)
        text = (element.text or "").strip()

        if not children:
            return text if text else None

        result: dict[str, Any] = {}
        if text:
            result["_text"] = text

        for child in children:
            key = self._local_name(child.tag)
            value = self._element_to_dict(child)

            if key in result:
                existing = result[key]
                if not isinstance(existing, list):
                    result[key] = [existing]
                result[key].append(value)
            else:
                result[key] = value

        return result

    def _format_http_error(self, response: httpx.Response) -> str:
        status = response.status_code
        body = response.text[:2000]

        hints = {
            400: "Bad request — check service name, field names, filter syntax, or key values.",
            401: "Authentication failed — verify .ionapi credentials and service account permissions.",
            403: "Access denied — the service account lacks permission for this LN service.",
            404: "Not found — verify the service name. Use list_ln_services to see available services.",
            500: "Internal server error — the SOAP request may be malformed or LN is unavailable.",
        }

        parsed_detail = body
        try:
            parsed = self._xml_to_dict(body)
            parsed_detail = json.dumps(parsed, indent=2, default=str, ensure_ascii=False)
        except Exception:
            pass

        return json.dumps({
            "error": True,
            "status": status,
            "hint": hints.get(status, "Unexpected error from ION API Gateway."),
            "detail": parsed_detail,
        }, indent=2, ensure_ascii=False)

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()


class LNSoapError(Exception):
    """Raised when an LN SOAP call fails after retries."""

    pass


# Backward-compatible alias during transition
IONAPIError = LNSoapError
