"""
Build SOAP request XML for Infor LN c4ws Web Services.

Follows the pattern validated in DOCS_API/POST_PurchaseOrder_v3.xml.
"""

from __future__ import annotations

import html
from typing import Optional

from infor_mcp.services_registry import LNServiceInfo, qualify_field, get_service

SOAP_ENV = "http://schemas.xmlsoap.org/soap/envelope/"


def escape_xml(value: str) -> str:
    """Escape text for XML element content."""
    return html.escape(str(value), quote=False)


def build_comparison_expression(
    attribute_name: str,
    instance_value: str,
    comparison_operator: str = "eq",
) -> str:
    """Build a single ComparisonExpression filter node."""
    return (
        "<ComparisonExpression>"
        f"<comparisonOperator>{escape_xml(comparison_operator)}</comparisonOperator>"
        f"<attributeName>{escape_xml(attribute_name)}</attributeName>"
        f"<instanceValue>{escape_xml(instance_value)}</instanceValue>"
        "</ComparisonExpression>"
    )


def build_filter_and(expressions: list[str]) -> str:
    """Wrap multiple comparison expressions in a logical AND."""
    if not expressions:
        return ""
    if len(expressions) == 1:
        return f"<Filter>{expressions[0]}</Filter>"

    inner = "".join(expressions)
    logical = (
        "<LogicalExpression>"
        "<logicalOperator>and</logicalOperator>"
        f"{inner}"
        "</LogicalExpression>"
    )
    return f"<Filter>{logical}</Filter>"


def parse_simple_filters(
    service: LNServiceInfo,
    filters: dict[str, str],
    filter_operator: str = "eq",
) -> str:
    """Convert a simple dict of field->value into Filter XML."""
    if not filters:
        return ""

    expressions = []
    for field_name, value in filters.items():
        if value is None or str(value).strip() == "":
            continue
        attribute = qualify_field(service, field_name)
        expressions.append(
            build_comparison_expression(attribute, str(value), filter_operator)
        )
    return build_filter_and(expressions)


def build_selection(selection_attributes: list[str]) -> str:
    """Build Selection block from attribute names."""
    if not selection_attributes:
        return ""
    attrs = "".join(
        f"<selectionAttribute>{escape_xml(attr)}</selectionAttribute>"
        for attr in selection_attributes
    )
    return f"<Selection>{attrs}</Selection>"


def build_control_area(
    selection: list[str],
    filter_xml: str = "",
    max_objects: Optional[int] = None,
    language_id: Optional[str] = None,
    iterator_id: Optional[int] = None,
) -> str:
    """Build ControlArea XML for List/Show requests."""
    parts = []
    selection_xml = build_selection(selection)
    if selection_xml:
        parts.append(selection_xml)
    if filter_xml:
        parts.append(filter_xml)
    if max_objects is not None:
        parts.append(f"<maxNumberOfObjects>{int(max_objects)}</maxNumberOfObjects>")
    if language_id:
        parts.append(f"<languageID>{escape_xml(language_id)}</languageID>")
    if iterator_id is not None:
        parts.append(f"<iteratorID>{int(iterator_id)}</iteratorID>")

    return f"<ControlArea>{''.join(parts)}</ControlArea>"


def build_entity_keys(service: LNServiceInfo, key_values: dict[str, str]) -> str:
    """Build entity XML with key field values for Show requests."""
    elements = []
    for field in service.key_fields:
        if field not in key_values:
            raise ValueError(
                f"Missing required key field '{field}' for service {service.name}. "
                f"Required keys: {', '.join(service.key_fields)}"
            )
        elements.append(
            f"<{field}>{escape_xml(key_values[field])}</{field}>"
        )

    # Include optional extra keys not in key_fields list
    for field, value in key_values.items():
        if field not in service.key_fields and value is not None:
            elements.append(f"<{field}>{escape_xml(value)}</{field}>")

    return f"<{service.entity}>{''.join(elements)}</{service.entity}>"


def build_list_request(
    service: LNServiceInfo,
    selection: list[str],
    filters: Optional[dict[str, str]] = None,
    max_objects: int = 20,
    filter_operator: str = "eq",
    language_id: Optional[str] = None,
) -> str:
    """Build inner ListRequest XML body."""
    filter_xml = parse_simple_filters(service, filters or {}, filter_operator)
    control = build_control_area(
        selection=selection,
        filter_xml=filter_xml,
        max_objects=max_objects,
        language_id=language_id,
    )
    request_element = service.list_request_element or "ListRequest"
    return f"<{request_element}>{control}</{request_element}>"


def build_show_request(
    service: LNServiceInfo,
    key_values: dict[str, str],
    selection: Optional[list[str]] = None,
    language_id: Optional[str] = None,
) -> str:
    """Build inner ShowRequest XML body."""
    entity_xml = build_entity_keys(service, key_values)
    control = build_control_area(
        selection=selection or [f"{service.entity}.*"],
        language_id=language_id,
    )
    request_element = service.show_request_element
    return (
        f"<{request_element}>"
        f"{control}"
        f"<DataArea>{entity_xml}</DataArea>"
        f"</{request_element}>"
    )


def build_envelope(
    namespace: str,
    operation: str,
    body_inner_xml: str,
    company: int | str,
) -> str:
    """
    Build a complete SOAP envelope with Activation header.

    Matches DOCS_API/POST_PurchaseOrder_v3.xml structure.
    """
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<soapenv:Envelope xmlns:soapenv="{SOAP_ENV}" xmlns:bo="{namespace}">'
        "<soapenv:Header>"
        "<bo:Activation>"
        f"<company>{escape_xml(company)}</company>"
        "</bo:Activation>"
        "</soapenv:Header>"
        "<soapenv:Body>"
        f"<bo:{operation}>"
        f"{body_inner_xml}"
        f"</bo:{operation}>"
        "</soapenv:Body>"
        "</soapenv:Envelope>"
    )


def build_list_envelope(
    service_name: str,
    fields: str,
    filters: Optional[dict[str, str]] = None,
    limit: int = 20,
    filter_operator: str = "eq",
    company: int | str = 100,
    language_id: Optional[str] = None,
) -> tuple[str, str, str]:
    """
    Build a complete List SOAP envelope.

    Returns:
        (envelope_xml, service_name, operation_name)
    """
    from infor_mcp.services_registry import resolve_selection

    service = get_service(service_name)
    if not service.supports_list or not service.list_operation:
        raise ValueError(f"Service {service_name} does not support List operations")

    selection = resolve_selection(service, fields)
    body = build_list_request(
        service,
        selection=selection,
        filters=filters,
        max_objects=limit,
        filter_operator=filter_operator,
        language_id=language_id,
    )
    envelope = build_envelope(service.namespace, service.list_operation, body, company)
    return envelope, service.name, service.list_operation


def build_show_envelope(
    service_name: str,
    key_values: dict[str, str],
    fields: str = "*",
    company: int | str = 100,
    language_id: Optional[str] = None,
) -> tuple[str, str, str]:
    """
    Build a complete Show SOAP envelope.

    Returns:
        (envelope_xml, service_name, operation_name)
    """
    from infor_mcp.services_registry import resolve_selection

    service = get_service(service_name)
    selection = resolve_selection(service, fields)
    body = build_show_request(
        service,
        key_values=key_values,
        selection=selection,
        language_id=language_id,
    )
    envelope = build_envelope(service.namespace, service.show_operation, body, company)
    return envelope, service.name, service.show_operation
