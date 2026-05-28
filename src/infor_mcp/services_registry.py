"""
Registry of Infor LN c4ws SOAP services available via ION API Gateway.

Derived from DOCS_API/ WSDL files.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

ShowStrategy = Literal["soap", "list_like_keys"]


WRITE_OPERATIONS = frozenset({
    "Change",
    "Create",
    "CreateAndApprove",
    "CreateRef",
    "Delete",
    "DeleteRef",
    "Approve",
    "Confirm",
    "Cancel",
    "Reprice",
    "PublishChanges",
    "PublishList",
    "UnpublishChanges",
    "SubscribeEvent",
    "UnSubscribeEvent",
    "SubscribeList",
    "OnEvent",
    "CheckStructure",
})


@dataclass(frozen=True)
class LNServiceInfo:
    """Metadata for one LN c4ws business interface service."""

    name: str
    namespace: str
    entity: str
    description: str
    list_operation: Optional[str] = None
    list_request_element: Optional[str] = None
    show_operation: str = "Show"
    show_request_element: str = "ShowRequest"
    key_fields: tuple[str, ...] = ()
    common_fields: tuple[str, ...] = ()
    filterable_fields: tuple[str, ...] = ()
    supports_list: bool = True
    # Item_v3: LN c4ws Show SOAP returns "Object not found" for valid items;
    # List with like %key% is the supported lookup path on this interface.
    show_strategy: ShowStrategy = "soap"
    # When True, eq filters on key_fields are sent as like %value% (LN tcitem quirk).
    list_key_eq_as_like: bool = False


# LLM / API guesses → LN selectionAttribute names (WSDL / Public Layer).
FIELD_ALIASES: dict[str, dict[str, str]] = {
    "PurchaseOrder_v3": {
        "purchaseOrderLine": "Line",
        "PurchaseOrderLine": "Line",
        "purchaseOrderLines": "Line",
        "PurchaseOrderLines": "Line",
        "lines": "Line",
        "line": "Line",
    },
}


LN_SERVICES: dict[str, LNServiceInfo] = {
    "PurchaseOrder_v3": LNServiceInfo(
        name="PurchaseOrder_v3",
        namespace="http://www.infor.com/businessinterface/PurchaseOrder_v3",
        entity="PurchaseOrder_v3",
        description="Commandes d'achat (headers et lignes)",
        list_operation="List",
        list_request_element="ListRequest",
        key_fields=("orderIdentifier",),
        common_fields=(
            "orderIdentifier",
            "buyFromSupplierCode",
            "status",
            "orderDatetime",
            "Line.*",
        ),
        filterable_fields=(
            "orderIdentifier",
            "buyFromSupplierCode",
            "status",
            "purchaseOfficeCode",
            "orderTypeCode",
        ),
    ),
    "BusinessPartner_v3": LNServiceInfo(
        name="BusinessPartner_v3",
        namespace="http://www.infor.com/businessinterface/BusinessPartner_v3",
        entity="BusinessPartner_v3",
        description="Partenaires commerciaux (clients, fournisseurs)",
        list_operation="List",
        list_request_element="ListRequest",
        key_fields=("businessPartnerCode",),
        common_fields=(
            "businessPartnerCode",
            "name",
            "status",
            "currency",
            "addressName",
        ),
        filterable_fields=(
            "businessPartnerCode",
            "status",
            "businessPartnerRole",
            "addressCountry",
        ),
    ),
    "Item_v3": LNServiceInfo(
        name="Item_v3",
        namespace="http://www.infor.com/businessinterface/Item_v3",
        entity="Item_v3",
        description="Articles / items",
        list_operation="List",
        list_request_element="ListRequest",
        key_fields=("itemCode",),
        common_fields=("itemCode", "description", "itemGroup", "itemType", "baseUOM"),
        filterable_fields=("itemCode", "itemGroup", "itemType", "generalSearchKey1"),
        show_strategy="list_like_keys",
        list_key_eq_as_like=True,
    ),
    "SalesOrder": LNServiceInfo(
        name="SalesOrder",
        namespace="http://www.infor.com/businessinterface/SalesOrder",
        entity="SalesOrder",
        description="Commandes de vente",
        list_operation="List",
        list_request_element="ListRequest",
        key_fields=("salesOrder",),
        common_fields=(
            "salesOrder",
            "soldToBusinessPartner",
            "orderCurrency",
            "salesOrderHeaderDate",
            "SalesOrderLine.*",
        ),
        filterable_fields=("salesOrder", "soldToBusinessPartner", "shipToBusinessPartner"),
    ),
    "PurchaseInvoice": LNServiceInfo(
        name="PurchaseInvoice",
        namespace="http://www.infor.com/businessinterface/PurchaseInvoice",
        entity="PurchaseInvoice",
        description="Factures fournisseurs",
        list_operation="ListPurchaseInvoices",
        list_request_element="ListPurchaseInvoicesRequest",
        show_operation="ShowPurchaseInvoice",
        show_request_element="ShowPurchaseInvoiceRequest",
        key_fields=("invoiceId",),
        common_fields=("invoiceId", "sourceCompany", "postingDate", "PurchaseInvoiceLine.*"),
        filterable_fields=("invoiceId", "sourceCompany", "postingDate"),
    ),
    "Warehouse_v2": LNServiceInfo(
        name="Warehouse_v2",
        namespace="http://www.infor.com/businessinterface/Warehouse_v2",
        entity="Warehouse_v2",
        description="Entrepôts",
        list_operation="List",
        list_request_element="ListRequest",
        key_fields=("warehouse",),
        common_fields=("warehouse", "warehouseDescription"),
        filterable_fields=("warehouse",),
    ),
    "WarehouseItemInventory": LNServiceInfo(
        name="WarehouseItemInventory",
        namespace="http://www.infor.com/businessinterface/WarehouseItemInventory",
        entity="WarehouseItemInventory",
        description="Stock article par entrepôt",
        supports_list=False,
        key_fields=("Warehouse", "Item"),
        common_fields=("Warehouse", "Item", "Inventory.*"),
        filterable_fields=("Warehouse", "Item", "WarehouseItemInventory.Warehouse"),
    ),
    "Employee_v2": LNServiceInfo(
        name="Employee_v2",
        namespace="http://www.infor.com/businessinterface/Employee_v2",
        entity="Employee_v2",
        description="Employés",
        list_operation="List",
        list_request_element="ListRequest",
        key_fields=("employeeCode",),
        common_fields=("employeeCode", "name", "department"),
        filterable_fields=("employeeCode",),
    ),
    "Customer360": LNServiceInfo(
        name="Customer360",
        namespace="http://www.infor.com/businessinterface/Customer360",
        entity="Customer360",
        description="Vue client 360 (détails enrichis)",
        supports_list=False,
        key_fields=("CustomerID",),
        common_fields=("CustomerID", "CustomerName", "AddressLine", "Contact.*"),
        filterable_fields=("CustomerID",),
    ),
}


def get_service(name: str) -> LNServiceInfo:
    """Return service metadata or raise KeyError."""
    if name not in LN_SERVICES:
        available = ", ".join(sorted(LN_SERVICES))
        raise KeyError(f"Unknown LN service '{name}'. Available: {available}")
    return LN_SERVICES[name]


def qualify_field(service: LNServiceInfo, field_name: str) -> str:
    """Ensure a field name is fully qualified with the entity prefix."""
    field_name = normalize_field_alias(service, field_name.strip())
    if not field_name or field_name == "*":
        return "*"
    if field_name.startswith(f"{service.entity}."):
        return field_name
    return f"{service.entity}.{field_name}"


def normalize_field_alias(service: LNServiceInfo, field_name: str) -> str:
    """Map common aliases to LN-valid selectionAttribute short names."""
    if not field_name or field_name in ("*", "_all", "all"):
        return field_name

    aliases = FIELD_ALIASES.get(service.name, {})
    if not aliases:
        return field_name

    entity_prefix = f"{service.entity}."
    raw = field_name
    if raw.startswith(entity_prefix):
        raw = raw[len(entity_prefix):]

    wildcard = raw.endswith(".*")
    base = raw[:-2] if wildcard else raw
    mapped = aliases.get(base, base)
    result = f"{mapped}.*" if wildcard else mapped
    if field_name.startswith(entity_prefix):
        return f"{entity_prefix}{result}"
    return result


def resolve_selection(service: LNServiceInfo, fields: str) -> list[str]:
    """Convert a comma-separated field list into selectionAttribute values."""
    if not fields or fields.strip() in ("*", "_all", "all"):
        return [f"{service.entity}.*"]

    selection = []
    for raw in fields.split(","):
        name = raw.strip()
        if name:
            selection.append(qualify_field(service, name))
    return selection or [f"{service.entity}.*"]


def normalize_list_key_filter(
    service: LNServiceInfo,
    field_name: str,
    value: str,
    filter_operator: str,
) -> tuple[str, str]:
    """
    Apply service-specific filter rules for LN key lookups.

    Item_v3 itemCode ignores eq; only like %value% matches (tcitem / Public Layer).
    """
    short_name = field_name.split(".")[-1]
    if (
        service.list_key_eq_as_like
        and filter_operator == "eq"
        and short_name in service.key_fields
        and "%" not in value
    ):
        return "like", f"%{value.strip()}%"
    return filter_operator, value
