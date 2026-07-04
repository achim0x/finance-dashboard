"""MCP server launcher (streamable HTTP; run behind a TLS reverse proxy)."""
import argparse
import os

from mcp_server.server import main


def _run():
    p = argparse.ArgumentParser(description="Musterdepot MCP server (streamable HTTP)")
    p.add_argument("--host", default=os.getenv("MUSTERDEPOT_MCP_HOST", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(os.getenv("MUSTERDEPOT_MCP_PORT", "8000")))
    a = p.parse_args()
    main(a.host, a.port)


if __name__ == "__main__":
    _run()
