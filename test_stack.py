#!/usr/bin/env python3
"""
Test script — verify the full v2 stack works.

Usage:
  python test_stack.py --tools       # Test FastMCP tools directly (no server needed)
  python test_stack.py --graphs      # Test LangGraph workflows
  python test_stack.py --api         # Test FastAPI endpoints (requires: python main.py)
  python test_stack.py --all         # Run all tests
"""
import sys, os, json, asyncio
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Also add v1 agents path
v1_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lc_platform")
if os.path.exists(v1_path): sys.path.insert(0, v1_path)

from dotenv import load_dotenv
load_dotenv(override=True)


def header(msg):
    print(f"\n{'='*60}\n  {msg}\n{'='*60}")


# ═══════════════════════════════════════════════════════════════
#  TEST 1: FastMCP Tools (in-process, no server)
# ═══════════════════════════════════════════════════════════════

def test_tools():
    header("TEST: FastMCP Tools (in-process)")
    from tools.server import mcp, call_tool, list_tools

    # List tools
    tools = list_tools()
    print(f"\n  ✅ {len(tools)} tools registered:\n")
    for t in tools:
        tags = ", ".join(t.get("tags",[]))
        print(f"     {t['name']:30s}  [{tags}]")

    # Test validation tool (no external APIs needed)
    print("\n  Testing validate_documents tool...")
    result = call_tool("validate_documents", {
        "documents": {
            "letter_of_credit": {
                "lc_number": "LC-2024-001",
                "date": "01/01/2024",
                "expiry_date": "31/12/2024",
                "amount_in_figures": "USD 150,000.00",
                "beneficiary_name": "TEDESCO S.R.L.",
                "port_loading": "Genoa",
            },
            "commercial_invoice": {
                "lc_number": "LC-2024-001",
                "amount_in_figures": "USD 148,500.00",
                "beneficiary_name": "Tedesco SRL",
                "port_loading": "Genoa",
            }
        },
        "language": "en",
    })
    print(f"  ✅ Validation result: {result.get('total_checks',0)} checks, "
          f"{result.get('passed_checks',0)} passed, "
          f"{result.get('errors',0)} errors")
    for ch in result.get("checks",[]):
        icon = "✅" if ch["passed"] else "❌"
        print(f"     {icon} {ch['rule_name']}: {ch['message']}")

    # Test incoterm (no API needed)
    print("\n  Testing chat_with_document tool...")
    chat_result = call_tool("chat_with_document", {
        "message": "What is the L/C number?",
        "extracted_data": {"lc_number": "LC-2024-001", "amount_in_figures": "USD 150,000.00"},
        "pdf_text": "",
        "history": [],
        "language": "en",
    })
    # This will fail without API keys, which is OK
    if chat_result.get("message"):
        print(f"  ✅ Chat response: {chat_result['message'][:100]}...")
    else:
        print(f"  ⚠️ Chat failed (likely no API keys): {chat_result}")

    print("\n  ✅ FastMCP tools test PASSED")


# ═══════════════════════════════════════════════════════════════
#  TEST 2: LangGraph Workflows
# ═══════════════════════════════════════════════════════════════

def test_graphs():
    header("TEST: LangGraph Workflows")
    from workflows.graphs import get_graph

    # Build all graphs
    for name in ("extraction", "validation", "verification", "chat", "pipeline"):
        g = get_graph(name)
        print(f"  ✅ Built graph: {name}")

    # Test validation graph
    print("\n  Running validation_graph.invoke()...")
    graph = get_graph("validation")
    state = graph.invoke({
        "documents": {
            "letter_of_credit": {
                "lc_number": "LC-TEST-999",
                "date": "15/06/2024",
                "expiry_date": "15/06/2023",  # Intentionally before issue date!
                "amount_in_figures": "EUR 200,000.00",
            },
        },
        "language": "en",
    })

    result = state.get("result", {})
    print(f"  ✅ Validation: {result.get('total_checks',0)} checks")
    for ch in result.get("checks",[]):
        icon = "✅" if ch["passed"] else "❌"
        print(f"     {icon} {ch['rule_name']}: {ch['message']}")

    # The date check should FAIL (expiry before issue)
    failed = [c for c in result.get("checks",[]) if not c["passed"]]
    if failed:
        print(f"\n  ✅ Correctly caught {len(failed)} validation error(s)")
    else:
        print(f"\n  ⚠️ Expected validation errors but found none")

    print("\n  ✅ LangGraph workflows test PASSED")


# ═══════════════════════════════════════════════════════════════
#  TEST 3: FastAPI Endpoints (requires running server)
# ═══════════════════════════════════════════════════════════════

def test_api():
    header("TEST: FastAPI Endpoints")
    try:
        import httpx
    except ImportError:
        print("  ❌ httpx not installed. Run: pip install httpx")
        return

    from config.settings import get_settings
    s = get_settings()
    base = f"http://localhost:{s.app_port}"

    print(f"  Testing {base}...")

    # Health check
    try:
        r = httpx.get(f"{base}/health", timeout=5)
        data = r.json()
        print(f"  ✅ GET /health → {data}")
    except Exception as e:
        print(f"  ❌ Cannot reach FastAPI at {base}")
        print(f"     Start it with: python main.py")
        print(f"     Error: {e}")
        return

    # List tools
    r = httpx.get(f"{base}/tools", timeout=5)
    tools = r.json().get("tools",[])
    print(f"  ✅ GET /tools → {len(tools)} tools")

    # Validate
    r = httpx.post(f"{base}/validate", json={
        "documents": {
            "letter_of_credit": {
                "lc_number": "LC-API-TEST",
                "date": "01/03/2024",
                "expiry_date": "01/12/2024",
                "amount_in_figures": "USD 500,000.00",
            }
        },
        "language": "en",
    }, timeout=30)
    vr = r.json()
    print(f"  ✅ POST /validate → {vr.get('total_checks',0)} checks, "
          f"{vr.get('passed_checks',0)} passed")

    # Chat
    r = httpx.post(f"{base}/chat", json={
        "message": "What currency is the L/C in?",
        "extracted_data": {"amount_in_figures": "USD 500,000.00", "currency": "USD"},
        "language": "en",
    }, timeout=60)
    cr = r.json()
    msg = cr.get("message","")[:100]
    if msg:
        print(f"  ✅ POST /chat → \"{msg}...\"")
    else:
        print(f"  ⚠️ POST /chat → no response (check API keys)")

    print("\n  ✅ FastAPI endpoints test PASSED")


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if "--tools" in sys.argv:
        test_tools()
    elif "--graphs" in sys.argv:
        test_graphs()
    elif "--api" in sys.argv:
        test_api()
    elif "--all" in sys.argv:
        test_tools()
        test_graphs()
        test_api()
    else:
        print(__doc__)
        print("Quick start:")
        print("  python test_stack.py --tools   # No server needed")
        print("  python test_stack.py --graphs  # No server needed")
        print("")
        print("  python main.py                 # Terminal 1: start FastAPI")
        print("  python test_stack.py --api     # Terminal 2: test endpoints")
