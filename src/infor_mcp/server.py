"""
Infor LN MCP Server

MCP server for Infor LN — an AI-powered orchestration layer that gives LLMs
structured access to LN c4ws SOAP data through the ION API Gateway.

Phase 1: Read-only query tools for searching and browsing LN data.

Usage:
    infor-mcp
    mcp dev src/infor_mcp/server.py
    uvicorn infor_mcp.server:app --host 0.0.0.0 --port 8080
"""

import os
import logging
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

from infor_mcp.auth import IONAuthManager
from infor_mcp.client import LNSoapClient
from infor_mcp.tools.query import register_query_tools
from infor_mcp.resources.reference import register_resources
from infor_mcp.prompts.workflows import register_prompts

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("infor_mcp")

IONAPI_PATH = os.getenv(
    "IONAPI_PATH",
    str(Path(__file__).parent.parent.parent / "config" / ".ionapi"),
)

INFOR_LN_COMPANY = os.getenv("INFOR_LN_COMPANY", "100")
INFOR_ION_TENANT_ID = os.getenv("INFOR_ION_TENANT_ID") or None
INFOR_LN_LANGUAGE = os.getenv("INFOR_LN_LANGUAGE") or None

SERVER_NAME = "Infor LN"
SERVER_VERSION = "0.2.0"


def create_server() -> FastMCP:
    """Create and configure the MCP server with tools, resources, and prompts."""
    mcp = FastMCP(
        SERVER_NAME,
        instructions=(
            "You are connected to an Infor LN ERP system through the ION API Gateway. "
            "You can query LN c4ws SOAP services to retrieve purchasing, sales, inventory, "
            "and master data.\n\n"
            "Key tips:\n"
            "- Use list_ln_services to discover available LN services\n"
            "- Use get_ln_service_info to understand fields and key requirements\n"
            "- Use list_ln_records to search and list records (List operations)\n"
            "- Use show_ln_record when you know the exact record key\n"
            "- Check infor://reference/ln-services for common service names\n"
            "- Filters are JSON objects: {\"buyFromSupplierCode\": \"SUPPLIER01\"}\n"
            "- Key values format: \"orderIdentifier=PO123\" or \"Warehouse=WH01&Item=ITEM01\"\n"
            "- Phase 1 is read-only — write operations are not available\n"
        ),
    )

    ionapi_path = Path(IONAPI_PATH)
    if not ionapi_path.exists():
        logger.warning(
            f"ION API credentials file not found at: {ionapi_path}\n"
            "The server will start but tool calls will fail until credentials are configured."
        )
        _register_with_placeholder(mcp, ionapi_path)
    else:
        try:
            if not INFOR_ION_TENANT_ID:
                raise ValueError(
                    "INFOR_ION_TENANT_ID is not set. "
                    "Add it to .env (e.g. INFOR_ION_TENANT_ID=YOUR_TENANT_PRD)."
                )
            auth = IONAuthManager(ionapi_path)
            client = LNSoapClient(
                auth,
                company=INFOR_LN_COMPANY,
                tenant_id=INFOR_ION_TENANT_ID,
                language=INFOR_LN_LANGUAGE,
            )
            register_query_tools(mcp, client)
            logger.info(
                f"Configured for tenant: {client.tenant_id} (INFOR_ION_TENANT_ID), "
                f"company: {INFOR_LN_COMPANY}, "
                f"API base: {auth.base_url}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize LN SOAP client: {e}")
            _register_with_placeholder(mcp, ionapi_path)

    register_resources(mcp)
    register_prompts(mcp)

    logger.info(f"{SERVER_NAME} MCP Server v{SERVER_VERSION} initialized")
    return mcp


def _register_with_placeholder(mcp: FastMCP, ionapi_path: Path):
    """Register placeholder tools when credentials are missing."""

    _SETUP_MSG = (
        f"ERROR: ION API credentials not configured.\n\n"
        f"Expected credentials file at: {ionapi_path}\n\n"
        f"To set up:\n"
        f"1. In Infor OS, go to ION API > Authorized Apps\n"
        f"2. Create a Backend Service application\n"
        f"3. Create a service account mapped to an LN user\n"
        f"4. Download the .ionapi credentials file\n"
        f"5. Place it at: {ionapi_path}\n"
        f"6. Set INFOR_ION_TENANT_ID and INFOR_LN_COMPANY in .env\n"
        f"7. Restart the MCP server"
    )

    @mcp.tool()
    async def list_ln_services(**kwargs) -> str:
        """List available Infor LN c4ws SOAP services."""
        return _SETUP_MSG

    @mcp.tool()
    async def get_ln_service_info(**kwargs) -> str:
        """Get metadata for an LN service."""
        return _SETUP_MSG

    @mcp.tool()
    async def list_ln_records(**kwargs) -> str:
        """List records from an Infor LN service."""
        return _SETUP_MSG

    @mcp.tool()
    async def show_ln_record(**kwargs) -> str:
        """Show a specific LN record by key."""
        return _SETUP_MSG

    logger.warning("Registered placeholder tools (no credentials)")


mcp = create_server()
app = mcp.sse_app()


def main():
    """Entry point for stdio transport (Claude Desktop, Claude Code)."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
