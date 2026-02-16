"""
External API Agent — verifies L/C field values against real external sources.

KEY DESIGN PRINCIPLES:
  1. ACCURACY FIRST: Cross-reference sources before concluding. Never flag fraud
     based on a single noisy signal. If Perplexity says "legitimate" but Exa found
     generic "fraud" results, trust the deeper research.
  2. SMART MATCHING: Port/city lookups use exact-first matching with country context.
     "Libya" should never match "Libiaz, Poland".
  3. CASCADING FALLBACK: Every tool tries multiple sources before giving up.
  4. RICH OUTPUT: Google Maps links, source URLs, citations on every result.

API Ninjas SWIFT: bank= is PREMIUM ONLY. Set API_NINJAS_PREMIUM=true in .env.
"""

from __future__ import annotations
import re
import logging
from urllib.parse import quote_plus

import httpx

from agents.base_agent import BaseAgent
from schemas.models import ExternalVerificationRequest, ExternalVerificationResult
from config.settings import get_settings

logger = logging.getLogger(__name__)
HTTP_TIMEOUT = 20.0


# ═══════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════

def _gmaps_link(lat, lon):
    if lat is None or lon is None:
        return None
    return f"https://www.google.com/maps?q={lat},{lon}"

def _gmaps_search(query):
    return f"https://www.google.com/maps/search/{quote_plus(query)}"


# ═══════════════════════════════════════════════════════════════
#  LOW-LEVEL API CLIENTS
# ═══════════════════════════════════════════════════════════════

def _call_exa_search(query, num_results=5, category=None, include_domains=None):
    settings = get_settings()
    if not settings.exa_api_key:
        return None
    headers = {"x-api-key": settings.exa_api_key, "Content-Type": "application/json"}
    payload = {"query": query, "numResults": num_results, "text": True, "highlights": True}
    if category:
        payload["category"] = category
    if include_domains:
        payload["includeDomains"] = include_domains
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            resp = client.post("https://api.exa.ai/search", headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.error(f"Exa search failed: {e}")
        return None


def _call_perplexity(question, system_prompt=None):
    settings = get_settings()
    if not settings.perplexity_api_key:
        return None
    headers = {"Authorization": f"Bearer {settings.perplexity_api_key}", "Content-Type": "application/json"}
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": question})
    payload = {"model": settings.perplexity_model, "messages": messages}
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post("https://api.perplexity.ai/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            citations = data.get("citations", [])
            return {"content": content, "citations": citations}
    except Exception as e:
        logger.error(f"Perplexity call failed: {e}")
        return None


def _call_api_ninjas_swift(**params):
    settings = get_settings()
    if not settings.api_ninjas_key:
        return None
    is_premium = getattr(settings, 'api_ninjas_premium', False)
    if is_premium:
        allowed = {k: v for k, v in params.items() if k in ("swift", "bank", "city", "country", "offset")}
    else:
        allowed = {k: v for k, v in params.items() if k in ("swift", "city", "country", "offset")}
    if not allowed:
        return None
    headers = {"X-Api-Key": settings.api_ninjas_key}
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            resp = client.get("https://api.api-ninjas.com/v1/swiftcode", headers=headers, params=allowed)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.error(f"API Ninjas SWIFT failed: {e}")
        return None


def _call_geoapify(query):
    settings = get_settings()
    if not settings.geoapify_key:
        return None
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            resp = client.get("https://api.geoapify.com/v1/geocode/search",
                              params={"text": query, "apiKey": settings.geoapify_key, "limit": 5})
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.error(f"Geoapify failed: {e}")
        return None


# ═══════════════════════════════════════════════════════════════
#  FORMAT VALIDATORS
# ═══════════════════════════════════════════════════════════════

def _validate_hs_code_format(code):
    cleaned = code.replace(".", "").replace(" ", "").strip()
    if not cleaned.isdigit():
        return {"valid": False, "error": "HS code must be numeric"}
    if len(cleaned) < 4:
        return {"valid": False, "error": "HS code must be at least 4 digits"}
    if len(cleaned) > 12:
        return {"valid": False, "error": "HS code cannot exceed 12 digits"}
    chapter = int(cleaned[:2])
    if chapter < 1 or chapter > 99:
        return {"valid": False, "error": f"Invalid chapter {chapter:02d}"}
    return {"valid": True, "chapter": f"{chapter:02d}", "heading": cleaned[:4],
            "subheading": cleaned[:6] if len(cleaned) >= 6 else None,
            "full_code": cleaned, "digits": len(cleaned)}


def _validate_swift_format(code):
    s = code.strip().upper().replace(" ", "").replace("-", "")
    if len(s) not in (8, 11):
        return {"valid": False, "error": f"Must be 8 or 11 chars, got {len(s)}", "cleaned": s}
    if not s[:4].isalpha():
        return {"valid": False, "error": f"First 4 chars must be letters: '{s[:4]}'", "cleaned": s}
    if not s[4:6].isalpha():
        return {"valid": False, "error": f"Country code must be letters: '{s[4:6]}'", "cleaned": s}
    if not s[6:8].isalnum():
        return {"valid": False, "error": f"Location must be alphanumeric: '{s[6:8]}'", "cleaned": s}
    return {"valid": True, "bank_code": s[:4], "country_code": s[4:6],
            "location_code": s[6:8], "branch_code": s[8:11] if len(s) == 11 else "XXX", "cleaned": s}


def _validate_container_number(number):
    c = number.strip().upper().replace(" ", "").replace("-", "")
    if len(c) != 11:
        return {"valid": False, "error": f"Must be 11 chars, got {len(c)}"}
    if not c[:3].isalpha():
        return {"valid": False, "error": f"First 3 must be letters: '{c[:3]}'"}
    if c[3] not in "UJZ":
        return {"valid": False, "error": f"4th char must be U/J/Z: '{c[3]}'"}
    if not c[4:10].isdigit():
        return {"valid": False, "error": f"Chars 5-10 must be digits: '{c[4:10]}'"}
    if not c[10].isdigit():
        return {"valid": False, "error": f"Check digit must be digit: '{c[10]}'"}
    return {"valid": True, "owner_code": c[:3], "equipment_category": c[3],
            "serial_number": c[4:10], "check_digit": c[10], "formatted": f"{c[:4]} {c[4:10]} {c[10]}"}


# ═══════════════════════════════════════════════════════════════
#  COUNTRY / PORT INTELLIGENCE
# ═══════════════════════════════════════════════════════════════

# Common country name → ISO code mapping for L/C documents
COUNTRY_ALIASES = {
    "libya": "LY", "libia": "LY", "libyan": "LY",
    "italy": "IT", "italia": "IT", "italian": "IT",
    "egypt": "EG", "egyptian": "EG",
    "tunisia": "TN", "tunisian": "TN",
    "algeria": "DZ", "algerian": "DZ",
    "morocco": "MA", "moroccan": "MA",
    "turkey": "TR", "turkiye": "TR",
    "china": "CN", "chinese": "CN",
    "india": "IN", "indian": "IN",
    "usa": "US", "united states": "US", "america": "US",
    "uk": "GB", "united kingdom": "GB", "england": "GB", "britain": "GB",
    "germany": "DE", "german": "DE", "deutschland": "DE",
    "france": "FR", "french": "FR",
    "spain": "ES", "spanish": "ES",
    "greece": "GR", "greek": "GR",
    "lebanon": "LB", "lebanese": "LB",
    "jordan": "JO", "jordanian": "JO",
    "uae": "AE", "emirates": "AE", "dubai": "AE",
    "saudi": "SA", "saudi arabia": "SA",
}

def _guess_country_code(text):
    """Try to extract a country code from free text (port name, context)."""
    t = text.lower().strip()
    for alias, code in COUNTRY_ALIASES.items():
        if alias in t:
            return code
    # Check for 2-letter code at end like "TRIPOLI, LY"
    m = re.search(r',\s*([A-Z]{2})\s*$', text.strip())
    if m:
        return m.group(1)
    return ""


# ═══════════════════════════════════════════════════════════════
#  AGENT
# ═══════════════════════════════════════════════════════════════

class ExternalAPIAgent(BaseAgent):
    name = "external_api_agent"
    description = "Verifies L/C fields via Exa, Perplexity, API Ninjas, Geoapify, UNLOCODE"

    def _register_tools(self):
        self.register_tool("verify_hs_code", self.verify_hs_code,
                           "Verify HS code format + lookup via Perplexity/Exa")
        self.register_tool("verify_swift_code", self.verify_swift_code,
                           "Verify SWIFT/BIC (smart cleanup + API Ninjas + Perplexity/Exa)")
        self.register_tool("check_sanctions", self.check_sanctions,
                           "Screen party against sanctions via Perplexity + Exa")
        self.register_tool("track_shipment", self.track_shipment,
                           "Track container/BL + provide tracking URLs")
        self.register_tool("verify_company", self.verify_company,
                           "Verify company legitimacy via Exa + Perplexity (cross-referenced)")
        self.register_tool("verify_port", self.verify_port,
                           "Verify port via UNLOCODE + Geoapify (country-aware smart matching)")
        self.register_tool("verify_bank_by_name", self.verify_bank_by_name,
                           "Search bank by name via Exa + Perplexity (+ API Ninjas if premium)")
        self.register_tool("deep_research_verify", self.deep_research_verify,
                           "Deep research via Perplexity sonar-pro + Exa")

    # ── 1. HS CODE ────────────────────────────────────────────
    @BaseAgent.timed
    def verify_hs_code(self, request):
        hs_code = request.field_value.strip()
        fmt = _validate_hs_code_format(hs_code)
        if not fmt["valid"]:
            return ExternalVerificationResult(verification_type="hs_code", verified=False,
                                              message=fmt["error"], source="format_validation")
        lookup_urls = {
            "us_hts": f"https://hts.usitc.gov/?query={hs_code}",
            "eu_taric": f"https://ec.europa.eu/taxation_customs/dds2/taric/measures.jsp?Lang=en&Taric={hs_code}",
        }
        pplx = _call_perplexity(
            f"What product does HS code {hs_code} (chapter {fmt['chapter']}) classify? Official description.",
            system_prompt="Trade classification expert. Be concise.")
        if pplx and pplx.get("content"):
            return ExternalVerificationResult(verification_type="hs_code", verified=True, confidence=0.85,
                message=f"HS {hs_code} — {pplx['content'][:300]}",
                details={**fmt, "description": pplx["content"][:500],
                         "source_urls": pplx.get("citations", [])[:3], "lookup_urls": lookup_urls},
                source="perplexity_sonar_pro")
        exa = _call_exa_search(f"HS code {hs_code} harmonized system", num_results=3,
                               include_domains=["hts.usitc.gov", "trade.gov", "wcoomd.org"])
        if exa and exa.get("results"):
            return ExternalVerificationResult(verification_type="hs_code", verified=True, confidence=0.75,
                message=f"HS {hs_code} format valid (Ch.{fmt['chapter']}). Web results found.",
                details={**fmt, "source_urls": [r.get("url","") for r in exa["results"][:3]], "lookup_urls": lookup_urls},
                source="exa_search")
        return ExternalVerificationResult(verification_type="hs_code", verified=True, confidence=0.6,
            message=f"HS {hs_code} format valid (Ch.{fmt['chapter']}). See lookup URLs.",
            details={**fmt, "lookup_urls": lookup_urls}, source="format_validation")

    # ── 2. SWIFT CODE ─────────────────────────────────────────
    @BaseAgent.timed
    def verify_swift_code(self, request):
        raw = request.field_value.strip().upper().replace(" ", "").replace("-", "")
        candidates = [raw]
        if len(raw) == 10:
            candidates += [raw[:8], raw + "X", raw[:8] + raw[9:]]
        elif len(raw) == 9:
            candidates += [raw[:8], raw + "XX"]
        elif len(raw) == 12:
            candidates += [raw[:11], raw[:8]]
        if raw.endswith("XXX") and len(raw) == 11:
            candidates.append(raw[:8])
        seen = set()
        candidates = [c for c in candidates if not (c in seen or seen.add(c))]

        for swift in candidates:
            fmt = _validate_swift_format(swift)
            if not fmt["valid"]:
                continue
            ninjas = _call_api_ninjas_swift(swift=fmt["cleaned"])
            if ninjas and isinstance(ninjas, list) and len(ninjas) > 0:
                b = ninjas[0]
                note = f" (cleaned from '{raw}')" if swift != raw else ""
                return ExternalVerificationResult(verification_type="swift_code", verified=True, confidence=0.95,
                    message=f"SWIFT {fmt['cleaned']} VERIFIED: {b.get('bank_name','')} "
                            f"in {b.get('city','')}, {b.get('country','')}{note}",
                    details={**fmt, "original_input": raw,
                             "bank_name": b.get("bank_name"), "city": b.get("city"),
                             "country": b.get("country"), "address": b.get("address"),
                             "google_maps": _gmaps_search(f"{b.get('bank_name','')} {b.get('city','')} {b.get('country','')}")},
                    source="api_ninjas")

        pplx = _call_perplexity(
            f"What bank has SWIFT/BIC code '{raw}'? Give bank name, city, country. "
            f"If code seems wrong, suggest the correct SWIFT code.",
            system_prompt="Banking SWIFT code expert. Always provide bank name and location.")
        if pplx and pplx.get("content"):
            return ExternalVerificationResult(verification_type="swift_code", verified=True, confidence=0.7,
                message=f"SWIFT '{raw}' — {pplx['content'][:250]}",
                details={"original_input": raw, "candidates_tried": candidates,
                         "research": pplx["content"][:600], "source_urls": pplx.get("citations", [])[:5]},
                source="perplexity_sonar_pro")

        exa = _call_exa_search(f"SWIFT BIC code {raw} bank", num_results=3)
        if exa and exa.get("results"):
            return ExternalVerificationResult(verification_type="swift_code", verified=True, confidence=0.5,
                message=f"SWIFT '{raw}' — web results found.",
                details={"original_input": raw,
                         "source_urls": [r.get("url","") for r in exa["results"][:3]]},
                source="exa_search")

        fmt = _validate_swift_format(raw)
        return ExternalVerificationResult(verification_type="swift_code",
            verified=fmt.get("valid", False), confidence=0.3,
            message=f"SWIFT '{raw}': {fmt.get('error','Format valid but not found.')} Tried: {candidates}",
            details={"original_input": raw, "candidates_tried": candidates, "format_check": fmt},
            source="format_validation")

    # ── 3. BANK NAME SEARCH ───────────────────────────────────
    @BaseAgent.timed
    def verify_bank_by_name(self, request):
        bank_name = request.field_value.strip()
        country = request.additional_context.get("country_code", "")
        if len(bank_name) < 2:
            return ExternalVerificationResult(verification_type="bank_lookup", verified=False,
                                              message="Bank name too short.", source="input_validation")

        search_names = [bank_name]
        words = bank_name.split()
        if len(words) > 3: search_names.append(" ".join(words[:3]))
        if len(words) > 2: search_names.append(" ".join(words[:2]))
        if len(words) > 1: search_names.append(words[0])
        for sfx in ["S.P.A.", "SPA", "S.A.", "SA", "PLC", "LTD", "LLC", "AG", "GMBH", "N.V.", "NV"]:
            cleaned = re.sub(r'\b' + re.escape(sfx) + r'\b', '', bank_name, flags=re.IGNORECASE).strip()
            if cleaned and cleaned.upper() != bank_name.upper():
                search_names.append(cleaned)
        seen = set()
        unique = [n for n in search_names if n.upper().strip() not in seen and not seen.add(n.upper().strip()) and len(n.strip()) >= 2]

        # L1: API Ninjas PREMIUM only
        if getattr(get_settings(), 'api_ninjas_premium', False):
            for sname in unique:
                params = {"bank": sname}
                if country: params["country"] = country
                ninjas = _call_api_ninjas_swift(**params)
                if ninjas and isinstance(ninjas, list) and len(ninjas) > 0:
                    branches = [{"swift": b.get("swift"), "name": b.get("bank_name"),
                                 "city": b.get("city"), "country": b.get("country"),
                                 "google_maps": _gmaps_search(f"{b.get('bank_name','')} {b.get('city','')}")}
                                for b in ninjas[:10]]
                    return ExternalVerificationResult(verification_type="bank_lookup", verified=True, confidence=0.9,
                        message=f"Found {len(ninjas)} branch(es) for '{bank_name}' (searched: '{sname}').",
                        details={"branches": branches, "total": len(ninjas)}, source="api_ninjas_premium")

        # L2: Exa
        exa = _call_exa_search(f"{bank_name} bank SWIFT BIC code official website" + (f" {country}" if country else ""),
                               num_results=5, category="company")
        if exa and exa.get("results"):
            results = [{"title": r.get("title",""), "url": r.get("url",""),
                        "snippet": (r.get("text") or "")[:250]} for r in exa["results"][:5]]
            return ExternalVerificationResult(verification_type="bank_lookup", verified=True, confidence=0.75,
                message=f"'{bank_name}' found via Exa ({len(exa['results'])} results).",
                details={"bank_name": bank_name, "exa_results": results,
                         "source_urls": [r["url"] for r in results],
                         "google_maps": _gmaps_search(f"{bank_name} bank")}, source="exa_search")

        # L3: Perplexity
        pplx = _call_perplexity(
            f"Is '{bank_name}' a real bank? Give SWIFT/BIC codes, headquarters, official website. "
            f"If misspelled suggest the correct name.",
            system_prompt="Banking expert. Verify bank existence. Provide SWIFT codes.")
        if pplx and pplx.get("content"):
            return ExternalVerificationResult(verification_type="bank_lookup", verified=True, confidence=0.7,
                message=f"'{bank_name}' — {pplx['content'][:200]}",
                details={"bank_name": bank_name, "research": pplx["content"][:800],
                         "source_urls": pplx.get("citations", [])[:5],
                         "google_maps": _gmaps_search(f"{bank_name} bank headquarters")},
                source="perplexity_sonar_pro")

        return ExternalVerificationResult(verification_type="bank_lookup", verified=False, confidence=0.2,
            message=f"No info for '{bank_name}'. Names tried: {unique}",
            details={"names_tried": unique, "google_maps": _gmaps_search(f"{bank_name} bank")},
            source="all_exhausted")

    # ── 4. SANCTIONS ──────────────────────────────────────────
    @BaseAgent.timed
    def check_sanctions(self, request):
        party = request.field_value.strip()
        if len(party) < 2:
            return ExternalVerificationResult(verification_type="sanctions", verified=False,
                                              message="Party name too short.", source="input_validation")
        ofac_url = f"https://sanctionssearch.ofac.treas.gov/Details.aspx?id={quote_plus(party)}"
        pplx = _call_perplexity(
            f"Is '{party}' on any OFAC SDN, EU, or UN sanctions list? Check for fraud or money laundering too.",
            system_prompt="AML/CFT compliance analyst. If no hits, say explicitly 'no sanctions found'.")
        if pplx and pplx.get("content"):
            content = pplx["content"].lower()
            hit_words = ["sanctioned", "designated", "listed on", "sdn list", "blocked", "restricted"]
            clear_words = ["no sanctions", "not listed", "not found on", "no matches", "not sanctioned",
                           "no indication", "does not appear", "no evidence", "not on any"]
            is_hit = any(w in content for w in hit_words)
            is_clear = any(w in content for w in clear_words)
            if is_hit and not is_clear:
                return ExternalVerificationResult(verification_type="sanctions", verified=False, confidence=0.8,
                    message=f"POTENTIAL SANCTIONS HIT for '{party}'. Manual review required.",
                    details={"party": party, "research": pplx["content"][:800],
                             "source_urls": pplx.get("citations", [])[:5], "ofac_search_url": ofac_url},
                    source="perplexity_sonar_pro")
            return ExternalVerificationResult(verification_type="sanctions", verified=True, confidence=0.7,
                message=f"No sanctions hits found for '{party}'.",
                details={"party": party, "research": pplx["content"][:500],
                         "source_urls": pplx.get("citations", [])[:5], "ofac_search_url": ofac_url},
                source="perplexity_sonar_pro")
        exa = _call_exa_search(f"'{party}' OFAC sanctions SDN list", num_results=5)
        if exa and exa.get("results"):
            return ExternalVerificationResult(verification_type="sanctions", verified=True, confidence=0.5,
                message=f"Exa: {len(exa['results'])} results for '{party}'. Manual review recommended.",
                details={"source_urls": [r.get("url","") for r in exa["results"][:5]], "ofac_search_url": ofac_url},
                source="exa_search")
        return ExternalVerificationResult(verification_type="sanctions", verified=True, confidence=0.3,
            message=f"Could not screen '{party}'. Use OFAC link manually.",
            details={"ofac_search_url": ofac_url}, source="no_api")

    # ── 5. SHIPMENT TRACKING ──────────────────────────────────
    @BaseAgent.timed
    def track_shipment(self, request):
        tracking = request.field_value.strip().upper()
        if not tracking:
            return ExternalVerificationResult(verification_type="shipment_tracking", verified=False,
                                              message="No tracking number.", source="input_validation")
        container_check = _validate_container_number(tracking)
        details = {"tracking_urls": {
            "shipsgo": f"https://shipsgo.com/container-tracking/{tracking}",
            "track_cargo": f"https://trackcargo.co/container/{tracking}",
            "cma_cgm": f"https://www.cma-cgm.com/ebusiness/tracking?SearchBy=Container&Reference={tracking}",
            "maersk": f"https://www.maersk.com/tracking/{tracking}",
            "msc": f"https://www.msc.com/en/track-a-shipment?trackingNumber={tracking}",
            "hapag_lloyd": f"https://www.hapag-lloyd.com/en/online-business/track/track-by-container-solution.html?container={tracking}",
        }}
        if container_check["valid"]:
            details["container_format"] = container_check
        pplx = _call_perplexity(
            f"Track container or BL '{tracking}'. Status, vessel, location, ETA?",
            system_prompt="Shipping logistics expert.")
        if pplx and pplx.get("content"):
            details["live_research"] = pplx["content"][:600]
            details["source_urls"] = pplx.get("citations", [])[:3]
            return ExternalVerificationResult(verification_type="shipment_tracking", verified=True, confidence=0.7,
                message=f"Research found for '{tracking}'. See tracking links.",
                details=details, source="perplexity_sonar_pro")
        v = container_check["valid"]
        return ExternalVerificationResult(verification_type="shipment_tracking", verified=v,
            confidence=0.5 if v else 0.3,
            message=f"Container format {'valid' if v else 'invalid'}. Use tracking URLs.",
            details=details, source="format_validation")

    # ══════════════════════════════════════════════════════════════
    #  6. COMPANY VERIFICATION — CROSS-REFERENCED, NOT NAIVE
    # ══════════════════════════════════════════════════════════════
    @BaseAgent.timed
    def verify_company(self, request):
        """
        ACCURACY DESIGN:
        - Exa fraud search returns noise for any company (generic "fraud prevention" articles).
        - We do NOT flag fraud based on Exa alone.
        - We use Perplexity as the AUTHORITATIVE source for legitimacy.
        - Only flag fraud if Perplexity SPECIFICALLY says the company is fraudulent.
        """
        company = request.field_value.strip()
        country = request.additional_context.get("country", "")
        if len(company) < 2:
            return ExternalVerificationResult(verification_type="company_verification", verified=False,
                                              message="Company name too short.", source="input_validation")

        sources = []
        details = {"company_name": company, "country": country,
                   "google_maps": _gmaps_search(f"{company} {country} headquarters")}

        # Step 1: Exa company search (existence check, NOT fraud check)
        exa = _call_exa_search(f"{company} {country} company official website", num_results=5, category="company")
        if exa and exa.get("results"):
            details["exa_results"] = [{"title": r.get("title",""), "url": r.get("url",""),
                                       "snippet": (r.get("text") or "")[:200]} for r in exa["results"][:5]]
            details["source_urls"] = [r.get("url","") for r in exa["results"][:5]]
            sources.append(f"Exa: {len(exa['results'])} results")

        # Step 2: Perplexity AUTHORITATIVE legitimacy check
        q = f"Is '{company}'"
        if country: q += f" from {country}"
        q += (" a legitimate registered company? Provide: "
              "1) Is it a real, registered business? "
              "2) Official website URL "
              "3) Industry/sector "
              "4) Any SPECIFIC fraud convictions, regulatory actions, or criminal charges? "
              "Do NOT flag generic industry fraud articles. Only flag if THIS SPECIFIC company has fraud issues.")
        pplx = _call_perplexity(q,
            system_prompt="Corporate due diligence analyst. Be PRECISE. "
                          "Only flag fraud if you find SPECIFIC evidence against THIS company. "
                          "Generic fraud articles about the industry do NOT count.")
        if pplx and pplx.get("content"):
            details["perplexity_research"] = pplx["content"][:800]
            if not details.get("source_urls"):
                details["source_urls"] = []
            details["source_urls"].extend(pplx.get("citations", [])[:5])
            sources.append("Perplexity research")

            # CROSS-REFERENCE: Only flag fraud if Perplexity SPECIFICALLY identifies fraud
            research_lower = pplx["content"].lower()
            # These indicate Perplexity found SPECIFIC fraud evidence
            specific_fraud = any(phrase in research_lower for phrase in [
                "convicted of fraud", "charged with fraud", "regulatory action against",
                "fined for", "shut down", "revoked license", "ponzi scheme",
                "criminal charges", "money laundering conviction", "blacklisted",
                "is fraudulent", "is a scam", "not a legitimate",
            ])
            # These indicate Perplexity confirmed legitimacy
            confirmed_legit = any(phrase in research_lower for phrase in [
                "legitimate", "registered", "established", "incorporated",
                "official website", "operates in", "headquartered",
                "no fraud", "no evidence of fraud", "reputable",
            ])

            if specific_fraud and not confirmed_legit:
                return ExternalVerificationResult(verification_type="company_verification", verified=False, confidence=0.75,
                    message=f"⚠️ SPECIFIC FRAUD EVIDENCE found for '{company}'. Review required.",
                    details=details, source=", ".join(sources))

        if not sources:
            return ExternalVerificationResult(verification_type="company_verification", verified=False, confidence=0.2,
                message=f"No info found for '{company}'. Could indicate non-existent entity.",
                details=details, source="no_results")

        confidence = 0.85 if (details.get("exa_results") and details.get("perplexity_research")) else 0.65
        return ExternalVerificationResult(verification_type="company_verification", verified=True, confidence=confidence,
            message=f"Company '{company}' verified via {len(sources)} source(s).",
            details=details, source=", ".join(sources))

    # ══════════════════════════════════════════════════════════════
    #  7. PORT VERIFICATION — COUNTRY-AWARE SMART MATCHING
    # ══════════════════════════════════════════════════════════════
    @BaseAgent.timed
    def verify_port(self, request):
        """
        ACCURACY DESIGN:
        - "Libya" must NOT match "Libiaz, Poland"
        - Extract country context from the L/C document or port name itself
        - Use exact matching first, then starts-with, then contains
        - UNLOCODE search with country filter when possible
        """
        raw_port = request.field_value.strip()
        if len(raw_port) < 2:
            return ExternalVerificationResult(verification_type="port_verification", verified=False,
                                              message="Port name too short.", source="input_validation")

        # Extract country context from the request or the port name itself
        doc_country = request.additional_context.get("country", "")
        doc_country_code = request.additional_context.get("country_code", "")
        if not doc_country_code:
            doc_country_code = _guess_country_code(raw_port) or _guess_country_code(doc_country)

        # Clean and split compound names
        cleaned = raw_port
        for nw in ["seaport", "sea port", "port", "airport", "terminal", "harbour", "harbor"]:
            cleaned = re.sub(r'\b' + re.escape(nw) + r'\b', "", cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.strip().strip(",").strip()
        port_names = re.split(r'\s+AND/OR\s+|\s+AND\s+|\s+OR\s+|/|,', cleaned, flags=re.IGNORECASE)
        port_names = [p.strip() for p in port_names if p.strip() and len(p.strip()) >= 2]
        if not port_names:
            port_names = [raw_port]

        # Also try to guess country from each port name (e.g. "Tripoli Libya" → LY)
        port_country_hints = {}
        for pn in port_names:
            cc = _guess_country_code(pn)
            if cc:
                port_country_hints[pn] = cc

        # L1: UNLOCODE (local, 116K records) — with COUNTRY FILTER
        all_matches = []
        try:
            from utils.unlocode import search_port as unlo_search, get_ports_count

            for pname in port_names:
                # Clean the port name of country words for search
                search_name = pname
                for alias in COUNTRY_ALIASES:
                    search_name = re.sub(r'\b' + re.escape(alias) + r'\b', '', search_name, flags=re.IGNORECASE).strip()
                if not search_name or len(search_name) < 2:
                    search_name = pname

                # Determine country filter
                cc = port_country_hints.get(pname, "") or doc_country_code

                # Search with country filter first (precise)
                if cc:
                    results = unlo_search(search_name, country_code=cc, ports_only=True, max_results=5)
                    if not results:
                        results = unlo_search(search_name, country_code=cc, ports_only=False, max_results=5)
                # If no country or no results, search globally but be strict
                if not cc or not results:
                    results = unlo_search(search_name, ports_only=True, max_results=10)
                    # FILTER: If we have a country hint, remove results from wrong countries
                    if cc and results:
                        filtered = [r for r in results if r["country_code"] == cc]
                        if filtered:
                            results = filtered

                if results:
                    all_matches.extend(results)

            if all_matches:
                # Deduplicate by locode
                seen_codes = set()
                unique_matches = []
                for m in all_matches:
                    if m["locode"] not in seen_codes:
                        seen_codes.add(m["locode"])
                        m["google_maps"] = _gmaps_link(m.get("lat"), m.get("lon")) or _gmaps_search(f"{m['name']} port {m['country_code']}")
                        unique_matches.append(m)

                summary = ", ".join(f"{m['name']} ({m['locode']})" for m in unique_matches[:5])
                return ExternalVerificationResult(verification_type="port_verification", verified=True, confidence=0.95,
                    message=f"Port(s) FOUND in UN/LOCODE: {summary}",
                    details={"query": raw_port, "parsed_ports": port_names,
                             "country_filter": doc_country_code,
                             "matches": [{"locode": m["locode"], "name": m["name"], "country": m["country_code"],
                                          "functions": m["functions"], "lat": m.get("lat"), "lon": m.get("lon"),
                                          "google_maps": m["google_maps"]} for m in unique_matches[:5]],
                             "database_size": get_ports_count()},
                    source="unlocode_database")
        except Exception as e:
            logger.warning(f"UNLOCODE lookup failed: {e}")

        # L2: Geoapify geocoding
        for pname in port_names:
            geo = _call_geoapify(f"{pname} port" + (f" {doc_country_code}" if doc_country_code else ""))
            if geo and geo.get("features"):
                locs = []
                for feat in geo["features"][:3]:
                    p = feat.get("properties", {})
                    lat, lon = p.get("lat"), p.get("lon")
                    locs.append({"name": p.get("formatted",""), "city": p.get("city",""),
                                 "country": p.get("country",""), "country_code": p.get("country_code",""),
                                 "lat": lat, "lon": lon,
                                 "google_maps": _gmaps_link(lat, lon)})
                if locs:
                    best = locs[0]
                    return ExternalVerificationResult(verification_type="port_verification", verified=True, confidence=0.85,
                        message=f"Port '{pname}' located: {best['name']} ({best['country']})",
                        details={"query": raw_port, "parsed_ports": port_names, "locations": locs,
                                 "google_maps": best["google_maps"]}, source="geoapify")

        # L3: Perplexity
        pplx = _call_perplexity(
            f"Where is the port '{raw_port}'? Give country, city, coordinates, UN/LOCODE.",
            system_prompt="Shipping logistics expert.")
        if pplx and pplx.get("content"):
            return ExternalVerificationResult(verification_type="port_verification", verified=True, confidence=0.6,
                message=f"Port '{raw_port}' — {pplx['content'][:200]}",
                details={"query": raw_port, "research": pplx["content"][:500],
                         "source_urls": pplx.get("citations", [])[:3],
                         "google_maps": _gmaps_search(f"{raw_port} seaport")},
                source="perplexity_sonar_pro")

        return ExternalVerificationResult(verification_type="port_verification", verified=False, confidence=0.3,
            message=f"Could not verify port '{raw_port}'. Searched: {', '.join(port_names)}",
            details={"query": raw_port, "parsed_ports": port_names,
                     "google_maps": _gmaps_search(f"{raw_port} port")}, source="no_results")

    # ── 8. DEEP RESEARCH ──────────────────────────────────────
    @BaseAgent.timed
    def deep_research_verify(self, request):
        query = request.field_value.strip()
        ctx = request.additional_context.get("context", "")
        full = f"{query} Context: {ctx}" if ctx else query
        pplx = _call_perplexity(full,
            system_prompt="Trade finance verification analyst. Be factual, cite sources, flag concerns.")
        if pplx and pplx.get("content"):
            return ExternalVerificationResult(verification_type="deep_research", verified=True, confidence=0.75,
                message="Research completed.",
                details={"query": query, "research": pplx["content"],
                         "source_urls": pplx.get("citations", [])},
                source="perplexity_sonar_pro")
        exa = _call_exa_search(query, num_results=5)
        if exa and exa.get("results"):
            return ExternalVerificationResult(verification_type="deep_research", verified=True, confidence=0.5,
                message=f"{len(exa['results'])} web results found.",
                details={"source_urls": [r.get("url","") for r in exa["results"][:5]],
                         "results": [{"title": r.get("title",""), "url": r.get("url",""),
                                      "text": (r.get("text") or "")[:300]} for r in exa["results"][:5]]},
                source="exa_search")
        return ExternalVerificationResult(verification_type="deep_research", verified=False, confidence=0.1,
            message="No results. Check API keys.", source="no_api")
