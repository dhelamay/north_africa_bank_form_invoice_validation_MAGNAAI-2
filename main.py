"""
MagnaAI L/C Platform — Entry point.

Usage:
    python main.py                 # Start FastAPI server (port 8000)
    python main.py --mcp           # Start FastMCP server (port 8100)
    python main.py --tools         # List all tools
    python main.py --both          # Start both servers
"""
import sys, os, logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Also add v1 agents path for business logic reuse
v1_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lc_platform")
if os.path.exists(v1_path):
    sys.path.insert(0, v1_path)

from dotenv import load_dotenv
load_dotenv(override=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")


def start_api():
    """Start the FastAPI server."""
    import uvicorn
    from config.settings import get_settings
    s = get_settings()
    print(f"\n  MagnaAI API Server — http://{s.app_host}:{s.app_port}")
    print(f"  Docs: http://localhost:{s.app_port}/docs\n")
    uvicorn.run("api.main:app", host=s.app_host, port=s.app_port, reload=True)


def start_mcp():
    """Start the FastMCP SSE server."""
    from config.settings import get_settings
    from tools.server import mcp, list_tools
    s = get_settings()
    tools = list_tools()
    print(f"\n  MagnaAI MCP Server — http://{s.app_host}:{s.mcp_port}")
    print(f"  {len(tools)} tools registered:\n")
    for t in tools:
        print(f"    {t['name']}: {t['description'][:60]}")
    print()
    mcp.run(transport="sse", host=s.app_host, port=s.mcp_port)


def show_tools():
    from tools.server import list_tools
    tools = list_tools()
    print(f"\n  MagnaAI — {len(tools)} FastMCP Tools\n  {'='*40}\n")
    for t in tools:
        tags = ", ".join(t.get("tags", []))
        print(f"  {t['name']}  [{tags}]")
        print(f"    {t['description']}\n")


if __name__ == "__main__":
    if "--mcp" in sys.argv:
        start_mcp()
    elif "--tools" in sys.argv:
        show_tools()
    elif "--both" in sys.argv:
        import threading
        threading.Thread(target=start_mcp, daemon=True).start()
        start_api()
    else:
        start_api()
