# HTML/JS Frontend — Quick Start Guide

**New:** MagnaAI now has **two frontends** — Streamlit (Python) and HTML/JS (Web).

---

## ✨ **What's New?**

You now have a **lightweight, modern web interface** built with pure HTML/CSS/JavaScript that works alongside the existing Streamlit frontend.

### **Why Two Frontends?**

| Feature | Streamlit | HTML/JS |
|---------|-----------|---------|
| **Technology** | Python | Pure Web (HTML/CSS/JS) |
| **Deployment** | Needs Python runtime | Static files (any web server) |
| **Performance** | Slower (WebSocket) | Faster (REST API) |
| **UI Library** | Streamlit components | Custom modern design |
| **Best For** | Rapid prototyping, internal tools | Production, embedded, mobile |

---

## 🚀 **Quick Start**

### **1. Start the Backend**

```bash
python main.py
```

The FastAPI server will start on `http://localhost:8000`.

### **2. Access the Frontends**

#### **Option A: HTML Frontend (New!)**
Open your browser to:
```
http://localhost:8000/
```

Clean, modern interface — no Python needed!

#### **Option B: Streamlit Frontend (Existing)**
In a **second terminal**:
```bash
streamlit run frontend/app.py
```

Then open:
```
http://localhost:8501/
```

Python-based dashboard with more widgets.

---

## 📁 **File Structure**

```
lc_platform_v2/
├── static/                      # NEW: HTML Frontend
│   ├── index.html              # Main HTML page
│   ├── css/
│   │   └── styles.css          # Modern styling
│   └── js/
│       └── app.js              # Frontend logic
├── frontend/
│   └── app.py                  # Streamlit frontend (existing)
├── api/
│   └── main.py                 # FastAPI backend (updated)
└── ...
```

---

## 🎨 **HTML Frontend Features**

### **Current Features**
- ✅ **Drag & Drop PDF Upload**
- ✅ **AI Model Selection** (Gemini 2.5, GPT-4o)
- ✅ **Extraction Methods** (Vision, Text, OCR)
- ✅ **Live Extraction Results** with field grid
- ✅ **PDF Preview** (shows extracted text)
- ✅ **Raw Response Viewer** (JSON)
- ✅ **Clean, Modern Design** (responsive, mobile-friendly)
- ✅ **Loading States & Error Handling**

### **What It Does**
1. Upload a PDF (drag & drop or click)
2. Select model and extraction method
3. Click "Extract Information"
4. View results in 3 tabs:
   - **Extracted Fields** — Clean grid of all L/C fields
   - **PDF Preview** — Full PDF text
   - **Raw Response** — Complete API response

---

## 🔧 **How It Works**

### **Frontend → Backend Flow**

```
┌──────────────┐
│ Browser      │
│ (index.html) │
└──────┬───────┘
       │ 1. Upload PDF
       │ 2. Click Extract
       ▼
┌──────────────┐
│ JavaScript   │
│ (app.js)     │
└──────┬───────┘
       │ POST /extract
       │ {pdf_bytes_b64, method, ...}
       ▼
┌──────────────┐
│ FastAPI      │
│ (main.py)    │
└──────┬───────┘
       │ invoke()
       ▼
┌──────────────┐
│ LangGraph    │
│ (graphs.py)  │
└──────┬───────┘
       │ call_tool()
       ▼
┌──────────────┐
│ FastMCP      │
│ (server.py)  │
└──────┬───────┘
       │ extract_lc_document()
       ▼
┌──────────────┐
│ LLM (Gemini) │
└──────────────┘
```

All frontends use the **same backend** — no duplicate logic!

---

## 🆚 **Frontend Comparison**

### **When to Use HTML Frontend**

✅ **Production deployment**
✅ **Embedding in existing website**
✅ **Mobile access**
✅ **Faster page loads**
✅ **Custom branding** (easy CSS changes)
✅ **No Python runtime on client**

### **When to Use Streamlit Frontend**

✅ **Internal team tools**
✅ **Rapid prototyping**
✅ **Complex Python widgets** (charts, dataframes)
✅ **Multi-language support** (has i18n)
✅ **Verification panel** (SWIFT, ports, sanctions)
✅ **Validation reports**

---

## 🎯 **Next Steps**

### **Enhance HTML Frontend**

Want to add more features? Here's what you can add:

1. **Validation Tab** — Show cross-document validation results
2. **Verification Panel** — SWIFT, port, HS code verification
3. **Chat Interface** — Ask questions about the document
4. **Export Options** — Download JSON, PDF report
5. **Field Editing** — Edit extracted values inline
6. **Multi-Language** — UI in Arabic, Spanish, Italian
7. **Dark Mode** — Toggle theme

### **How to Customize**

#### Change Colors
Edit `static/css/styles.css`:
```css
:root {
    --primary: #2563eb;  /* Change to your brand color */
}
```

#### Add New Tab
1. Add button to `static/index.html`:
   ```html
   <button class="tab-btn" data-tab="mytab">My Tab</button>
   ```
2. Add content:
   ```html
   <div id="tab-mytab" class="tab-content">...</div>
   ```

#### Add API Endpoint
1. Add function in `static/js/app.js`:
   ```javascript
   async function validateDocument() {
       return apiPost('/validate', {...});
   }
   ```

---

## 🐛 **Troubleshooting**

### **"Cannot GET /" Error**

Check that:
1. Backend is running (`python main.py`)
2. `static/` folder exists with `index.html`
3. FastAPI logs show "Mounted static files"

### **Extraction Fails**

Check `.env` file has API keys:
```bash
GOOGLE_GEMINI_API_KEY=your_key_here
# or
OPENAI_API_KEY=your_key_here
```

### **CORS Errors**

FastAPI already has CORS enabled. If still blocked:
- Open browser DevTools → Console
- Check the actual error message
- Verify API_BASE in `app.js` matches your server URL

---

## 📚 **API Documentation**

Both frontends use the same REST API.

**Interactive Docs:**
```
http://localhost:8000/docs
```

**Key Endpoints:**
- `POST /extract` — Extract L/C fields from PDF
- `POST /validate` — Cross-validate documents
- `POST /verify/batch` — Verify multiple fields
- `POST /chat` — Chat about a document
- `GET /tools` — List all MCP tools

---

## 🚢 **Deployment**

### **Static HTML (Recommended)**

The HTML frontend is just 3 files. Deploy anywhere:

**Option 1: With FastAPI**
```bash
python main.py  # Serves HTML at http://localhost:8000/
```

**Option 2: Separate Static Server**
```bash
cd static
python -m http.server 8080
# Update API_BASE in app.js to point to FastAPI
```

**Option 3: CDN / S3**
- Upload `static/` to S3, Netlify, Vercel
- Update API_BASE to your FastAPI domain
- Enable CORS on FastAPI for your domain

### **Streamlit (For Internal Use)**

```bash
streamlit run frontend/app.py --server.port 8501
```

---

## 📝 **Summary**

- ✅ HTML frontend created (`static/`)
- ✅ FastAPI serves static files
- ✅ Both frontends share same backend
- ✅ No code duplication
- ✅ Choose the right tool for your use case

**Next:** Add validation, verification, and chat tabs to HTML frontend!
