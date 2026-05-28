"""Tests for SOAP XML builder."""

import pytest

from infor_mcp.soap_builder import (
    build_comparison_expression,
    build_envelope,
    build_filter_and,
    build_list_request,
    build_show_request,
    parse_simple_filters,
)
from infor_mcp.services_registry import get_service


class TestComparisonExpression:
    def test_builds_eq_filter(self):
        xml = build_comparison_expression(
            "PurchaseOrder_v3.buyFromSupplierCode",
            "POWERSUR",
            "eq",
        )
        assert "<comparisonOperator>eq</comparisonOperator>" in xml
        assert "<attributeName>PurchaseOrder_v3.buyFromSupplierCode</attributeName>" in xml
        assert "<instanceValue>POWERSUR</instanceValue>" in xml


class TestFilterAnd:
    def test_single_expression(self):
        expr = build_comparison_expression("PurchaseOrder_v3.status", "Open")
        result = build_filter_and([expr])
        assert result.startswith("<Filter>")
        assert "ComparisonExpression" in result

    def test_multiple_expressions_use_and(self):
        e1 = build_comparison_expression("PurchaseOrder_v3.status", "Open")
        e2 = build_comparison_expression("PurchaseOrder_v3.buyFromSupplierCode", "X")
        result = build_filter_and([e1, e2])
        assert "<logicalOperator>and</logicalOperator>" in result


class TestParseSimpleFilters:
    def test_qualifies_field_names(self):
        service = get_service("PurchaseOrder_v3")
        xml = parse_simple_filters(service, {"buyFromSupplierCode": "POWERSUR"})
        assert "PurchaseOrder_v3.buyFromSupplierCode" in xml
        assert "POWERSUR" in xml


class TestListRequest:
    def test_matches_postman_example_structure(self):
        service = get_service("PurchaseOrder_v3")
        body = build_list_request(
            service,
            selection=[
                "PurchaseOrder_v3.orderIdentifier",
                "PurchaseOrder_v3.buyFromSupplierCode",
                "PurchaseOrder_v3.status",
                "PurchaseOrder_v3.Line.*",
            ],
            filters={"buyFromSupplierCode": "POWERSUR"},
            max_objects=20,
        )
        assert body.startswith("<ListRequest>")
        assert "<maxNumberOfObjects>20</maxNumberOfObjects>" in body
        assert "POWERSUR" in body
        assert "PurchaseOrder_v3.Line.*" in body


class TestShowRequest:
    def test_includes_data_area_keys(self):
        service = get_service("Item_v3")
        body = build_show_request(
            service,
            key_values={"itemCode": "ITEM001"},
            selection=["Item_v3.*"],
        )
        assert "<ShowRequest>" in body
        assert "<itemCode>ITEM001</itemCode>" in body
        assert "<DataArea>" in body


class TestResolveSelection:
    def test_purchase_order_line_alias(self):
        from infor_mcp.services_registry import resolve_selection

        service = get_service("PurchaseOrder_v3")
        selection = resolve_selection(
            service,
            "orderIdentifier,purchaseOrderLine.*",
        )
        assert selection == [
            "PurchaseOrder_v3.orderIdentifier",
            "PurchaseOrder_v3.Line.*",
        ]

    def test_purchase_order_qualified_line_alias(self):
        from infor_mcp.services_registry import resolve_selection

        service = get_service("PurchaseOrder_v3")
        selection = resolve_selection(
            service, "PurchaseOrder_v3.purchaseOrderLine.*"
        )
        assert selection == ["PurchaseOrder_v3.Line.*"]


class TestEnvelope:
    def test_includes_activation_company(self):
        service = get_service("PurchaseOrder_v3")
        body = build_list_request(
            service,
            selection=["PurchaseOrder_v3.*"],
            max_objects=5,
        )
        envelope = build_envelope(service.namespace, "List", body, company=100)
        assert "<company>100</company>" in envelope
        assert 'xmlns:bo="http://www.infor.com/businessinterface/PurchaseOrder_v3"' in envelope
        assert "<bo:List>" in envelope

    def test_purchase_invoice_list_operation(self):
        service = get_service("PurchaseInvoice")
        assert service.list_request_element == "ListPurchaseInvoicesRequest"
        body = build_list_request(service, selection=["PurchaseInvoice.*"], max_objects=10)
        assert body.startswith("<ListPurchaseInvoicesRequest>")
