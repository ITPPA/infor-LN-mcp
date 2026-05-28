# Infor LN MCP Server

MCP (Model Context Protocol) server for **Infor LN** — an AI orchestration layer that gives LLMs structured, read-only access to LN data through the ION API Gateway and c4ws SOAP Web Services.

Ask your ERP questions in plain language. Get answers from live LN data.

> **Public repository** — never commit credentials (`.ionapi`, `.env`). Use `.env.example` as a template only.

## What This Does

Connect an MCP-compatible AI client (Claude, AnythingLLM, etc.) to your Infor LN environment. Query purchase orders, business partners, items, sales orders, invoices, warehouses, inventory, and employees in natural language.

**Example prompts:**
- "List open purchase orders for supplier SUPPLIER01"
- "Show item master details for item ITEM001"
- "What purchase invoices were posted this month?"
- "Show inventory for warehouse WH01 and item ITEM001"

## Prerequisites

- Python 3.11+
- Access to an Infor LN environment with ION API Gateway
- ION API **Backend Service** app + `.ionapi` credentials file
- LN service account with read-only access (recommended for Phase 1)

### Configure ION API Credentials

#### Step A: Create the Authorized App

1. Log into your Infor CloudSuite environment
2. Navigate to **Infor OS > ION API** (or search for "ION API" in the hamburger menu)
3. Go to **Authorized Apps**
4. Click + Add (or "Create New")
5. Configure:
    Name: InforMCP (or any descriptive name)
    Type: Backend Service
    Description: "MCP Server for AI-powered LN access"
6. Save the application

#### Step B: Download Credentials

1. In your Authorized App, click Download Credentials
2. Select Service Accounts
3. Map it to a CloudSuite user — this user determines what the MCP server can access
  - For Phase 1 (read-only), map to a user with inquiry-level access
  - The user should have access to the financial modules you want to query
  - **Do NOT map to an admin account** — use least-privilege

This downloads a .ionapi file (JSON format)
Place it at config/.ionapi in the project directory

---

## Production deployment

### 1. Install standalone on node server

#### Clone the repo

```bash
git clone https://github.com/ITPPA/infor-LN-mcp.git /opt/infor-LN-mcp
cd /opt/infor-LN-mcp

python3 -m venv .venv
source .venv/bin/activate
pip install -e .

### 2. Set Environment Variables

```bash
mkdir -p /opt/infor-LN-mcp/config
cp /secure/path/to/credentials.ionapi config/.ionapi

cp .env.example .env
```

Edit `.env` with your environment values:

```env
IONAPI_PATH=config/.ionapi
INFOR_ION_TENANT_ID=YOUR_TENANT_ID
INFOR_LN_COMPANY=100
```

| Variable | Required | Description |
|----------|----------|-------------|
| `IONAPI_PATH` | Yes | Path to the `.ionapi` OAuth credentials file |
| `INFOR_ION_TENANT_ID` | Yes | ION API tenant ID — unique per environment. Used in URL: `/{tenant}/LN/c4ws/services/...` |
| `INFOR_LN_COMPANY` | Yes | LN company number in the SOAP `<Activation>` header |
| `INFOR_LN_LANGUAGE` | No | Response language (e.g. `en`, `fr`) |

**How to find `INFOR_ION_TENANT_ID`:** it appears in your ION API URLs and WSDL addresses, e.g. `https://mingle-ionapi.{region}.inforcloudsuite.com/YOUR_TENANT_ID/LN/c4ws/services/...`

### 3. Verify the installation

```bash
source .venv/bin/activate

# Check OAuth
python -c "
import asyncio
from infor_mcp.auth import IONAuthManager
async def main():
    auth = IONAuthManager('config/.ionapi')
    token = await auth.get_token()
    print('Auth OK')
    await auth.close()
asyncio.run(main())
"

# Start the MCP server (stdio)
infor-mcp
```

On startup, logs should show:

```
Configured for tenant: YOUR_TENANT_ID (INFOR_ION_TENANT_ID), company: 100, ...
```

### Install and run With AnythingLLM (Docker)

> Self-hosted only — see [AnythingLLM MCP on Docker](https://docs.anythingllm.com/mcp-compatibility/docker).

**Deploy the project** (mount at a fixed path or inside storage):

```bash
git clone https://github.com/ITPPA/infor-LN-mcp.git /opt/infor-LN-mcp
mkdir -p /opt/infor-LN-mcp/config
cp /secure/path/to/credentials.ionapi /opt/infor-LN-mcp/config/.ionapi
```

**Docker Compose** — mount the project and storage:

```yaml
services:
  anythingllm:
    image: mintplexlabs/anythingllm
    environment:
      - STORAGE_LOCATION=/app/server/storage
    volumes:
      - ./anythingllm_storage:/app/server/storage
      - /opt/infor-LN-mcp:/app/infor-LN-mcp
```

**MCP config** — edit `anythingllm_storage/plugins/anythingllm_mcp_servers.json`:

```json
{
  "mcpServers": {
    "infor-ln": {
      "command": "uvx",
      "args": ["infor-mcp"],
      "cwd": "/app/infor-LN-mcp",
      "env": {
        "IONAPI_PATH": "/app/infor-LN-mcp/config/.ionapi",
        "INFOR_ION_TENANT_ID": "YOUR_TENANT_ID",
        "INFOR_LN_COMPANY": "100"
      }
    }
  }
}
```

AnythingLLM Docker includes **`uv`** for Python MCP servers — no manual venv needed inside the container.

**First-time warm-up** (optional, speeds up first start):

```bash
docker exec -it <anythingllm-container> uv sync --directory /app/infor-LN-mcp
> ou
docker exec -it <anythingllm-container> /bin/bash
anythingllm@<anythingllm-container>: uv tool install -e /app/infor-LN-mcp
```

**Verify:** open **Agent Skills** in AnythingLLM → `infor-ln` should be **running** with 4 tools → use `@agent` in chat.

**AnythingLLM limitations:**
- Tools only — Resources and Prompts from this server are not supported
- Use a model with reliable tool-calling

| Issue | Solution |
|-------|----------|
| MCP not listed | Open Agent Skills page; check JSON syntax |
| Missing tenant | Set `INFOR_ION_TENANT_ID` in the MCP `env` block |
| Slow first start | Run `uv sync --directory /app/infor-LN-mcp` in the container |
| Tools not invoked | Use `@agent` and a capable LLM model |


### Run with Claude Desktop


Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "infor-ln": {
      "command": "/opt/infor-LN-mcp/.venv/bin/python",
      "args": ["-m", "infor_mcp.server"],
      "cwd": "/opt/infor-LN-mcp",
      "env": {
        "IONAPI_PATH": "/opt/infor-LN-mcp/config/.ionapi",
        "INFOR_ION_TENANT_ID": "YOUR_TENANT_ID",
        "INFOR_LN_COMPANY": "100"
      }
    }
  }
}
```

---

## Development and testing

Use this workflow on a **dev/sandbox LN environment** — not production data.

### Local setup

```bash
git clone https://github.com/ITPPA/infor-LN-mcp.git
cd infor-LN-mcp

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
# Edit .env with your sandbox tenant, company, and IONAPI_PATH
mkdir -p config && cp ~/sandbox/.ionapi config/.ionapi
```

### Unit tests (no LN connection required)

```bash
source .venv/bin/activate
pytest -v
```

Unit tests cover SOAP envelope building and the HTTP client (mocked). No `.ionapi` needed.

### Integration tests (live LN API)

Requires `.env`, `config/.ionapi`, and data in your tenant.

```bash
source .venv/bin/activate
INTEGRATION=1 pytest tests/test_api.py -v
```

### Interactive test — MCP Inspector

```bash
source .venv/bin/activate
mcp dev src/infor_mcp/server.py
```

Test tools in order:

1. `list_ln_services` — `{}`
2. `get_ln_service_info` — `{"service": "PurchaseOrder_v3"}`
3. `list_ln_records` — sandbox filters, e.g.:

```json
{
  "service": "PurchaseOrder_v3",
  "fields": "orderIdentifier,buyFromSupplierCode,status,Line.*",
  "filters": "{\"buyFromSupplierCode\": \"SUPPLIER01\"}",
  "limit": 20
}
```

### Claude Code (dev)

```bash
claude mcp add infor-ln -- python -m infor_mcp.server
```

Ensure `INFOR_ION_TENANT_ID` and `INFOR_LN_COMPANY` are set in the environment or `.env`.

---

## Available Tools (Phase 1)

| Tool | Description |
|------|-------------|
| `list_ln_services` | Discover available LN SOAP services |
| `get_ln_service_info` | Metadata, key fields, filter examples |
| `list_ln_records` | List/search records (List operations) |
| `show_ln_record` | Show a record by key field(s) |

## Available LN Services

| Service | Description |
|---------|-------------|
| `PurchaseOrder_v3` | Purchase orders |
| `BusinessPartner_v3` | Business partners (suppliers/customers) |
| `Item_v3` | Items / articles |
| `SalesOrder` | Sales orders |
| `PurchaseInvoice` | Supplier invoices |
| `Warehouse_v2` | Warehouses |
| `WarehouseItemInventory` | Warehouse stock (Show only) |
| `Employee_v2` | Employees |
| `Customer360` | Customer 360 view (Show only) |

## Example Tool Calls

```
list_ln_records(
  service="PurchaseOrder_v3",
  fields="orderIdentifier,buyFromSupplierCode,status,Line.*",
  filters='{"buyFromSupplierCode": "SUPPLIER01"}',
  limit=20
)

show_ln_record(
  service="Item_v3",
  key_values="itemCode=ITEM001"
)
```

## Available Prompts

Supported by MCP clients that expose Prompts (not AnythingLLM):

| Prompt | Description |
|--------|-------------|
| `purchase_order_status` | PO status and line details |
| `vendor_spend_analysis` | Supplier activity |
| `ap_aging_analysis` | Purchase invoices |
| `sales_order_inquiry` | Sales orders |
| `inventory_inquiry` | Stock and items |
| `month_end_close_checklist` | Month-end open items |

## API Architecture

```
POST https://mingle-ionapi.{region}.inforcloudsuite.com/{INFOR_ION_TENANT_ID}/LN/c4ws/services/{ServiceName}
```

- **Auth:** OAuth Bearer token (`.ionapi`)
- **Tenant:** `INFOR_ION_TENANT_ID` — URL path segment
- **Company:** `INFOR_LN_COMPANY` — SOAP `<Activation><company>N</company></Activation>`
- **Phase 1:** read-only `List` / `Show` operations

## Security (public repo)

- **Never commit** `.env`, `config/.ionapi`, or any credentials
- `.gitignore` excludes `.env`, `config/.ionapi`, `.venv/`, `DOCS_API/`
- Use a **least-privilege** LN service account in production
- Phase 1 is read-only — no write operations exposed
- Rotate ION API credentials if accidentally exposed
- All API calls are auditable via ION API Gateway logs

## Project Structure

```
infor-LN-mcp/
├── config/
│   └── .ionapi              # Credentials (gitignored — create locally)
├── src/infor_mcp/
│   ├── server.py            # MCP entry point
│   ├── auth.py              # OAuth (.ionapi)
│   ├── client.py            # LN SOAP client
│   ├── soap_builder.py      # SOAP XML builder
│   ├── services_registry.py # Service catalog
│   └── tools/query.py       # Read-only MCP tools
├── tests/
├── .env.example             # Template (safe to commit)
└── pyproject.toml
```

## Roadmap

- **Phase 1** (current): Read-only List/Show on services
- **Phase 2**: Write operations with confirmation gates
- **Phase 3**: Agentic multi-step workflows

## License

MIT
