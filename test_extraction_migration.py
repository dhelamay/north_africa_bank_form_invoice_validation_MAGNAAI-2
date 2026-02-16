"""
Test script to verify PDF extraction now returns pdf_text and is_scanned.
Tests the backend migration from frontend to backend PDF processing.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tools.server import call_tool
import base64

# Create a minimal test PDF (simple text-based PDF)
def create_test_pdf():
    """Create a minimal PDF for testing."""
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from io import BytesIO

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.drawString(100, 750, "TEST LETTER OF CREDIT")
    c.drawString(100, 730, "L/C Number: TEST-001")
    c.drawString(100, 710, "Beneficiary: Test Company Ltd")
    c.drawString(100, 690, "Amount: USD 100,000.00")
    c.drawString(100, 670, "Issue Date: 01/01/2025")
    c.drawString(100, 650, "Expiry Date: 31/12/2025")
    c.showPage()
    c.save()
    return buffer.getvalue()


def test_extraction_returns_pdf_text():
    """Test that extract_lc_document returns pdf_text and is_scanned."""
    print("\n" + "="*60)
    print("Testing PDF Extraction Migration")
    print("="*60 + "\n")

    try:
        # Try to create a test PDF
        try:
            pdf_bytes = create_test_pdf()
            print("✅ Created test PDF with reportlab")
        except ImportError:
            print("⚠️  reportlab not installed, using mock PDF bytes")
            # Use a minimal PDF header for testing
            pdf_bytes = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/Contents 4 0 R\n>>\nendobj\n4 0 obj\n<<\n/Length 44\n>>\nstream\nBT\n/F1 12 Tf\n100 700 Td\n(TEST L/C) Tj\nET\nendstream\nendobj\nxref\n0 5\ntrailer\n<<\n/Size 5\n/Root 1 0 R\n>>\nstartxref\n%%EOF"

        pdf_b64 = base64.b64encode(pdf_bytes).decode()

        print("📤 Calling extract_lc_document tool...")
        result = call_tool("extract_lc_document", {
            "pdf_bytes_b64": pdf_b64,
            "method": "text",
            "llm_provider": "gemini",
            "model_name": "gemini-2.5-flash",
            "language": "en",
        })

        print("\n📥 Response received:")
        print(f"  - success: {result.get('success')}")
        print(f"  - fields_found: {result.get('fields_found')}")
        print(f"  - method_used: {result.get('method_used')}")

        # CHECK NEW FIELDS
        print("\n🔍 Checking new backend fields:")

        has_pdf_text = "pdf_text" in result
        has_is_scanned = "is_scanned" in result

        print(f"  - pdf_text present: {has_pdf_text}")
        if has_pdf_text:
            pdf_text = result.get("pdf_text", "")
            print(f"    Length: {len(pdf_text)} chars")
            if pdf_text:
                print(f"    Preview: {pdf_text[:100]}...")

        print(f"  - is_scanned present: {has_is_scanned}")
        if has_is_scanned:
            is_scanned = result.get("is_scanned")
            print(f"    Value: {is_scanned}")

        # VALIDATION
        print("\n" + "="*60)
        if has_pdf_text and has_is_scanned:
            print("✅ SUCCESS: Migration complete!")
            print("   Backend now returns pdf_text and is_scanned")
            return True
        else:
            print("❌ FAILED: Missing new fields")
            if not has_pdf_text:
                print("   - pdf_text not found in response")
            if not has_is_scanned:
                print("   - is_scanned not found in response")
            return False

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_extraction_returns_pdf_text()
    sys.exit(0 if success else 1)
