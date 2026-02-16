# Database Lookup Feature — User Guide

**MagnaAI L/C Platform v2.0**
**Feature:** NAB_DEMO Database Integration with Customer Lookup & Data Comparison

---

## ✅ **What's Implemented**

### **1. Database Connection** ✅
- PostgreSQL connection to `NAB_DEMO` database via FastAPI + MCP
- Table: `cbl` (customer banking ledger)
- Connection details:
  - Host: `204.12.251.157:5432`
  - Database: `NAB_DEMO` (updated from lc_platform)
  - User: `postgres`
  - Architecture: **Async FastAPI endpoint** (not direct DB access from frontend)

### **2. Sidebar Lookup Panel** ✅
- **Location:** Streamlit sidebar (below API Debug section)
- **Input:** Customer Number or Account Number
- **Search fields:** `cst_id` or `current_account_number`
- **Button:** "🔎 Lookup" to query database
- **Status indicator:** Shows customer name, account, and status

### **3. Account Status Display** ✅
- **🟢 Active:** Green success message
- **🔴 Blocked:** Red error message with warning
- **🟡 Under Review:** Yellow warning message
- **ℹ️ Other:** Info message for any other status

### **4. Database Match Tab** ✅
- **New tab:** "🏦 Database Match"
- **Displays:**
  - Complete CBL record (all fields)
  - Account status with visual indicators
  - Data comparison between PDF and database
  - Discrepancy highlighting

### **5. Data Comparison Engine** ✅
- **Field mappings:**
  - `applicant_name` ↔ `customer_name`
  - `beneficiary_name` ↔ `beneficiary_name`
  - `amount` ↔ `lc_amount`
  - `currency` ↔ `lc_currency`
  - `lc_number` ↔ `lc_reference_number`
  - `applicant_account` ↔ `current_account_number`
  - `applicant_address` ↔ `customer_address`

- **Visual feedback:**
  - ✅ Green checkmark for matching fields
  - 🔴 Red warning for discrepancies
  - Side-by-side comparison (PDF vs Database)

---

## 📋 **How to Use**

### **Step 1: Start the Application**

```bash
# Terminal 1: Start FastAPI backend
python main.py

# Terminal 2: Start Streamlit frontend
streamlit run frontend/app.py
```

### **Step 2: Lookup a Customer**

1. **Open Streamlit** at `http://localhost:8501`
2. **Go to sidebar** → Find "🔍 User ID Lookup (NAB_DEMO)"
3. **Enter** a Customer Number or Account Number
   - Example: `12345` or `ACC-001`
4. **Click** "🔎 Lookup"
5. **View results:**
   - ✅ Success: Customer found
   - ⚠️ Warning: No match found
   - ❌ Error: Database connection issue

### **Step 3: View Database Record**

1. **Navigate** to the "🏦 Database Match" tab
2. **Review:**
   - Account status (blocked/active/under review)
   - Complete CBL record with all fields
   - Customer details

### **Step 4: Compare with PDF Data**

1. **Upload and extract** a Letter of Credit PDF
2. **Return** to "🏦 Database Match" tab
3. **View comparison section:**
   - Matching fields (green ✅)
   - Discrepancies (red 🔴) with side-by-side values
   - Field-by-field breakdown

---

## 🎨 **UI Features**

### **Sidebar Status Indicators**

```
✅ Status: active              → Green success box
⛔ Status: blocked             → Red error box
⚠️ Status: under review        → Yellow warning box
ℹ️ Status: [other]             → Blue info box
```

### **Comparison Display**

**Matches:**
```
✅ 3 field(s) match
  - Applicant Name: ABC Corporation
  - Currency: USD
  - L/C Number: LC123456
```

**Discrepancies:**
```
⚠️ 2 discrepancy(ies) found

🔴 Amount
  PDF Value: 100,000.00
  Database Value: 95,000.00

🔴 Beneficiary Name
  PDF Value: XYZ Trading Co.
  Database Value: XYZ Trading Company Ltd.
```

---

## 🔧 **Technical Details**

### **Architecture** (FastAPI + MCP Based)

**Frontend (Streamlit):**
```python
# Streamlit calls FastAPI endpoint (NOT direct DB access)
response = api_lookup_customer(lookup_value)
# api_lookup_customer → POST /lookup_customer
```

**Backend (FastAPI):**
```python
# api/main.py
@app.post("/lookup_customer")
async def lookup_customer(req: CustomerLookupRequest):
    result = await db_lookup_customer(req.lookup_value)
    return {"success": True, "data": result}
```

**Database Layer (utils/database.py):**
```python
# Async PostgreSQL via asyncpg
async def db_lookup_customer(lookup_value: str):
    pool = await get_nab_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, lookup_value)
        return dict(row) if row else None
```

### **Database Query**

```sql
SELECT * FROM cbl
WHERE cst_id = $1 OR current_account_number = $1
LIMIT 1
```

### **Connection Library**

- **asyncpg** (async PostgreSQL driver)
- Connection pooling for NAB_DEMO database
- Returns dictionary format from asyncpg.Record

### **Database URL**

```bash
# .env or config/settings.py
DATABASE_URL=postgresql://postgres:nasser123@204.12.251.157:5432/NAB_DEMO
DATABASE_URL_ASYNC=postgresql+asyncpg://postgres:nasser123@204.12.251.157:5432/NAB_DEMO
```

### **Session State Variables**

```python
st.session_state["cbl_data"]      # Database record (dict or None)
st.session_state["lookup_value"]  # Last searched value
```

### **Error Handling**

- Database connection errors caught at backend
- API errors displayed in frontend
- No matching customer → Warning message
- Invalid input → Validation prompt

---

## 🧪 **Testing Checklist**

### **Database Connectivity**
- [ ] Database connection successful
- [ ] Query returns results for valid customer
- [ ] Query returns None for invalid customer
- [ ] Error handling for connection failures

### **Sidebar Lookup**
- [ ] Input field accepts text
- [ ] Lookup button triggers query
- [ ] Success message shows customer name
- [ ] Warning shows for no match
- [ ] Account status displays correctly

### **Database Match Tab**
- [ ] Tab appears in navigation
- [ ] Instructions show when no data
- [ ] Complete CBL record displays all fields
- [ ] Account status indicator works (active/blocked/review)

### **Data Comparison**
- [ ] Matching fields show in green
- [ ] Discrepancies highlight in red
- [ ] Side-by-side comparison displays correctly
- [ ] Field mappings work as expected

---

## 🐛 **Troubleshooting**

### **Database Connection Error**

**Error:** `Database error: connection refused`

**Fix:**
1. Check database server is running
2. Verify IP address: `204.12.251.157`
3. Confirm port: `5432`
4. Test credentials: `postgres:nasser123`

### **No Customer Found**

**Error:** `No matching customer found`

**Fix:**
1. Verify customer number exists in `cbl` table
2. Check spelling/formatting
3. Try both `cst_id` and `current_account_number`

### **Import Error: asyncpg**

**Error:** `ModuleNotFoundError: No module named 'asyncpg'`

**Fix:**
```bash
pip install asyncpg
```

### **FastAPI Endpoint Not Found**

**Error:** `404 Not Found: /lookup_customer`

**Fix:**
1. Ensure FastAPI server is running: `python main.py`
2. Check API_BASE in Streamlit sidebar (should be `http://localhost:8000`)
3. Verify endpoint exists in `api/main.py`

### **Discrepancies Not Showing**

**Fix:**
1. Ensure document has been extracted first
2. Check field mappings in code
3. Verify field names match schema

---

## 📊 **Field Mappings Reference**

| PDF Field            | CBL Field                  | Description                |
|---------------------|---------------------------|---------------------------|
| applicant_name      | customer_name             | Customer/Applicant name   |
| beneficiary_name    | beneficiary_name          | Beneficiary name          |
| amount              | lc_amount                 | L/C amount                |
| currency            | lc_currency               | L/C currency              |
| lc_number           | lc_reference_number       | L/C reference number      |
| applicant_account   | current_account_number    | Account number            |
| applicant_address   | customer_address          | Customer address          |

---

## 🎯 **Use Cases**

### **1. Customer Verification**
- Lookup customer before processing L/C
- Verify account is active (not blocked)
- Check customer details match application

### **2. Data Validation**
- Compare extracted PDF data with database records
- Identify discrepancies before approval
- Flag accounts under review

### **3. Compliance Checking**
- Ensure L/C applicant matches account holder
- Verify amounts align with account limits
- Check beneficiary against approved parties

### **4. Audit Trail**
- Document comparison results
- Track discrepancies for investigation
- Maintain data integrity

---

## 🚀 **Future Enhancements**

### **Planned Features**
- [ ] Support multiple customer records (pagination)
- [ ] Edit database values directly from UI
- [ ] Save comparison results to database
- [ ] Export discrepancy report as PDF
- [ ] Auto-lookup when L/C number matches
- [ ] Sanctions screening integration
- [ ] Historical comparison (show changes over time)

### **Advanced**
- [ ] Real-time database sync
- [ ] Multi-table joins (cbl + transactions + limits)
- [ ] Machine learning discrepancy detection
- [ ] Automated approval workflow

---

## ✅ **Summary**

You now have a **fully integrated database lookup system** with:

- ✅ **Customer lookup** in sidebar by ID or account number
- ✅ **Account status display** (blocked/active/review)
- ✅ **Complete CBL record** display in dedicated tab
- ✅ **Data comparison** between PDF and database
- ✅ **Discrepancy highlighting** with side-by-side view
- ✅ **Visual indicators** for status and matches

**Ready to use!** Just lookup a customer and compare with extracted L/C data. 🎉

---

## 📝 **Example Workflow**

```
1. User uploads L/C PDF → Extract data
   → Extracted: applicant_name = "ABC Corporation"
   → Extracted: amount = "100,000.00"

2. User enters customer number "12345" in sidebar → Click Lookup
   → Database found: customer_name = "ABC Corporation"
   → Database found: lc_amount = "95,000.00"
   → Status: ✅ Active

3. Navigate to "🏦 Database Match" tab
   → View complete CBL record
   → Comparison shows:
      ✅ Applicant Name: MATCH
      🔴 Amount: DISCREPANCY (100,000 vs 95,000)

4. Review discrepancy → Investigate → Update or reject
```

---

**Questions?** Check the code:
- **FastAPI Endpoint:** [api/main.py](api/main.py) lines 103-106 (CustomerLookupRequest model) and lines 248-258 (/lookup_customer endpoint)
- **Database Logic:** [utils/database.py](utils/database.py) lines 382-460 (NAB_DEMO async pool and lookup function)
- **Streamlit API Call:** [frontend/app.py](frontend/app.py) lines 111-113 (api_lookup_customer)
- **Streamlit Sidebar:** [frontend/app.py](frontend/app.py) lines 673-710 (User ID Lookup section)
- **Database Match Tab:** [frontend/app.py](frontend/app.py) lines 855-973 (tab_db content)
