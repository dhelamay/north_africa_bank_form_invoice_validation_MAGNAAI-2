"""
MagnaAI L/C Document Processing Dashboard — v2.
Calls FastAPI backend over HTTP. No direct agent/MCP/orchestrator imports.

Features preserved from v1:
  - Form fields with confidence bars + check signs
  - Form Review tab with filters + metrics
  - NAB-style API Verification Panel (Field|Value|Type|Status|Conf|Verify|Accept)
  - Verify All with progress bar + per-field verify buttons
  - Chat, Validation, Preview, Summary tabs

Start:
  Terminal 1:  python main.py                  # FastAPI on :8000
  Terminal 2:  streamlit run frontend/app.py   # Streamlit on :8501
"""
import os, sys, json, base64
import concurrent.futures
import streamlit as st
import httpx
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config.settings import get_settings, GEMINI_MODELS
from schemas.lc_fields import SECTIONS
from locales.i18n import t, is_rtl, get_available_languages

settings = get_settings()

# ═══════════════════════════════════════════════════════════════
#  API CLIENT — all calls to FastAPI backend go through here
# ═══════════════════════════════════════════════════════════════

API_BASE = os.getenv("API_URL", f"http://localhost:{settings.app_port}")
TIMEOUT = 120.0  # LLM calls can be slow


def api_post(path: str, payload: dict) -> dict:
    """POST to FastAPI backend. Returns JSON response or an {'error': ...} dict (with debug)."""
    url = f"{API_BASE}{path}"
    try:
        r = httpx.post(
            url,
            json=payload,
            timeout=TIMEOUT,
            follow_redirects=True,
            headers={"Accept": "application/json"},
        )
        if r.status_code >= 400:
            raw = (r.text or "")[:2000]
            try:
                j = r.json()
            except Exception:
                j = None
            return {
                "error": f"HTTP {r.status_code}",
                "detail": (j.get("detail") if isinstance(j, dict) else None) or j or raw,
                "status_code": r.status_code,
                "raw": raw,
                "url": url,
                "payload": payload,
            }
        try:
            return r.json()
        except Exception as e:
            raw = (r.text or "")[:2000]
            return {"error": f"Invalid JSON from API: {e}", "status_code": r.status_code, "raw": raw, "url": url}
    except Exception as e:
        return {"error": f"Request failed: {e}", "url": url, "payload": payload}


def api_get(path: str) -> dict:
    """GET request to FastAPI backend with error handling."""
    url = f"{API_BASE}{path}"
    try:
        r = httpx.get(url, timeout=10, follow_redirects=True, headers={"Accept": "application/json"})
        if r.status_code >= 400:
            return {"error": f"HTTP {r.status_code}", "raw": (r.text or "")[:2000], "url": url}
        return r.json()
    except Exception as e:
        return {"error": f"Request failed: {e}", "url": url}


def api_extract(pdf_bytes: bytes, method="vision", provider="gemini", model="gemini-2.5-flash", lang="en"):
    """Extract L/C fields from PDF via FastAPI."""
    return api_post("/extract", {
        "pdf_bytes_b64": base64.b64encode(pdf_bytes).decode(),
        "method": method, "llm_provider": provider,
        "model_name": model, "language": lang,
    })


def api_validate(documents: dict, lang="en"):
    return api_post("/validate", {"documents": documents, "language": lang})


def api_verify(tool_name: str, args: dict):
    return api_post("/verify", {"tool_name": tool_name, "args": args})


def api_verify_batch(fields: list):
    return api_post("/verify/batch", {"fields": fields})


def api_chat(message: str, extracted_data=None, pdf_text="", history=None, lang="en"):
    return api_post("/chat", {
        "message": message, "extracted_data": extracted_data or {},
        "pdf_text": pdf_text, "history": history or [], "language": lang,
    })


def api_lookup_customer(lookup_value: str):
    """Lookup customer in NAB_DEMO database via FastAPI."""
    return api_post("/lookup_customer", {"lookup_value": lookup_value})


# ═══════════════════════════════════════════════════════════════
#  FIELD → VERIFICATION TOOL MAPPING
# ═══════════════════════════════════════════════════════════════

FIELD_API_MAPPING = {
    "beneficiary_bank_swift": "verify_swift_code",
    "correspondent_bank_swift": "verify_swift_code",
    "advising_bank_swift": "verify_swift_code",
    "available_at_correspondent": "verify_swift_code",
    "port_loading": "verify_port",
    "port_destination": "verify_port",
    "port_of_loading": "verify_port",
    "port_of_destination": "verify_port",
    "port_of_discharge": "verify_port",
    "named_place_port": "verify_port",
    "place_of_receipt": "verify_port",
    "hs_code": "verify_hs_code",
    "goods_hs_code": "verify_hs_code",
    "beneficiary_name": "verify_company",
    "applicant_name": "check_sanctions",
    "beneficiary_bank": "verify_bank_by_name",
    "price_delivery_term": "_incoterm",
    "incoterm": "_incoterm",
    "delivery_term": "_incoterm",
}

VERIFY_PATTERNS = ["swift","bic","port","loading","destination","hs_code",
                   "beneficiary_name","beneficiary_bank","applicant_name","incoterm"]


def _get_verifiable_fields():
    fields, seen = [], set()
    for sec in SECTIONS:
        for f in sec.fields:
            if f.type in ("file","signature","stamp","checkbox") or f.key in seen:
                continue
            if f.key in FIELD_API_MAPPING:
                fields.append((f.key, f, sec, FIELD_API_MAPPING[f.key]))
                seen.add(f.key); continue
            text = f"{f.key} {f.en} {f.ar}".lower()
            for p in VERIFY_PATTERNS:
                if p in text:
                    vtype = _infer_verify_tool(f.key)
                    if vtype:
                        fields.append((f.key, f, sec, vtype))
                        seen.add(f.key)
                    break
    return fields


def _infer_verify_tool(k):
    k = k.lower()
    if any(w in k for w in ["swift","bic"]): return "verify_swift_code"
    if any(w in k for w in ["port","loading","destination","discharge"]): return "verify_port"
    if "hs" in k and "code" in k: return "verify_hs_code"
    if "beneficiary_name" in k: return "verify_company"
    if "applicant_name" in k: return "check_sanctions"
    if "beneficiary_bank" in k and "swift" not in k: return "verify_bank_by_name"
    if "incoterm" in k or "delivery_term" in k: return "_incoterm"
    return None


def _build_verify_args(tool_name, value):
    """Build the correct args dict for each verification tool."""
    if tool_name == "verify_swift_code": return {"code": value}
    if tool_name == "verify_port": return {"port_name": value}
    if tool_name == "verify_hs_code": return {"code": value}
    if tool_name == "check_sanctions": return {"party_name": value}
    if tool_name == "verify_company": return {"company_name": value}
    if tool_name == "verify_bank_by_name": return {"bank_name": value}
    if tool_name == "deep_research": return {"query": value}
    return {"field_value": value}


# ═══════════════════════════════════════════════════════════════
#  VERIFICATION HELPERS
# ═══════════════════════════════════════════════════════════════

def _verify_single_field(field_key, value, tool_name):
    """Verify one field (uses /verify/batch for consistency and better throughput)."""
    if tool_name == "_incoterm":
        valid = ["FOB","CFR","CIF","CPT","CIP","EXW","FCA","FAS","DAP","DPU","DDP","Ex Works"]
        v = value or ""
        ok = any(t.lower() in v.lower() for t in valid)
        return {
            "status": "verified" if ok else "warn",
            "message": f"Incoterm '{v}' {'recognized' if ok else 'not recognized'}",
            "confidence": 0.9 if ok else 0.3,
            "source": "format_validation",
            "details": {},
        }

    args = _build_verify_args(tool_name, value)
    batch = api_verify_batch([{"tool_name": tool_name, "args": args}])

    # Transport/debug error from api_post
    if isinstance(batch, dict) and batch.get("error"):
        return {
            "status": "error",
            "message": str(batch.get("detail") or batch.get("error") or "API request failed"),
            "confidence": 0.0,
            "source": "api_error",
            "details": {k: batch.get(k) for k in ("status_code","raw","url","payload","detail") if k in batch},
        }

    results = (batch or {}).get("results") or []
    errors = (batch or {}).get("errors") or []

    if (not results) and errors:
        err0 = errors[0] if isinstance(errors[0], dict) else {"error": str(errors[0])}
        return {
            "status": "error",
            "message": str(err0.get("error") or "Verification failed"),
            "confidence": 0.0,
            "source": "api_error",
            "details": err0,
        }

    r = results[0] if results else {}

    # Normalize to UI panel schema
    if isinstance(r, dict) and "verified" in r:
        return {
            "status": "verified" if r.get("verified") else "warn",
            "message": str(r.get("message") or ""),
            "confidence": float(r.get("confidence") or 0.0),
            "source": r.get("source") or "",
            "details": r.get("details") or {},
        }

    if isinstance(r, dict) and "status" in r:
        return {
            "status": r.get("status") or "error",
            "message": str(r.get("message") or ""),
            "confidence": float(r.get("confidence") or 0.0),
            "source": r.get("source") or "",
            "details": r.get("details") or {},
        }

    return {
        "status": "error",
        "message": "Unexpected verification response",
        "confidence": 0.0,
        "source": "api_error",
        "details": {"raw": r, "tool_name": tool_name, "args": args},
    }



def _verify_all_async(fields_to_verify):
    """Verify all fields using a single /verify/batch call (faster + consistent)."""
    batch_fields = []
    key_order = []
    out = {}

    # Incoterms locally
    for fk, (val, tool_name) in fields_to_verify.items():
        if tool_name == "_incoterm":
            out[fk] = _verify_single_field(fk, val, tool_name)
        else:
            batch_fields.append({"tool_name": tool_name, "args": _build_verify_args(tool_name, val)})
            key_order.append(fk)

    if not batch_fields:
        return out

    batch = api_verify_batch(batch_fields)

    if isinstance(batch, dict) and batch.get("error"):
        msg = str(batch.get("detail") or batch.get("error") or "API request failed")
        for fk in key_order:
            out[fk] = {"status": "error", "message": msg, "confidence": 0.0, "source": "api_error", "details": batch}
        return out

    results = (batch or {}).get("results") or []
    errors = (batch or {}).get("errors") or []

    for i, fk in enumerate(key_order):
        r = results[i] if i < len(results) else None
        if not r:
            err = errors[i] if i < len(errors) else {"error": "Missing result"}
            out[fk] = {"status": "error", "message": str(err.get("error", err)), "confidence": 0.0, "source": "api_error", "details": err}
            continue

        if "verified" in r:
            out[fk] = {
                "status": "verified" if r.get("verified") else "warn",
                "message": str(r.get("message") or ""),
                "confidence": float(r.get("confidence") or 0.0),
                "source": r.get("source") or "",
                "details": r.get("details") or {},
            }
        else:
            out[fk] = {
                "status": r.get("status") or "error",
                "message": str(r.get("message") or ""),
                "confidence": float(r.get("confidence") or 0.0),
                "source": r.get("source") or "",
                "details": r.get("details") or {},
            }

    return out



# ═══════════════════════════════════════════════════════════════
#  UI HELPERS
# ═══════════════════════════════════════════════════════════════

def safe_date(value):
    if not value or not isinstance(value, str): return None
    for fmt in ("%d/%m/%Y","%m/%d/%Y","%Y-%m-%d","%d-%m-%Y","%B %d, %Y"):
        try: return datetime.strptime(value.strip(), fmt).date()
        except: continue
    return None

def _confidence_badge(conf):
    if conf is None: return "⚪","gray"
    if conf >= 0.9: return "✅","green"
    if conf >= 0.7: return "🟢","green"
    if conf >= 0.5: return "🟡","orange"
    if conf >= 0.3: return "🟠","orange"
    return "🔴","red"

def _source_badge(source):
    if not source: return ""
    s = str(source).lower()
    badges = {"db":"🔒 DB","gemini":"🤖 Gemini","openai":"🤖 GPT","gpt":"🤖 GPT",
              "vision":"👁️ Vision","ocr":"📸 OCR","perplexity":"🔍 Perplexity",
              "exa":"🌐 Exa","api_ninjas":"🏦 API Ninjas","unlocode":"🚢 UNLOCODE",
              "geoapify":"🗺️ Geoapify","user":"✏️ User","format":"📐 Format"}
    for k,v in badges.items():
        if k in s: return v
    return f"📋 {source[:15]}"

def _chip_for_status(status):
    status = (status or "").lower()
    if status in ("pass","verified","ok","valid","true"): return "✅"
    if status in ("warn","review","needs_verify","needs_review"): return "⚠️"
    if status in ("fail","failed","invalid","blocked","false"): return "❌"
    if status in ("error","api_error","exception"): return "🛑"
    if status in ("low_confidence",): return "🔶"
    return "⚪"

def _verify_type_label(tool_name):
    return {"verify_swift_code":"🏦 SWIFT","verify_port":"🚢 Port",
            "verify_hs_code":"📦 HS Code","verify_company":"🏢 Company",
            "check_sanctions":"🛡️ Sanctions","verify_bank_by_name":"🏦 Bank",
            "_incoterm":"📋 Incoterm","deep_research":"🔬 Research",
    }.get(tool_name, f"🔍 {tool_name}")

def _check_sign(info, field_key):
    if not info: return ""
    val = info.get(field_key)
    meta = st.session_state.get("field_meta",{}).get(field_key,{})
    conf = meta.get("confidence")
    verified = meta.get("verified")
    if verified is True: return " ✅"
    if verified is False: return " ❌"
    if val is None or val == "": return " ⬜"
    if conf is not None:
        emoji, _ = _confidence_badge(conf)
        return f" {emoji}"
    return " ✔️"


# ═══════════════════════════════════════════════════════════════
#  FORM RENDERING
# ═══════════════════════════════════════════════════════════════

def render_section_form(section, info, lang):
    st.markdown(f"**{section.label(lang)}**")
    if lang != "ar": st.caption(section.ar)
    for f in section.fields:
        if f.type in ("file","signature","stamp"): continue
        wk = f"form_{section.key}_{f.key}"
        val = info.get(f.key)
        label = f"{f.label(lang)}  |  {f.ar}" if lang != "ar" else f.ar
        meta = st.session_state.get("field_meta",{}).get(f.key,{})
        conf = meta.get("confidence")
        source = meta.get("source","")
        check = _check_sign(info, f.key)
        conf_str = f" ({conf:.0%})" if conf is not None else ""
        src_str = f" {_source_badge(source)}" if source else ""
        display_label = f"{label}{check}{conf_str}{src_str}"
        if f.required and (not val or val == ""):
            display_label = f"🔴 {display_label}"
        if f.type == "text":
            info[f.key] = st.text_input(display_label, str(val) if val else "", key=wk)
        elif f.type == "textarea":
            info[f.key] = st.text_area(display_label, str(val) if val else "", height=80, key=wk)
        elif f.type == "number":
            info[f.key] = st.text_input(display_label, str(val) if val else "", key=wk)
        elif f.type == "date":
            d = safe_date(val) if isinstance(val, str) else None
            if d:
                new_d = st.date_input(display_label, d, key=wk)
                info[f.key] = new_d.strftime("%d/%m/%Y")
            else:
                info[f.key] = st.text_input(display_label + " (DD/MM/YYYY)", str(val) if val else "", key=wk)
        elif f.type == "select":
            opts = [""] + f.options
            cur = str(val) if val else ""
            idx = opts.index(cur) if cur in opts else 0
            info[f.key] = st.selectbox(display_label, opts, index=idx, key=wk)
        elif f.type == "checkbox":
            checked = str(val).lower() in ("true","yes","1") if val else False
            info[f.key] = st.checkbox(display_label, value=checked, key=wk)
    return info


# ═══════════════════════════════════════════════════════════════
#  FORM REVIEW PANEL
# ═══════════════════════════════════════════════════════════════

def render_form_review(info, lang):
    st.subheader("📋 Form Review — All Fields")
    meta_store = st.session_state.get("field_meta",{})
    total = filled = high_conf = low_conf = missing_required = 0
    rows = []
    for sec in SECTIONS:
        for f in sec.fields:
            if f.type in ("file","signature","stamp"): continue
            total += 1
            val = info.get(f.key)
            meta = meta_store.get(f.key,{})
            conf = meta.get("confidence")
            source = meta.get("source","")
            verified = meta.get("verified")
            has_value = val is not None and str(val).strip() != "" and val is not False
            if has_value: filled += 1
            if conf is not None and conf >= 0.7: high_conf += 1
            if conf is not None and conf < 0.5: low_conf += 1
            if f.required and not has_value: missing_required += 1
            if verified is True: status = "✅ Verified"
            elif verified is False: status = "❌ Failed"
            elif has_value and conf is not None and conf >= 0.7: status = "🟢 Good"
            elif has_value and conf is not None and conf >= 0.5: status = "🟡 Review"
            elif has_value and conf is not None and conf < 0.5: status = "🔴 Low Conf"
            elif has_value: status = "✔️ Filled"
            elif f.required: status = "⭕ MISSING"
            else: status = "⬜ Empty"
            rows.append({"Section":sec.label(lang),"Field":f.label(lang),"Field ID":f.key,
                "Value":str(val)[:60] if has_value else "—",
                "Confidence":f"{conf:.0%}" if conf is not None else "—",
                "Source":_source_badge(source) if source else "—",
                "Status":status,"Required":"⭐" if f.required else ""})

    c1,c2,c3,c4,c5 = st.columns(5)
    with c1: st.metric("Total Fields", total)
    with c2: st.metric("Filled", filled, f"{filled/total:.0%}" if total else "")
    with c3: st.metric("High Confidence", high_conf)
    with c4: st.metric("Low Confidence", low_conf)
    with c5: st.metric("Missing Required", missing_required, delta_color="inverse")

    filter_opt = st.radio("Filter",["All","Filled Only","Missing Only","Low Confidence","Required Missing"],
                          horizontal=True, key="review_filter")
    if filter_opt == "Filled Only": rows = [r for r in rows if r["Value"] != "—"]
    elif filter_opt == "Missing Only": rows = [r for r in rows if r["Value"] == "—"]
    elif filter_opt == "Low Confidence": rows = [r for r in rows if "🔴" in r["Status"] or "🟡" in r["Status"]]
    elif filter_opt == "Required Missing": rows = [r for r in rows if r["Status"] == "⭕ MISSING"]

    if rows:
        import pandas as pd
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No fields match the selected filter.")

    st.divider()
    if st.button("📥 Export Review as JSON", key="export_review"):
        export_data = {}
        for sec in SECTIONS:
            for f in sec.fields:
                meta = meta_store.get(f.key,{})
                export_data[f.key] = {"value":info.get(f.key),"confidence":meta.get("confidence"),
                    "source":meta.get("source"),"verified":meta.get("verified"),
                    "required":f.required,"section":sec.en}
        st.download_button("⬇️ Download", json.dumps(export_data,indent=2,ensure_ascii=False,default=str),
                           file_name="form_review.json", mime="application/json")


# ═══════════════════════════════════════════════════════════════
#  VERIFICATION RESULT DISPLAY
# ═══════════════════════════════════════════════════════════════

def _show_result_inline(r_dict):
    d = r_dict.get("details",{})
    msg = r_dict.get("message","")
    if msg:
        status = r_dict.get("status","")
        if status in ("verified","pass","ok"): st.success(f"✅ {msg[:300]}")
        elif status in ("error","fail"): st.error(f"❌ {msg[:300]}")
        else: st.warning(f"⚠️ {msg[:300]}")
    if d.get("google_maps"):
        st.markdown(f"🗺️ [Open in Google Maps]({d['google_maps']})")
    if d.get("matches"):
        for m in d["matches"][:3]:
            gm = m.get("google_maps","")
            label = f"{m.get('name','')} ({m.get('country','')})"
            if gm: st.markdown(f"  📍 [{label}]({gm})")
    urls = d.get("source_urls",[])
    if urls:
        with st.expander(f"🔗 Sources ({len(urls)})"):
            for u in urls[:8]:
                st.markdown(f"- [{u}]({u})" if str(u).startswith("http") else f"- {u}")
    if d.get("lookup_urls"):
        with st.expander("🔍 Lookup URLs"):
            for k,v in d["lookup_urls"].items(): st.markdown(f"- [{k}]({v})")
    if d.get("tracking_urls"):
        with st.expander("🚢 Tracking Links"):
            for k,v in d["tracking_urls"].items(): st.markdown(f"- [{k}]({v})")
    if d.get("perplexity_research") or d.get("research"):
        with st.expander("📝 Research Details"):
            st.write(d.get("perplexity_research") or d.get("research"))
    if d.get("exa_results"):
        with st.expander(f"🌐 Web Results ({len(d['exa_results'])})"):
            for er in d["exa_results"]: st.markdown(f"- [{er.get('title','')}]({er.get('url','')})")
    if d.get("branches"):
        with st.expander(f"🏦 Bank Branches ({len(d['branches'])})"):
            for b in d["branches"][:10]:
                line = f"**{b.get('swift','')}** — {b.get('name','')} ({b.get('city','')}, {b.get('country','')})"
                gm = b.get("google_maps","")
                if gm: line += f"  [🗺️ Map]({gm})"
                st.markdown(line)


# ═══════════════════════════════════════════════════════════════
#  NAB-STYLE VERIFICATION PANEL
# ═══════════════════════════════════════════════════════════════

def render_verification_panel(info):
    with st.expander("🔎 API Verification Panel", expanded=True):
        ctrl1,ctrl2,ctrl3 = st.columns([2,2,1])
        with ctrl1: show_raw = st.checkbox("Show raw API responses", value=False, key="show_raw_api")
        with ctrl2: st.checkbox("Auto-verify on extraction", value=False, key="auto_verify_chk")
        with ctrl3:
            if st.button("🔄 Reset All", key="reset_all_verify"):
                st.session_state["verification"] = {}
                st.session_state["accepted"] = {}
                st.rerun()

        verifiable = _get_verifiable_fields()
        if not verifiable:
            st.info("No verifiable fields detected."); return

        fields_with_values = []
        for (fk,fdef,sec,tool_name) in verifiable:
            val = info.get(fk)
            if val and str(val).strip():
                fields_with_values.append((fk,fdef,sec,tool_name,str(val).strip()))

        if not fields_with_values:
            st.info("No field values to verify. Extract a document first."); return

        # Verify All
        if st.button("⚡ Verify All Fields", key="verify_all_btn"):
            to_verify = {fk:(val,tn) for (fk,fdef,sec,tn,val) in fields_with_values}
            progress_bar = st.progress(0.0)
            st.info(f"Verifying {len(to_verify)} fields in parallel...")
            results = _verify_all_async(to_verify)
            for fk, result in results.items():
                st.session_state["verification"][fk] = result
            progress_bar.progress(1.0)
            st.success(f"✅ Verification complete! {len(results)} fields checked.")
            st.rerun()

        st.markdown("---")
        headers = st.columns([2.5,3,1.2,1.5,1,0.8,0.8])
        headers[0].markdown("**Field**"); headers[1].markdown("**Value**")
        headers[2].markdown("**Type**"); headers[3].markdown("**Status**")
        headers[4].markdown("**Conf.**"); headers[5].markdown("**Verify**")
        headers[6].markdown("**Accept**")
        st.markdown("---")

        all_accepted = True
        for (fk,fdef,sec,tool_name,val) in fields_with_values:
            vres = st.session_state.get("verification",{}).get(fk) or {}
            status = (vres.get("status") or "not_checked").lower()
            conf = vres.get("confidence")
            accepted = bool(st.session_state.get("accepted",{}).get(fk))
            icon = _chip_for_status(status)

            cols = st.columns([2.5,3,1.2,1.5,1,0.8,0.8])
            with cols[0]: st.write(f"**{fdef.en}**"); st.caption(sec.en)
            with cols[1]: st.write(val[:45]+"…" if len(val)>45 else val)
            with cols[2]: st.write(_verify_type_label(tool_name))
            with cols[3]:
                sl = status.upper() if status != "not_checked" else "NOT CHECKED"
                st.write(f"{icon} {sl}")
            with cols[4]:
                if conf is not None:
                    badge,_ = _confidence_badge(conf)
                    st.write(f"{badge} {conf:.0%}")
                else: st.write("—")
            with cols[5]:
                if st.button("🔍",key=f"vfy_{fk}",help=f"Verify {fdef.en}"):
                    with st.spinner(f"Verifying {fdef.en}..."):
                        result = _verify_single_field(fk,val,tool_name)
                    st.session_state["verification"][fk] = result
                    st.rerun()
            with cols[6]:
                if accepted: st.write("✅")
                else:
                    can_accept = status in ("verified","pass","ok","valid","warn")
                    if st.button("OK",key=f"ok_{fk}",disabled=not can_accept):
                        st.session_state["accepted"][fk] = True
                        st.rerun()

            if vres:
                with st.expander(f"📋 Details: {fdef.en}", expanded=False):
                    _show_result_inline(vres)
                    if show_raw: st.markdown("**Raw API Response:**"); st.json(vres)

            if not accepted: all_accepted = False

        # Footer
        st.markdown("---")
        sc1,sc2,sc3 = st.columns(3)
        with sc1: st.metric("Total Verifiable", len(fields_with_values))
        with sc2:
            verified_n = sum(1 for (fk,_,_,_,_) in fields_with_values
                if (st.session_state.get("verification",{}).get(fk) or {}).get("status","").lower() in ("verified","pass","ok"))
            st.metric("Verified", verified_n)
        with sc3:
            accepted_n = sum(1 for (fk,_,_,_,_) in fields_with_values
                if st.session_state.get("accepted",{}).get(fk))
            st.metric("Accepted", accepted_n)

        if all_accepted and fields_with_values:
            st.success("✅ All fields verified and accepted!")
        else:
            pending = sum(1 for (fk,_,_,_,_) in fields_with_values
                if not st.session_state.get("accepted",{}).get(fk))
            st.warning(f"⚠️ {pending} field(s) pending verification/acceptance.")

    # Deep Research
    st.divider()
    st.markdown("**🔬 Custom Deep Research**")
    research_query = st.text_input("Research any entity, claim, or question:", key="deep_research_q")
    if st.button("Run Deep Research", key="v_deep") and research_query:
        with st.spinner("Researching with Perplexity sonar-pro..."):
            r = api_verify("deep_research", {"query": research_query})
        _show_result_inline({"status":"verified" if r.get("verified") else "warn",
            "message":r.get("message",""),"confidence":r.get("confidence",0),
            "source":r.get("source",""),"details":r.get("details",{})})


# ═══════════════════════════════════════════════════════════════
#  PAGE CONFIG & STATE
# ═══════════════════════════════════════════════════════════════

st.set_page_config(page_title="MagnaAI — L/C Processing", layout="wide", page_icon="🏦")

# ── quick API debug (helps catch wrong API_URL/port) ──
with st.sidebar:
    st.markdown('### API Debug')
    st.write('API_BASE:', API_BASE)
    st.write('Health:', api_get('/health'))

    st.divider()
    st.markdown('### 🔍 User ID Lookup (NAB_DEMO)')
    lookup_input = st.text_input("Enter Customer No or Account No",
                                  value=st.session_state.get("lookup_value", ""),
                                  placeholder="e.g., 12345 or ACC-001",
                                  help="Searches cbl table by cst_id or current_account_number")

    if st.button("🔎 Lookup", use_container_width=True, key="lookup_btn"):
        if lookup_input and lookup_input.strip():
            with st.spinner("Querying NAB_DEMO database..."):
                response = api_lookup_customer(lookup_input)
            st.session_state["lookup_value"] = lookup_input

            # Handle API response
            if response.get("error"):
                st.error(f"API error: {response.get('detail') or response.get('error')}")
                st.session_state["cbl_data"] = None
            elif response.get("success"):
                st.session_state["cbl_data"] = response.get("data")
                if response.get("data"):
                    cust_name = response['data'].get('customer_name1') or response['data'].get('entity_name', 'N/A')
                    st.success(f"✅ Found customer: {cust_name}")
                else:
                    st.warning("No matching customer found.")
            else:
                st.warning("No matching customer found.")
                st.session_state["cbl_data"] = None
        else:
            st.warning("Please enter a customer number or account number.")

    if st.session_state.get("cbl_data") and not st.session_state["cbl_data"].get("error"):
        cbl = st.session_state["cbl_data"]
        st.caption(f"**Customer:** {cbl.get('customer_name1') or cbl.get('entity_name', 'N/A')}")
        st.caption(f"**Account:** {cbl.get('account_number') or cbl.get('current_account_number', 'N/A')}")

        # Account status indicator
        status = (cbl.get("account_status") or "").lower()
        if "block" in status:
            st.error(f"⛔ Status: {cbl.get('account_status', 'N/A')}")
        elif "active" in status:
            st.success(f"✅ Status: {cbl.get('account_status', 'N/A')}")
        elif "review" in status or "under" in status:
            st.warning(f"⚠️ Status: {cbl.get('account_status', 'N/A')}")
        else:
            st.info(f"Status: {cbl.get('account_status') or 'N/A'}")


defaults = {"extracted_info":{},"raw_extracted_text":"","pdf_text":"","pdf_bytes":None,
            "messages":[],"extraction_done":False,"validation_result":None,
            "language":settings.app_language,"field_meta":{},"verification":{},"accepted":{},
            "cbl_data":None,"lookup_value":""}
for k,v in defaults.items():
    if k not in st.session_state: st.session_state[k] = v

lang = st.session_state["language"]
if is_rtl(lang):
    st.markdown('<style>body{direction:rtl;text-align:right}</style>', unsafe_allow_html=True)

# Check API connectivity
health = api_get("/health")
if "error" in health:
    st.error(f"⚠️ Cannot reach FastAPI backend at {API_BASE} — Start it with: `python main.py`")
    st.stop()

st.title(f"🏦 MagnaAI — {t('app_title', lang)}")


# ═══════════════════════════════════════════════════════════════
#  SIDEBAR
# ═══════════════════════════════════════════════════════════════

with st.sidebar:
    languages = get_available_languages()
    lang_labels = [f"{l['native']} ({l['label']})" for l in languages]
    lang_codes = [l["code"] for l in languages]
    sel_idx = lang_codes.index(lang) if lang in lang_codes else 0
    new_lang = lang_codes[st.selectbox("🌐 Language", range(len(lang_labels)), index=sel_idx,
                                        format_func=lambda i: lang_labels[i])]
    if new_lang != lang:
        st.session_state["language"] = new_lang; st.rerun()

    st.divider()
    st.header(f"① {t('upload_pdf', lang)}")
    uploaded_file = st.file_uploader(t("upload_pdf", lang), type=["pdf"], key="pdf_uploader")

    if uploaded_file:
        file_id = f"{uploaded_file.name}_{uploaded_file.size}"
        if st.session_state.get("_file_id") != file_id:
            uploaded_file.seek(0)
            st.session_state["pdf_bytes"] = uploaded_file.read()
            # PDF text and is_scanned now come from backend after extraction
            st.session_state["pdf_text"] = ""
            st.session_state["is_scanned"] = False
            st.session_state["_file_id"] = file_id
            st.session_state["extracted_info"] = {}
            st.session_state["field_meta"] = {}
            st.session_state["raw_extracted_text"] = ""
            st.session_state["extraction_done"] = False
            st.session_state["validation_result"] = None
            st.session_state["messages"] = []
            st.session_state["verification"] = {}
            st.session_state["accepted"] = {}

        pdf_bytes = st.session_state["pdf_bytes"]
        pdf_text = st.session_state.get("pdf_text", "")
        scanned = st.session_state.get("is_scanned", False)

        # Show status only after extraction (when we have backend data)
        if st.session_state.get("extraction_done"):
            if scanned: st.warning(f"📷 {t('scanned_pdf_warning', lang)}")
            else: st.success(f"✅ {len(pdf_text):,} chars")
        else:
            st.info("Upload complete. Click 'Extract' to process the document.")

        st.divider()
        llm_option = st.selectbox(t("choose_llm", lang), ["Google Gemini", "OpenAI GPT-4o"])
        provider = "gemini" if "Gemini" in llm_option else "openai"
        gemini_model = "gemini-2.5-flash"
        if provider == "gemini":
            gemini_model = st.selectbox("Gemini Model", GEMINI_MODELS, index=0)

        methods = ["vision","text"]
        method_labels = [t("vision_ai",lang), t("text_llm",lang)]
        try:
            from pdf2image import convert_from_bytes
            methods.append("ocr"); method_labels.append(t("ocr_llm",lang))
        except: pass

        if scanned: method = "vision"
        else:
            mi = st.radio(t("extraction_method",lang), range(len(methods)), format_func=lambda i: method_labels[i])
            method = methods[mi]

        if st.button(f"🔍 {t('extract_info', lang)}", use_container_width=True, type="primary"):
            with st.spinner(t("extracting", lang)):
                result = api_extract(pdf_bytes, method=method, provider=provider,
                                     model=gemini_model, lang=lang)
            if result.get("success"):
                st.session_state["extracted_info"] = result.get("extracted_data",{})
                st.session_state["raw_extracted_text"] = result.get("raw_llm_response","")
                # Read PDF preprocessing outputs from backend
                st.session_state["pdf_text"] = result.get("pdf_text", "")
                st.session_state["is_scanned"] = result.get("is_scanned", False)
                st.session_state["extraction_done"] = True
                st.session_state["verification"] = {}
                st.session_state["accepted"] = {}
                meta = {}
                for fk, fv in result.get("extracted_data",{}).items():
                    if isinstance(fv,dict):
                        meta[fk] = {"confidence":fv.get("confidence"),"source":fv.get("source",method)}
                    elif fv is not None and str(fv).strip():
                        meta[fk] = {"confidence":0.8,"source":method}
                st.session_state["field_meta"] = meta
                st.success(f"✅ {result.get('fields_found',0)}/{result.get('fields_total',0)} "
                          f"{t('fields_found',lang)} ({result.get('processing_time_ms',0)}ms)")
            elif result.get("error"):
                st.error(f"Failed: {result['error']}")
            else:
                st.error("Extraction failed — check FastAPI logs")

        if st.session_state.get("extraction_done"):
            if st.button(f"✅ {t('validate_docs', lang)}", use_container_width=True):
                with st.spinner("Validating..."):
                    docs = {"letter_of_credit": st.session_state["extracted_info"]}
                    vr = api_validate(docs, lang)
                st.session_state["validation_result"] = vr
                if vr.get("success"):
                    st.success(f"✅ {vr.get('passed_checks',0)}/{vr.get('total_checks',0)} passed")

    if st.session_state.get("raw_extracted_text"):
        with st.expander("🔬 Raw LLM Response", expanded=False):
            st.code(st.session_state["raw_extracted_text"], language="json")

    # Footer: show tools from FastAPI
    with st.expander("🔧 FastMCP Tools", expanded=False):
        tools = api_get("/tools")
        if not tools.get("error"):
            for tl in tools.get("tools",[]):
                tags = ", ".join(tl.get("tags",[]))
                st.write(f"- `{tl['name']}` [{tags}]")


# ═══════════════════════════════════════════════════════════════
#  MAIN TABS
# ═══════════════════════════════════════════════════════════════

tab_form,tab_review,tab_verify,tab_db,tab_chat,tab_val,tab_prev,tab_sum = st.tabs([
    f"📋 {t('form_tab',lang)}","📊 Form Review",
    "🔎 Verify & Screen","🏦 Database Match",f"💬 {t('chat_tab',lang)}",
    f"✅ {t('validation_report',lang)}",f"📝 {t('preview_tab',lang)}",
    f"📈 {t('summary_tab',lang)}"])

# ── TAB: FORM ──
with tab_form:
    if not st.session_state.get("extraction_done"):
        st.info(t("upload_prompt", lang))
    else:
        info = st.session_state.get("extracted_info",{})
        for i in range(0, len(SECTIONS), 2):
            cols = st.columns(2)
            for ci in range(2):
                if i+ci < len(SECTIONS):
                    sec = SECTIONS[i+ci]
                    with cols[ci]:
                        with st.expander(sec.label(lang), expanded=True):
                            info = render_section_form(sec, info, lang)
        st.session_state["extracted_info"] = info
        st.divider()
        c1,c2 = st.columns(2)
        with c1:
            if st.button(f"💾 {t('save_form',lang)}", use_container_width=True): st.success("Saved!")
        with c2:
            st.download_button(f"📥 {t('export_json',lang)}",
                data=json.dumps(info, indent=2, ensure_ascii=False, default=str),
                file_name="lc_data.json", mime="application/json", use_container_width=True)

# ── TAB: FORM REVIEW ──
with tab_review:
    info = st.session_state.get("extracted_info",{})
    if not info: st.info("Extract a document first to see the form review.")
    else: render_form_review(info, lang)

# ── TAB: VERIFY & SCREEN ──
with tab_verify:
    info = st.session_state.get("extracted_info",{})
    if not st.session_state.get("extraction_done"):
        st.info("Extract a document first, then verify fields here.")
    else: render_verification_panel(info)

# ── TAB: DATABASE MATCH ──
with tab_db:
    cbl_data = st.session_state.get("cbl_data")
    extracted_info = st.session_state.get("extracted_info", {})

    if not cbl_data:
        st.info("👈 Use the sidebar to lookup a customer in the NAB_DEMO database.")
        st.markdown("""
        ### How to use:
        1. Enter a **Customer Number** or **Account Number** in the sidebar
        2. Click **🔎 Lookup** to query the `cbl` table
        3. View the database record and compare with extracted PDF data
        4. Discrepancies will be highlighted automatically
        """)
    elif cbl_data.get("error"):
        st.error(f"Database error: {cbl_data['error']}")
    else:
        st.subheader("🏦 Database Match — CBL Table Data")

        # Account Status Display
        status = (cbl_data.get("account_status") or "").lower()
        if "block" in status:
            st.error(f"⛔ **Account Status:** {cbl_data.get('account_status')} — This account is BLOCKED")
        elif "active" in status:
            st.success(f"✅ **Account Status:** {cbl_data.get('account_status')} — Account is active")
        elif "review" in status or "under" in status:
            st.warning(f"⚠️ **Account Status:** {cbl_data.get('account_status')} — Account under review")
        else:
            st.info(f"**Account Status:** {cbl_data.get('account_status') or 'N/A'}")

        st.divider()

        # Display all CBL fields
        st.markdown("### 📋 Complete CBL Record")
        col1, col2 = st.columns(2)

        cbl_fields = [k for k in cbl_data.keys() if k != "error"]
        mid = len(cbl_fields) // 2

        with col1:
            for field in cbl_fields[:mid]:
                value = cbl_data.get(field, "N/A")
                st.text_input(field.replace("_", " ").title(), str(value), disabled=True, key=f"cbl_{field}")

        with col2:
            for field in cbl_fields[mid:]:
                value = cbl_data.get(field, "N/A")
                st.text_input(field.replace("_", " ").title(), str(value), disabled=True, key=f"cbl2_{field}")

        # Comparison Section
        if extracted_info:
            st.divider()
            st.markdown("### 🔍 Data Comparison — PDF vs Database")

            # Define field mappings (PDF field → Database field)
            field_mappings = {
                "applicant_name": ["customer_name1", "entity_name"],
                "amount": ["lc_amount"],
                "currency": ["lc_currency", "account_currency"],
                "lc_number": ["lc_number"],
                "applicant_account": ["account_number", "current_account_number"],
                "applicant_address": ["address_line1"],
                "swift_code": ["swift_number"],
            }

            discrepancies = []
            matches = []

            for pdf_field, db_fields in field_mappings.items():
                pdf_value = extracted_info.get(pdf_field, "")

                # Try multiple database field names
                db_value = None
                matched_db_field = None
                for db_field in db_fields:
                    db_value = cbl_data.get(db_field)
                    if db_value:
                        matched_db_field = db_field
                        break

                if pdf_value and db_value:
                    # Normalize for comparison
                    pdf_normalized = str(pdf_value).strip().lower()
                    db_normalized = str(db_value).strip().lower()

                    if pdf_normalized != db_normalized:
                        discrepancies.append({
                            "field": pdf_field.replace("_", " ").title(),
                            "pdf_value": str(pdf_value),
                            "cbl_value": str(db_value),
                            "pdf_field": pdf_field,
                            "cbl_field": matched_db_field
                        })
                    else:
                        matches.append({
                            "field": pdf_field.replace("_", " ").title(),
                            "value": str(pdf_value)
                        })

            # Display matches
            if matches:
                st.success(f"✅ **{len(matches)} field(s) match**")
                with st.expander("View matching fields", expanded=False):
                    for match in matches:
                        st.write(f"- **{match['field']}**: {match['value']}")

            # Display discrepancies
            if discrepancies:
                st.error(f"⚠️ **{len(discrepancies)} discrepancy(ies) found**")
                for disc in discrepancies:
                    with st.container():
                        st.markdown(f"**🔴 {disc['field']}**")
                        c1, c2 = st.columns(2)
                        with c1:
                            st.text_input("PDF Value", disc['pdf_value'], disabled=True,
                                        key=f"disc_pdf_{disc['pdf_field']}", label_visibility="visible")
                        with c2:
                            st.text_input("Database Value", disc['cbl_value'], disabled=True,
                                        key=f"disc_cbl_{disc['cbl_field']}", label_visibility="visible")
                        st.divider()
            else:
                if extracted_info:
                    st.success("✅ No discrepancies found in mapped fields!")

        else:
            st.info("Extract a document first to compare with database data.")

# ── TAB: CHAT ──
with tab_chat:
    if not st.session_state.get("pdf_bytes"):
        st.info(t("upload_prompt", lang))
    else:
        cc = st.container(height=480)
        for msg in st.session_state.messages:
            with cc.chat_message(msg["role"]): st.markdown(msg["content"])
        if ui := st.chat_input(t("chat_placeholder", lang)):
            st.session_state.messages.append({"role":"user","content":ui})
            with cc.chat_message("user"): st.markdown(ui)
            with st.spinner("..."):
                hist = [{"role":m["role"],"content":m["content"]} for m in st.session_state.messages[:-1]]
                resp = api_chat(message=ui, extracted_data=st.session_state.get("extracted_info",{}),
                    pdf_text=st.session_state.get("pdf_text",""), history=hist, language=lang)
            reply = resp.get("message","Sorry, I couldn't generate a response.")
            st.session_state.messages.append({"role":"assistant","content":reply})
            with cc.chat_message("assistant"): st.markdown(reply)

# ── TAB: VALIDATION REPORT ──
with tab_val:
    vr = st.session_state.get("validation_result")
    if not vr: st.info("Run validation from sidebar.")
    else:
        c1,c2,c3 = st.columns(3)
        with c1: st.metric("✅ Passed", vr.get("passed_checks",0))
        with c2: st.metric("⚠️ Warnings", vr.get("warnings",0))
        with c3: st.metric("❌ Errors", vr.get("errors",0))
        for ch in vr.get("checks",[]):
            passed = ch.get("passed",False)
            sev = ch.get("severity","info")
            ico = "✅" if passed else ("⚠️" if sev == "warning" else "❌")
            st.write(f"{ico} **{ch.get('rule_name','')}**: {ch.get('message','')}")

# ── TAB: PREVIEW ──
with tab_prev:
    pt = st.session_state.get("pdf_text","")
    if pt: st.text_area("PDF text", pt, height=600, disabled=True)
    else: st.warning(t("no_text_warning", lang))

# ── TAB: SUMMARY ──
with tab_sum:
    info_d = st.session_state.get("extracted_info",{})
    if info_d:
        found = {k:v for k,v in info_d.items() if v is not None and v != "" and v is not False}
        missing = {k:v for k,v in info_d.items() if v is None or v == ""}
        c1,c2 = st.columns(2)
        with c1: st.metric(t("fields_extracted",lang), len(found))
        with c2: st.metric(t("fields_missing",lang), len(missing))
        if found:
            for k,v in found.items():
                meta = st.session_state.get("field_meta",{}).get(k,{})
                conf = meta.get("confidence")
                badge,_ = _confidence_badge(conf) if conf else ("","")
                st.write(f"- {badge} **{k.replace('_',' ').title()}**: {v}")
    else: st.info("Run extraction first.")