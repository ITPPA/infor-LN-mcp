"""
MCP Prompts for Common Infor LN Workflows

Pre-crafted instruction sets that guide the LLM through multi-step LN queries.
"""

import logging

logger = logging.getLogger("infor_mcp.prompts")


def register_prompts(mcp):
    """Register MCP prompts for common Infor LN workflows."""

    @mcp.prompt()
    async def purchase_order_status() -> str:
        """
        Check purchase order status — open POs, supplier details, and line items.
        """
        return (
            "You are checking purchase order status in Infor LN. Follow these steps:\n\n"
            "1. Query open purchase orders:\n"
            '   - Use list_ln_records with service="PurchaseOrder_v3"\n'
            '   - Fields: "orderIdentifier,buyFromSupplierCode,status,orderDatetime,Line.*"\n'
            "   - Apply filters if the user specified a supplier or status\n"
            "   - Set limit to 50 for a good overview\n\n"
            "2. For a specific PO, use show_ln_record:\n"
            '   - service="PurchaseOrder_v3", key_values="orderIdentifier=PO_NUMBER"\n\n'
            "3. Summarize:\n"
            "   - Total open POs and value if amounts are available\n"
            "   - POs by supplier\n"
            "   - Line-level details for specific POs if requested\n"
        )

    @mcp.prompt()
    async def vendor_spend_analysis() -> str:
        """
        Analyze supplier/vendor activity using business partners and purchase invoices.
        """
        return (
            "You are analyzing supplier activity in Infor LN. Follow these steps:\n\n"
            "1. List suppliers if needed:\n"
            '   - list_ln_records service="BusinessPartner_v3"\n'
            '   - Fields: "businessPartnerCode,name,status"\n'
            "   - Filter by businessPartnerCode or name if specified\n\n"
            "2. Get supplier details:\n"
            '   - show_ln_record service="BusinessPartner_v3"\n'
            '   - key_values="businessPartnerCode=CODE"\n\n'
            "3. List purchase invoices:\n"
            '   - list_ln_records service="PurchaseInvoice"\n'
            "   - Filter by supplier if possible\n\n"
            "4. Summarize spending patterns and top suppliers.\n"
        )

    @mcp.prompt()
    async def ap_aging_analysis() -> str:
        """
        Analyze accounts payable — list supplier invoices and payment status.
        """
        return (
            "You are analyzing AP invoices in Infor LN. Follow these steps:\n\n"
            "1. List purchase invoices:\n"
            '   - list_ln_records service="PurchaseInvoice"\n'
            '   - Fields: "invoiceId,sourceCompany,postingDate,PurchaseInvoiceLine.*"\n'
            "   - Set limit to 100\n\n"
            "2. For a specific invoice:\n"
            '   - show_ln_record service="PurchaseInvoice"\n'
            '   - key_values="invoiceId=INVOICE_ID"\n\n'
            "3. Summarize by posting date, company, and outstanding amounts if available.\n"
        )

    @mcp.prompt()
    async def sales_order_inquiry() -> str:
        """
        Investigate sales orders — status, customer, and line details.
        """
        return (
            "You are investigating sales orders in Infor LN. Follow these steps:\n\n"
            "1. List sales orders:\n"
            '   - list_ln_records service="SalesOrder"\n'
            '   - Fields: "salesOrder,soldToBusinessPartner,orderCurrency,salesOrderHeaderDate,SalesOrderLine.*"\n\n'
            "2. For a specific order:\n"
            '   - show_ln_record service="SalesOrder"\n'
            '   - key_values="salesOrder=ORDER_NUMBER"\n\n'
            "3. Summarize order status, customer, dates, and line details.\n"
        )

    @mcp.prompt()
    async def inventory_inquiry() -> str:
        """
        Check inventory levels — warehouse stock and item master data.
        """
        return (
            "You are checking inventory in Infor LN. Follow these steps:\n\n"
            "1. For stock by warehouse and item:\n"
            '   - show_ln_record service="WarehouseItemInventory"\n'
            '   - key_values="Warehouse=WH_CODE&Item=ITEM_CODE"\n'
            "   - Or only Warehouse or Item if partial keys are accepted\n\n"
            "2. For item master details:\n"
            '   - show_ln_record service="Item_v3"\n'
            '   - key_values="itemCode=ITEM_CODE"\n\n'
            "3. List warehouses if needed:\n"
            '   - list_ln_records service="Warehouse_v2"\n\n'
            "4. Summarize on-hand quantities, units, and item descriptions.\n"
        )

    @mcp.prompt()
    async def month_end_close_checklist() -> str:
        """
        Month-end checklist — open POs, uninvoiced receipts, and pending items.
        """
        return (
            "You are helping with month-end close in Infor LN. Check:\n\n"
            "1. Open purchase orders:\n"
            '   - list_ln_records service="PurchaseOrder_v3"\n'
            "   - Filter by status if applicable\n\n"
            "2. Recent purchase invoices:\n"
            '   - list_ln_records service="PurchaseInvoice"\n\n'
            "3. Open sales orders:\n"
            '   - list_ln_records service="SalesOrder"\n\n'
            "4. Summarize blocking items by category and recommended priority.\n"
        )

    logger.info("Registered MCP prompts")
