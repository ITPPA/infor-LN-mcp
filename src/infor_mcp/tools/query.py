"""
Phase 1 Read-Only Query Tools for Infor LN MCP Server

These tools provide natural language access to Infor LN c4ws SOAP services
through the ION API Gateway.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from infor_mcp.client import LNSoapClient
from infor_mcp.services_registry import FIELD_ALIASES, LN_SERVICES, get_service

logger = logging.getLogger("infor_mcp.tools.query")


def _parse_key_values(key_values: str) -> dict[str, str]:
    """Parse 'Field1=Value1&Field2=Value2' into a dict."""
    result: dict[str, str] = {}
    if not key_values:
        return result
    for pair in key_values.split("&"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            result[k.strip()] = v.strip()
    return result


def _parse_filters(filters_json: str) -> dict[str, str]:
    """Parse filters from JSON string or empty."""
    if not filters_json or not filters_json.strip():
        return {}
    try:
        parsed = json.loads(filters_json)
        if not isinstance(parsed, dict):
            raise ValueError("filters must be a JSON object")
        return {str(k): str(v) for k, v in parsed.items()}
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid filters JSON: {e}") from e


def register_query_tools(mcp, client: LNSoapClient):
    """Register all Phase 1 read-only LN query tools with the MCP server."""

    @mcp.tool()
    async def list_ln_services(search_term: str = "") -> str:
        """
        List available Infor LN c4ws SOAP services exposed by this MCP server.

        Use this to discover which services you can query before calling
        list_ln_records or show_ln_record.

        Args:
            search_term: Optional filter (e.g. "Purchase", "Item", "Warehouse").
                Leave empty to list all services.

        Returns:
            JSON catalog of LN services with descriptions and capabilities.
        """
        term = search_term.lower().strip()
        catalog = []
        for name, svc in sorted(LN_SERVICES.items()):
            if term and term not in name.lower() and term not in svc.description.lower():
                continue
            catalog.append({
                "service": name,
                "description": svc.description,
                "entity": svc.entity,
                "supports_list": svc.supports_list,
                "list_operation": svc.list_operation,
                "show_operation": svc.show_operation,
                "key_fields": list(svc.key_fields),
                "common_fields": list(svc.common_fields),
            })
        return json.dumps({"services": catalog, "count": len(catalog)}, indent=2)

    @mcp.tool()
    async def get_ln_service_info(service: str) -> str:
        """
        Get detailed metadata for an LN service — key fields, filterable fields,
        and usage examples.

        Use this before querying to understand field names and required keys.

        Args:
            service: LN service name (e.g. "PurchaseOrder_v3", "BusinessPartner_v3").
                Use list_ln_services to discover available services.

        Returns:
            JSON with service metadata, key fields, filterable fields, and examples.
        """
        try:
            svc = get_service(service)
        except KeyError as e:
            return json.dumps({"error": True, "hint": str(e)}, indent=2)

        examples = {}
        if svc.supports_list and svc.list_operation:
            examples["list"] = {
                "tool": "list_ln_records",
                "service": svc.name,
                "fields": ", ".join(svc.common_fields[:4]),
                "filters": {svc.filterable_fields[0]: "VALUE"} if svc.filterable_fields else {},
            }
        if svc.key_fields:
            examples["show"] = {
                "tool": "show_ln_record",
                "service": svc.name,
                "key_values": "&".join(f"{k}=VALUE" for k in svc.key_fields),
            }

        return json.dumps({
            "service": svc.name,
            "description": svc.description,
            "namespace": svc.namespace,
            "entity": svc.entity,
            "supports_list": svc.supports_list,
            "list_operation": svc.list_operation,
            "show_operation": svc.show_operation,
            "key_fields": list(svc.key_fields),
            "common_fields": list(svc.common_fields),
            "filterable_fields": list(svc.filterable_fields),
            "filter_operators": ["eq", "ne", "lt", "le", "gt", "ge", "like"],
            "field_aliases": dict(FIELD_ALIASES.get(svc.name, {})),
            "examples": examples,
        }, indent=2, ensure_ascii=False)

    @mcp.tool()
    async def list_ln_records(
        service: str,
        fields: str = "*",
        filters: str = "",
        limit: int = 20,
        filter_operator: str = "eq",
    ) -> str:
        """
        List records from an Infor LN c4ws service using a List operation.

        Returns matching records with the specified fields. Use this to search
        and browse LN data (purchase orders, items, business partners, etc.).

        Args:
            service: LN service name. Examples:
                - PurchaseOrder_v3 — purchase orders
                - BusinessPartner_v3 — suppliers/customers
                - Item_v3 — items/articles
                - SalesOrder — sales orders
                - PurchaseInvoice — supplier invoices
                - Warehouse_v2 — warehouses
                - Employee_v2 — employees
                Use list_ln_services to see all available services.
            fields: Comma-separated field names, or "*" for all fields.
                Examples: "orderIdentifier,buyFromSupplierCode,status"
                or "PurchaseOrder_v3.Line.*" for line details (not purchaseOrderLine).
            filters: JSON object of field->value filters.
                Example: '{"buyFromSupplierCode": "POWERSUR"}'
                Field names can be short (buyFromSupplierCode) or fully qualified
                (PurchaseOrder_v3.buyFromSupplierCode).
            limit: Maximum records to return (1-100). Default 20.
            filter_operator: Comparison operator — eq, ne, lt, le, gt, ge, like.
                Default eq.

        Returns:
            JSON with matching records from the LN service response.
        """
        limit = max(1, min(limit, 100))

        try:
            svc = get_service(service)
            if not svc.supports_list or not svc.list_operation:
                return json.dumps({
                    "error": True,
                    "hint": (
                        f"Service '{service}' does not support List operations. "
                        f"Use show_ln_record with key_values instead."
                    ),
                }, indent=2)

            filter_dict = _parse_filters(filters)
            return await client.list_records(
                service=service,
                fields=fields,
                filters=filter_dict,
                limit=limit,
                filter_operator=filter_operator,
            )
        except (KeyError, ValueError) as e:
            return json.dumps({"error": True, "hint": str(e)}, indent=2)

    @mcp.tool()
    async def show_ln_record(
        service: str,
        key_values: str,
        fields: str = "*",
    ) -> str:
        """
        Show a specific record from an Infor LN service by its key field(s).

        Use this when you know the exact identifier of a record.

        Args:
            service: LN service name (e.g. "PurchaseOrder_v3", "Item_v3").
            key_values: Key field values as "Field1=Value1&Field2=Value2".
                Examples:
                    PurchaseOrder_v3: "orderIdentifier=PO123456"
                    BusinessPartner_v3: "businessPartnerCode=BP001"
                    Item_v3: "itemCode=ITEM001"
                    SalesOrder: "salesOrder=SO123456"
                    PurchaseInvoice: "invoiceId=INV001"
                    WarehouseItemInventory: "Warehouse=WH01&Item=ITEM001"
                    Customer360: "CustomerID=CUST001"
                Use get_ln_service_info to discover required key fields.
            fields: Comma-separated fields to return, or "*" for all.
                Item_v3 uses List-based key lookup (LN Show SOAP is not reliable).

        Returns:
            JSON with the full record details from the LN service.
        """
        try:
            get_service(service)
            keys = _parse_key_values(key_values)
            if not keys:
                return json.dumps({
                    "error": True,
                    "hint": (
                        "key_values is required. Format: 'Field1=Value1&Field2=Value2'. "
                        "Use get_ln_service_info to see required key fields."
                    ),
                }, indent=2)
            return await client.show_record(
                service=service,
                key_values=keys,
                fields=fields,
            )
        except (KeyError, ValueError) as e:
            return json.dumps({"error": True, "hint": str(e)}, indent=2)

    logger.info("Registered Phase 1 LN query tools")
