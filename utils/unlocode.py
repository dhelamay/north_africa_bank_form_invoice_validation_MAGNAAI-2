"""
UN/LOCODE Port Lookup — local database of 116K+ locations worldwide.

CSV Format (no header): Change,Country,Location,Name,NameWoDiacritics,Subdivision,Function,Status,Date,IATA,Coordinates,Remarks

Usage:
    from utils.unlocode import search_port, get_port_by_code
    results = search_port("Tripoli")
    port = get_port_by_code("LY", "TIP")
"""

from __future__ import annotations
import csv
import os
import logging
from typing import Optional
from functools import lru_cache

from config.settings import get_settings

logger = logging.getLogger(__name__)

# CSV column indices (no header row)
COL_CHANGE = 0
COL_COUNTRY = 1
COL_LOCATION = 2
COL_NAME = 3
COL_NAME_NODIACRITICS = 4
COL_SUBDIVISION = 5
COL_FUNCTION = 6
COL_STATUS = 7
COL_DATE = 8
COL_IATA = 9
COL_COORDINATES = 10
COL_REMARKS = 11

# Function code meanings (position in 8-char string)
FUNCTION_LABELS = {
    0: "Port",
    1: "Rail Terminal",
    2: "Road Terminal",
    3: "Airport",
    4: "Postal Exchange",
    5: "Multimodal (ICD/CFS)",
    6: "Fixed Transport",
    7: "Border Crossing",
}

_ports_cache: list[dict] | None = None


def _find_csv_files() -> list[str]:
    """Find UNLOCODE CSV files. Checks settings path, then common locations."""
    settings = get_settings()
    paths_to_check = []

    # From .env
    if settings.unlocode_csv_path:
        # Could be a single file or directory
        p = settings.unlocode_csv_path
        if os.path.isfile(p):
            paths_to_check.append(p)
        elif os.path.isdir(p):
            for f in sorted(os.listdir(p)):
                if "UNLOCODE" in f and f.endswith(".csv"):
                    paths_to_check.append(os.path.join(p, f))

    # Check relative to project root
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for subdir in ["unlocode_data", "data", "."]:
        d = os.path.join(project_root, subdir)
        if os.path.isdir(d):
            for f in sorted(os.listdir(d)):
                if "UNLOCODE" in f and f.endswith(".csv") and "CodeList" in f:
                    full = os.path.join(d, f)
                    if full not in paths_to_check:
                        paths_to_check.append(full)

    return paths_to_check


def _load_ports() -> list[dict]:
    """Load all ports from UNLOCODE CSV files."""
    global _ports_cache
    if _ports_cache is not None:
        return _ports_cache

    csv_files = _find_csv_files()
    if not csv_files:
        logger.warning("No UNLOCODE CSV files found. Port lookup will use Geoapify only.")
        _ports_cache = []
        return _ports_cache

    ports = []
    for csv_path in csv_files:
        logger.info(f"Loading UNLOCODE data from: {csv_path}")
        try:
            with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) < 7:
                        continue
                    country = (row[COL_COUNTRY] or "").strip()
                    location_code = (row[COL_LOCATION] or "").strip()
                    name = (row[COL_NAME] or "").strip()
                    name_ascii = (row[COL_NAME_NODIACRITICS] or "").strip()

                    if not country or not name:
                        continue
                    if name.startswith("."):  # Country header row
                        continue

                    # Parse function codes
                    func_str = row[COL_FUNCTION].strip() if len(row) > COL_FUNCTION else ""
                    functions = []
                    for i, label in FUNCTION_LABELS.items():
                        if i < len(func_str) and func_str[i] != "-":
                            functions.append(label)

                    is_port = "Port" in functions
                    is_airport = "Airport" in functions

                    # Parse coordinates
                    coords_str = row[COL_COORDINATES].strip() if len(row) > COL_COORDINATES else ""
                    lat, lon = _parse_coordinates(coords_str)

                    ports.append({
                        "country_code": country,
                        "location_code": location_code,
                        "locode": f"{country}{location_code}",
                        "name": name,
                        "name_ascii": name_ascii or name,
                        "subdivision": (row[COL_SUBDIVISION] or "").strip() if len(row) > COL_SUBDIVISION else "",
                        "functions": functions,
                        "is_port": is_port,
                        "is_airport": is_airport,
                        "status": (row[COL_STATUS] or "").strip() if len(row) > COL_STATUS else "",
                        "coordinates": coords_str,
                        "lat": lat,
                        "lon": lon,
                        "iata": (row[COL_IATA] or "").strip() if len(row) > COL_IATA else "",
                    })
        except Exception as e:
            logger.error(f"Error loading {csv_path}: {e}")

    _ports_cache = ports
    logger.info(f"Loaded {len(ports)} UNLOCODE locations from {len(csv_files)} files")
    return _ports_cache


def _parse_coordinates(coords: str) -> tuple[float | None, float | None]:
    """Parse UNLOCODE coordinate format like '4230N 00131E' to lat/lon."""
    if not coords or len(coords) < 10:
        return None, None
    try:
        parts = coords.strip().split()
        if len(parts) != 2:
            return None, None

        lat_str, lon_str = parts
        lat_deg = int(lat_str[:2])
        lat_min = int(lat_str[2:4])
        lat_dir = lat_str[-1]
        lat = lat_deg + lat_min / 60.0
        if lat_dir in ("S", "s"):
            lat = -lat

        lon_deg = int(lon_str[:3])
        lon_min = int(lon_str[3:5])
        lon_dir = lon_str[-1]
        lon = lon_deg + lon_min / 60.0
        if lon_dir in ("W", "w"):
            lon = -lon

        return lat, lon
    except (ValueError, IndexError):
        return None, None


def search_port(query: str, country_code: str = "", ports_only: bool = False,
                max_results: int = 10) -> list[dict]:
    """Search for ports/locations by name. Case-insensitive partial match."""
    ports = _load_ports()
    if not ports:
        return []

    q = query.lower().strip()
    results = []

    for p in ports:
        if ports_only and not p["is_port"]:
            continue
        if country_code and p["country_code"].upper() != country_code.upper():
            continue

        name_lower = p["name_ascii"].lower()
        name_orig = p["name"].lower()

        # Exact match gets highest priority
        if name_lower == q or name_orig == q:
            results.insert(0, {**p, "_score": 100})
        # Starts with query
        elif name_lower.startswith(q) or name_orig.startswith(q):
            results.append({**p, "_score": 80})
        # Contains query
        elif q in name_lower or q in name_orig:
            results.append({**p, "_score": 60})
        # LOCODE match
        elif q.upper() == p["locode"] or q.upper() == p["location_code"]:
            results.insert(0, {**p, "_score": 100})

    # Sort by score then by is_port (prefer ports)
    results.sort(key=lambda x: (-x.get("_score", 0), -int(x["is_port"])))

    # Clean up score
    for r in results:
        r.pop("_score", None)

    return results[:max_results]


def get_port_by_code(country_code: str, location_code: str) -> dict | None:
    """Get a specific port by its country + location code (e.g., LY + TIP)."""
    ports = _load_ports()
    cc = country_code.upper()
    lc = location_code.upper()
    for p in ports:
        if p["country_code"] == cc and p["location_code"] == lc:
            return p
    return None


def get_ports_count() -> int:
    """Get total number of loaded locations."""
    return len(_load_ports())
