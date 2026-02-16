"""
Internationalization (i18n) engine.
Supports: English, Arabic, Spanish, Italian.
"""

from __future__ import annotations
from config.constants import SUPPORTED_LANGUAGES, RTL_LANGUAGES

# ── UI Strings (embedded for simplicity — can be loaded from JSON files) ──
STRINGS = {
    "en": {
        "app_title": "L/C Document Processing Dashboard",
        "upload_pdf": "Upload PDF",
        "extract_info": "Extract Information",
        "choose_llm": "Choose LLM",
        "extraction_method": "Extraction Method",
        "vision_ai": "Vision AI (send PDF to LLM)",
        "text_llm": "Text → LLM (fast)",
        "ocr_llm": "OCR → LLM",
        "extracting": "Extracting information...",
        "extraction_complete": "Extraction complete!",
        "fields_found": "fields found",
        "chat_placeholder": "Ask a question about the document...",
        "form_tab": "L/C Application Form",
        "chat_tab": "Chat with Document",
        "preview_tab": "PDF Text Preview",
        "summary_tab": "Extracted Summary",
        "save_form": "Save Form Data",
        "export_json": "Export as JSON",
        "validate_docs": "Validate Documents",
        "validation_report": "Validation Report",
        "scanned_pdf_warning": "Scanned/image PDF detected — will use Vision AI.",
        "no_text_warning": "No text extracted. If you used Vision AI, check the Summary tab.",
        "upload_prompt": "Upload a PDF in the sidebar to get started.",
        "fields_missing": "Fields Missing",
        "fields_extracted": "Fields Found",
        "basic_information": "Basic Information",
        "account_information": "Account Information",
        "beneficiary_information": "Beneficiary Information",
        "credit_amount": "Credit Amount",
        "goods_services": "Goods / Services",
        "lc_type_conditions": "L/C Type & Conditions",
        "shipment_details": "Shipment Details",
        "delivery_terms": "Delivery Terms",
        "required_documents": "Required Documents",
        "payment_conditions": "Payment Conditions",
        "expiry_information": "Expiry Information",
        "additional_conditions": "Additional Conditions",
        "compliance_legal": "Compliance & Legal",
        "financial_information": "Financial Information",
        "special_conditions": "Special Conditions",
    },
    "ar": {
        "app_title": "لوحة معالجة مستندات الإعتماد المستندي",
        "upload_pdf": "تحميل ملف PDF",
        "extract_info": "استخراج المعلومات",
        "choose_llm": "اختر محرك الذكاء الاصطناعي",
        "extraction_method": "طريقة الاستخراج",
        "vision_ai": "الذكاء الاصطناعي البصري",
        "text_llm": "نص → ذكاء اصطناعي (سريع)",
        "ocr_llm": "التعرف الضوئي → ذكاء اصطناعي",
        "extracting": "جاري استخراج المعلومات...",
        "extraction_complete": "تم الاستخراج بنجاح!",
        "fields_found": "حقول مستخرجة",
        "chat_placeholder": "اطرح سؤالاً حول المستند...",
        "form_tab": "نموذج طلب الإعتماد",
        "chat_tab": "محادثة مع المستند",
        "preview_tab": "معاينة نص PDF",
        "summary_tab": "ملخص الاستخراج",
        "save_form": "حفظ بيانات النموذج",
        "export_json": "تصدير كـ JSON",
        "validate_docs": "التحقق من المستندات",
        "validation_report": "تقرير التحقق",
        "scanned_pdf_warning": "تم اكتشاف ملف PDF ممسوح ضوئياً — سيتم استخدام الذكاء البصري.",
        "no_text_warning": "لم يتم استخراج نص. إذا استخدمت الذكاء البصري، تحقق من تبويب الملخص.",
        "upload_prompt": "قم بتحميل ملف PDF في الشريط الجانبي للبدء.",
        "fields_missing": "حقول مفقودة",
        "fields_extracted": "حقول مستخرجة",
    },
    "es": {
        "app_title": "Panel de Procesamiento de Documentos L/C",
        "upload_pdf": "Subir PDF",
        "extract_info": "Extraer Información",
        "choose_llm": "Elegir LLM",
        "chat_placeholder": "Haga una pregunta sobre el documento...",
        "form_tab": "Formulario de Solicitud L/C",
        "chat_tab": "Chat con el Documento",
        "preview_tab": "Vista Previa del Texto PDF",
        "summary_tab": "Resumen de Extracción",
        "save_form": "Guardar Datos",
        "export_json": "Exportar como JSON",
        "validate_docs": "Validar Documentos",
        "upload_prompt": "Suba un PDF en la barra lateral para comenzar.",
    },
    "it": {
        "app_title": "Dashboard Elaborazione Documenti L/C",
        "upload_pdf": "Carica PDF",
        "extract_info": "Estrai Informazioni",
        "choose_llm": "Scegli LLM",
        "chat_placeholder": "Fai una domanda sul documento...",
        "form_tab": "Modulo Richiesta L/C",
        "chat_tab": "Chat con il Documento",
        "preview_tab": "Anteprima Testo PDF",
        "summary_tab": "Riepilogo Estrazione",
        "save_form": "Salva Dati",
        "export_json": "Esporta come JSON",
        "validate_docs": "Valida Documenti",
        "upload_prompt": "Carica un PDF nella barra laterale per iniziare.",
    },
}


def t(key: str, lang: str = "en") -> str:
    """Translate a UI string key. Falls back to English."""
    return STRINGS.get(lang, STRINGS["en"]).get(key, STRINGS["en"].get(key, key))


def is_rtl(lang: str) -> bool:
    """Check if a language is right-to-left."""
    return lang in RTL_LANGUAGES


def get_available_languages() -> list[dict[str, str]]:
    """Return list of available languages with labels."""
    return [
        {"code": "en", "label": "English", "native": "English"},
        {"code": "ar", "label": "Arabic", "native": "العربية"},
        {"code": "es", "label": "Spanish", "native": "Español"},
        {"code": "it", "label": "Italian", "native": "Italiano"},
    ]
