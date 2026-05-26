"""
MCP Resources for Infor LN

Resources expose read-only reference data for LLM context when constructing
LN SOAP queries.
"""

import json
import logging

from infor_mcp.services_registry import LN_SERVICES

logger = logging.getLogger("infor_mcp.resources")


def _build_ln_services_catalog() -> dict:
    """Build a categorized catalog from the services registry."""
    categories = {
        "Purchasing": {},
        "Sales": {},
        "Master Data": {},
        "Inventory": {},
        "HR": {},
    }

    mapping = {
        "PurchaseOrder_v3": "Purchasing",
        "PurchaseInvoice": "Purchasing",
        "SalesOrder": "Sales",
        "BusinessPartner_v3": "Master Data",
        "Item_v3": "Master Data",
        "Customer360": "Master Data",
        "Warehouse_v2": "Inventory",
        "WarehouseItemInventory": "Inventory",
        "Employee_v2": "HR",
    }

    for name, svc in LN_SERVICES.items():
        category = mapping.get(name, "Master Data")
        categories[category][name] = {
            "description": svc.description,
            "entity": svc.entity,
            "supports_list": svc.supports_list,
            "list_operation": svc.list_operation,
            "show_operation": svc.show_operation,
            "key_fields": list(svc.key_fields),
            "common_fields": list(svc.common_fields),
        }

    return {k: v for k, v in categories.items() if v}


FILTER_PATTERNS = {
    "Single field equals": {
        "filters": '{"buyFromSupplierCode": "POWERSUR"}',
        "filter_operator": "eq",
    },
    "Prefix / pattern match": {
        "filters": '{"itemCode": "ABC%"}',
        "filter_operator": "like",
    },
    "Multiple fields (AND)": {
        "filters": '{"status": "Open", "buyFromSupplierCode": "POWERSUR"}',
        "filter_operator": "eq",
    },
    "Note": (
        "LN filters use SOAP ComparisonExpression inside the List request. "
        "Pass filters as a JSON object to list_ln_records. "
        "Field names can be short (buyFromSupplierCode) or fully qualified "
        "(PurchaseOrder_v3.buyFromSupplierCode). "
        "Operators: eq, ne, lt, le, gt, ge, like."
    ),
}


API_PATTERNS = {
    "Endpoint": "POST {base_url}/{INFOR_ION_TENANT_ID}/LN/c4ws/services/{ServiceName}",
    "Authentication": "OAuth Bearer token (.ionapi) + SOAP Activation header with INFOR_LN_COMPANY",
    "Configuration": {
        "INFOR_ION_TENANT_ID": "ION API tenant (URL path), e.g. XXXXXXXXXXXXX_PRD",
        "INFOR_LN_COMPANY": "LN company number (SOAP Activation header), e.g. 100",
    },
    "List records": "Operation List (or ListPurchaseInvoices) with Selection, Filter, maxNumberOfObjects",
    "Show record": "Operation Show (or ShowPurchaseInvoice) with DataArea key fields",
    "Example List": {
        "tool": "list_ln_records",
        "service": "PurchaseOrder_v3",
        "fields": "orderIdentifier,buyFromSupplierCode,status,Line.*",
        "filters": '{"buyFromSupplierCode": "POWERSUR"}',
        "limit": 20,
    },
    "Example Show": {
        "tool": "show_ln_record",
        "service": "Item_v3",
        "key_values": "itemCode=ITEM001",
    },
}


def register_resources(mcp):
    """Register MCP resources for LN reference data."""

    @mcp.resource("infor://reference/ln-services")
    async def get_ln_services_reference() -> str:
        """
        Reference guide to Infor LN c4ws SOAP services organized by functional area.
        Use this to identify the correct service name for queries.
        """
        return json.dumps(_build_ln_services_catalog(), indent=2, ensure_ascii=False)

    @mcp.resource("infor://reference/filter-patterns")
    async def get_filter_patterns() -> str:
        """
        Reference guide to LN SOAP filter syntax for list_ln_records.
        """
        return json.dumps(FILTER_PATTERNS, indent=2, ensure_ascii=False)

    @mcp.resource("infor://reference/api-patterns")
    async def get_api_patterns() -> str:
        """
        Reference guide to LN c4ws SOAP API conventions used by the query tools.
        """
        return json.dumps(API_PATTERNS, indent=2, ensure_ascii=False)

    logger.info("Registered MCP resources")
