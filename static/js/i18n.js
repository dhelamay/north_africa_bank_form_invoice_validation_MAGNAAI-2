/**
 * Internationalization (i18n) for MagnaAI L/C Platform
 * Supports English (en) and Arabic (ar)
 */

const translations = {
    en: {
        // Header
        appTitle: "MagnaAI — Letter of Credit Processing",
        appSubtitle: "AI-Powered Document Extraction & Validation",

        // Sidebar
        uploadPDF: "① Upload Document",
        extractSettings: "② Extract Settings",
        llmProvider: "LLM Provider",
        model: "Model",
        method: "Method",
        extractBtn: "🔍 Extract Information",
        status: "Status",

        // Methods
        visionAI: "Vision AI (Recommended)",
        textExtraction: "Text Extraction",
        ocrLLM: "OCR + LLM",

        // Welcome
        welcomeTitle: "Welcome to MagnaAI",
        welcomeText: "Upload a Letter of Credit PDF to get started.",
        feature1: "AI-powered field extraction",
        feature2: "Multi-language support (EN, AR, ES, IT)",
        feature3: "External API verification (SWIFT, Ports, HS Codes)",
        feature4: "Cross-document validation",

        // Tabs
        tabExtracted: "📋 Extracted",
        tabValidation: "✅ Validation",
        tabVerification: "🔎 Verification",
        tabChat: "💬 Chat",
        tabSearch: "🔍 Deep Search",
        tabPreview: "📝 Preview",
        tabRaw: "🔬 Raw",

        // Extraction
        fieldsFound: "Fields Found",
        processingTime: "Processing Time",
        pdfType: "PDF Type",
        scanned: "Scanned",
        text: "Text",
        saveChanges: "💾 Save Changes",

        // Validation
        validationTitle: "📋 Document Validation",
        runValidation: "Run Validation Checks",
        validationPrompt: "Click 'Run Validation Checks' to cross-validate the extracted data.",
        pass: "PASS",
        warning: "WARNING",
        fail: "FAIL",

        // Verification
        verificationTitle: "🔎 API Verification Panel",
        verificationSubtitle: "Verify fields using external APIs (SWIFT, Ports, HS Codes, Sanctions, etc.)",
        verifyAll: "⚡ Verify All Fields",
        verifyPrompt: "Extract a document first, then verify fields here.",
        verified: "✅ Verified",
        failed: "❌ Failed",
        confidence: "Confidence",

        // Chat
        chatTitle: "💬 Chat Assistant",
        chatSubtitle: "Ask questions about the extracted Letter of Credit document.",
        chatExamples: "Try asking:",
        chatQ1: "What is the total amount?",
        chatQ2: "When does this L/C expire?",
        chatQ3: "Who is the beneficiary?",
        chatQ4: "Summarize the key terms",
        chatPlaceholder: "Ask a question about the document...",
        send: "Send",

        // Search
        searchTitle: "🔍 Deep Research",
        searchSubtitle: "Search the uploaded document + external sources (Perplexity + Exa)",
        searchPlaceholder: "Enter your research query (e.g., 'Verify HSBC Bank SWIFT code')",
        research: "Research",
        searchDoc: "Search uploaded document",
        searchExternal: "Search external sources (Perplexity + Exa)",
        searchPrompt: "Enter a query and click 'Research' to start deep search.",
        sources: "Sources",
        webResults: "Web Results",

        // Preview
        pdfMetadata: "PDF Metadata",
        file: "File",
        textLength: "Text Length",
        characters: "characters",

        // Messages
        uploadFirst: "Please upload a PDF first",
        extractFirst: "Please extract a document first",
        enterQuery: "Please enter a search query",
        processing: "Processing...",
        extracting: "Extracting L/C fields...",
        validating: "Running validation checks...",
        verifying: "Verifying",
        fields: "fields",
        thinking: "Thinking...",
        researching: "Researching with Perplexity + Exa...",

        // Results
        validationComplete: "Validation complete",
        checksOf: "checks passed",
        verified: "Verified",
        researchComplete: "Research complete",

        // Footer
        footerText: "MagnaAI v2.0 — Powered by FastMCP + LangGraph + FastAPI",
        apiDocs: "API Docs",
        streamlitUI: "Streamlit UI",

        // Field labels (common L/C fields)
        lc_number: "L/C Number",
        issue_date: "Issue Date",
        expiry_date: "Expiry Date",
        applicant_name: "Applicant Name",
        beneficiary_name: "Beneficiary Name",
        amount: "Amount",
        currency: "Currency",
        beneficiary_bank_swift: "Beneficiary Bank SWIFT",
        port_loading: "Port of Loading",
        port_destination: "Port of Destination",
        latest_shipment_date: "Latest Shipment Date",
    },

    ar: {
        // Header
        appTitle: "ماجنا إيه آي — معالجة الاعتمادات المستندية",
        appSubtitle: "استخراج وتحقق من المستندات بالذكاء الاصطناعي",

        // Sidebar
        uploadPDF: "① تحميل المستند",
        extractSettings: "② إعدادات الاستخراج",
        llmProvider: "مزود الذكاء الاصطناعي",
        model: "النموذج",
        method: "الطريقة",
        extractBtn: "🔍 استخراج المعلومات",
        status: "الحالة",

        // Methods
        visionAI: "الرؤية بالذكاء الاصطناعي (موصى به)",
        textExtraction: "استخراج النص",
        ocrLLM: "التعرف الضوئي + الذكاء الاصطناعي",

        // Welcome
        welcomeTitle: "مرحباً بك في ماجنا إيه آي",
        welcomeText: "قم بتحميل ملف PDF للاعتماد المستندي للبدء.",
        feature1: "استخراج الحقول بالذكاء الاصطناعي",
        feature2: "دعم متعدد اللغات (EN, AR, ES, IT)",
        feature3: "التحقق عبر APIs الخارجية (SWIFT، الموانئ، أكواد HS)",
        feature4: "التحقق من صحة المستندات",

        // Tabs
        tabExtracted: "📋 المستخرج",
        tabValidation: "✅ التحقق",
        tabVerification: "🔎 المراجعة",
        tabChat: "💬 المحادثة",
        tabSearch: "🔍 البحث العميق",
        tabPreview: "📝 المعاينة",
        tabRaw: "🔬 البيانات الخام",

        // Extraction
        fieldsFound: "الحقول المستخرجة",
        processingTime: "وقت المعالجة",
        pdfType: "نوع الملف",
        scanned: "ممسوح ضوئياً",
        text: "نص",
        saveChanges: "💾 حفظ التغييرات",

        // Validation
        validationTitle: "📋 التحقق من المستند",
        runValidation: "تشغيل فحوصات التحقق",
        validationPrompt: "انقر على 'تشغيل فحوصات التحقق' للتحقق من البيانات المستخرجة.",
        pass: "نجح",
        warning: "تحذير",
        fail: "فشل",

        // Verification
        verificationTitle: "🔎 لوحة التحقق من واجهة برمجة التطبيقات",
        verificationSubtitle: "التحقق من الحقول باستخدام واجهات APIs الخارجية (SWIFT، الموانئ، أكواد HS، العقوبات، إلخ.)",
        verifyAll: "⚡ التحقق من جميع الحقول",
        verifyPrompt: "استخرج مستنداً أولاً، ثم تحقق من الحقول هنا.",
        verified: "✅ تم التحقق",
        failed: "❌ فشل",
        confidence: "الثقة",

        // Chat
        chatTitle: "💬 مساعد المحادثة",
        chatSubtitle: "اطرح أسئلة حول مستند الاعتماد المستندي المستخرج.",
        chatExamples: "جرب السؤال:",
        chatQ1: "ما هو المبلغ الإجمالي؟",
        chatQ2: "متى ينتهي صلاحية الاعتماد المستندي؟",
        chatQ3: "من هو المستفيد؟",
        chatQ4: "لخص الشروط الأساسية",
        chatPlaceholder: "اطرح سؤالاً حول المستند...",
        send: "إرسال",

        // Search
        searchTitle: "🔍 البحث العميق",
        searchSubtitle: "البحث في المستند المحمل + المصادر الخارجية (Perplexity + Exa)",
        searchPlaceholder: "أدخل استعلام البحث الخاص بك (مثل: 'تحقق من رمز SWIFT لبنك HSBC')",
        research: "بحث",
        searchDoc: "البحث في المستند المحمل",
        searchExternal: "البحث في المصادر الخارجية (Perplexity + Exa)",
        searchPrompt: "أدخل استعلاماً وانقر على 'بحث' لبدء البحث العميق.",
        sources: "المصادر",
        webResults: "نتائج الويب",

        // Preview
        pdfMetadata: "بيانات ملف PDF",
        file: "الملف",
        textLength: "طول النص",
        characters: "حرف",

        // Messages
        uploadFirst: "الرجاء تحميل ملف PDF أولاً",
        extractFirst: "الرجاء استخراج مستند أولاً",
        enterQuery: "الرجاء إدخال استعلام بحث",
        processing: "جاري المعالجة...",
        extracting: "استخراج حقول الاعتماد المستندي...",
        validating: "تشغيل فحوصات التحقق...",
        verifying: "التحقق من",
        fields: "الحقول",
        thinking: "جاري التفكير...",
        researching: "البحث باستخدام Perplexity + Exa...",

        // Results
        validationComplete: "اكتمل التحقق",
        checksOf: "فحص نجح",
        verified: "تم التحقق",
        researchComplete: "اكتمل البحث",

        // Footer
        footerText: "ماجنا إيه آي v2.0 — مدعوم بـ FastMCP + LangGraph + FastAPI",
        apiDocs: "وثائق API",
        streamlitUI: "واجهة Streamlit",

        // Field labels (Arabic translations)
        lc_number: "رقم الاعتماد المستندي",
        issue_date: "تاريخ الإصدار",
        expiry_date: "تاريخ الانتهاء",
        applicant_name: "اسم مقدم الطلب",
        beneficiary_name: "اسم المستفيد",
        amount: "المبلغ",
        currency: "العملة",
        beneficiary_bank_swift: "رمز SWIFT للبنك المستفيد",
        port_loading: "ميناء الشحن",
        port_destination: "ميناء الوصول",
        latest_shipment_date: "آخر موعد للشحن",
    }
};

// Current language (default: English)
let currentLang = 'en';

// Translation function
function t(key) {
    return translations[currentLang][key] || key;
}

// Get field label translation
function getFieldLabel(fieldKey) {
    // Try to get translation, fallback to formatted key
    const translated = translations[currentLang][fieldKey];
    if (translated) return translated;

    // Format the key: snake_case → Title Case
    return fieldKey
        .replace(/_/g, ' ')
        .replace(/\b\w/g, l => l.toUpperCase());
}

// Switch language
function setLanguage(lang) {
    currentLang = lang;

    // Update document direction for RTL
    if (lang === 'ar') {
        document.documentElement.setAttribute('dir', 'rtl');
        document.documentElement.setAttribute('lang', 'ar');
    } else {
        document.documentElement.setAttribute('dir', 'ltr');
        document.documentElement.setAttribute('lang', 'en');
    }

    // Trigger UI update
    updateUILanguage();
}

// Update all UI text (called after language change)
function updateUILanguage() {
    // Update all elements with data-i18n attribute
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        el.textContent = t(key);
    });

    // Update placeholders
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
        const key = el.getAttribute('data-i18n-placeholder');
        el.placeholder = t(key);
    });
}
