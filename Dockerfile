FROM python:3.12-slim

WORKDIR /app

# Install uv for fast dependency installation
RUN pip install --no-cache-dir uv

# Copy project files
COPY pyproject.toml README.md ./
COPY vmware_aiops/ vmware_aiops/
COPY mcp_server/ mcp_server/
COPY examples/ examples/

# Install dependencies
RUN uv pip install --system --no-cache .

# Config directory (mount at runtime)
RUN mkdir -p /root/.vmware-aiops

# MCP server uses stdio transport — no port needed
CMD ["python", "-m", "mcp_server"]
