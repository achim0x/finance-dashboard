"""FastMCP instance + entry point (streamable HTTP behind TLS)."""
import sys

from mcp.server.fastmcp import FastMCP

from mcp_server.tools import register_all

mcp = FastMCP("Musterdepot")
register_all(mcp)


def main(host: str, port: int) -> None:
    import uvicorn

    from mcp_server.http_app import build_asgi_app

    print(
        f"[Musterdepot MCP] streamable-HTTP on http://{host}:{port}/mcp "
        f"(static Bearer key from MUSTERDEPOT_MCP_KEY; put TLS in front).",
        file=sys.stderr,
    )
    uvicorn.run(build_asgi_app(), host=host, port=port, log_level="info")
