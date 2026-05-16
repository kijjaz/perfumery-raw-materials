#!/usr/bin/env python3
"""
Scraper for new PerfumersWorld raw materials.
Fetches product details for each new SKU and produces a Google Sheets-ready CSV.

New items found after cutoff SKU: 6WX24054 (Sandalwood Base X3)
"""

import csv
import re
import ssl
import time
import urllib.request
from html.parser import HTMLParser

# ─────────────────────────────────────────────────
# New SKUs to scrape (from the What's New page)
# listed in order they appear AFTER the cutoff 6WX24054
# ─────────────────────────────────────────────────
NEW_SKUS = [
    "7RB00837",   # Geranium Oil Egypt
    "6CN24668",   # Petigrain Bigarade
    "8CS23654",   # Nepal Pepper Co2 Extract
    "8FY24655",   # Caribbean Rum Extract
    "8IQ24653",   # Orris Liquid
    "7SL24626",   # Jungle Pepper Oil
    "7CK24631",   # Key Lime Oil Egypt
    "7PL24627",   # Basil Linalool Oil Egypt
    "4WX24656",   # Hindinol
    # 6WX24054 is the cutoff — everything above is new
    # The items below were already in the existing CSV
    # "4WF06853",  # Aphermate – check existing CSV
    # "4GI24147",  # Liffarome – etc.
]

# SKUs that appear on What's New page AFTER 6WX24054
# (everything from 4WF06853 onwards is OLDER than our cutoff or needs checking)
# Let's include all that appeared between 6WX24055-onwards on the page, 
# and the ones right after 6WX24054:
# The page order from top = newest first, so items ABOVE 6WX24054 are newer.

BASE_URL = "https://www.perfumersworld.com"
SUPPLIER = "PerfumersWorld"

# SSL context that skips verification (needed for some environments)
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


def fetch(url: str, retries: int = 3) -> str:
    """Fetch a URL and return the HTML content."""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; PerfumeScraper/1.0)"},
            )
            with urllib.request.urlopen(req, context=SSL_CTX, timeout=15) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            print(f"  [ERROR] Attempt {attempt+1}/{retries}: {e}")
            time.sleep(3)
    return ""


# ── HTML helpers ───────────────────────────────────────────────────────────────

class TextExtractor(HTMLParser):
    """Strips all HTML tags, returns plain text."""

    def __init__(self):
        super().__init__()
        self.parts = []
        self._skip_tags = {"script", "style"}
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._skip_tags:
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in self._skip_tags and self._skip > 0:
            self._skip -= 1

    def handle_data(self, data):
        if self._skip == 0:
            self.parts.append(data)

    def get_text(self):
        return " ".join(self.parts)


def strip_html(html: str) -> str:
    p = TextExtractor()
    p.feed(html)
    return p.get_text()


# ── Price extraction ────────────────────────────────────────────────────────────

PRICE_RE = re.compile(
    r"US\$\s*([\d,.]+)\s*/\s*gram",
    re.IGNORECASE,
)


def extract_price(html: str) -> str:
    m = PRICE_RE.search(html)
    if m:
        price_str = m.group(1).replace(",", "").strip()
        try:
            return str(float(price_str))
        except ValueError:
            return price_str
    return ""


# ── Product name extraction ─────────────────────────────────────────────────────

def extract_product_name(html: str, sku: str) -> str:
    """Try to find the canonical product name from the product detail page."""
    # Look for <h1> or <title> with the product name
    h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.IGNORECASE | re.DOTALL)
    if h1_match:
        name = strip_html(h1_match.group(1)).strip()
        if name and sku not in name:
            return name

    # Fallback: look for title tag
    title_match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if title_match:
        title = strip_html(title_match.group(1)).strip()
        # PW titles are like "Product Name | PerfumersWorld"
        if "|" in title:
            name = title.split("|")[0].strip()
            if name:
                return name

    return ""


# ── CAS extraction from SDS page ───────────────────────────────────────────────

CAS_RE = re.compile(
    r"(?:Cas\s*no\.?|CAS[-\s]?No\.?|CAS\s*Number)[:\s]*([\d]{2,7}-\d{2}-\d)",
    re.IGNORECASE,
)
CAS_GENERIC_RE = re.compile(r"\b(\d{2,7}-\d{2}-\d)\b")
CAS_MIXTURE_RE = re.compile(r"Cas\s*no\.?\s*:\s*Mixture", re.IGNORECASE)


def cas_checksum_ok(cas: str) -> bool:
    """Validate a CAS number using its check digit algorithm."""
    try:
        parts = cas.split("-")
        if len(parts) != 3:
            return False
        digits = parts[0] + parts[1]
        check = int(parts[2])
        total = sum((i + 1) * int(d) for i, d in enumerate(reversed(digits)))
        return total % 10 == check
    except Exception:
        return False


def extract_cas_from_sds(html: str) -> str:
    """Extract and validate CAS numbers from the SDS page text."""
    text = strip_html(html)

    # Detect "Mixture" placeholder
    if CAS_MIXTURE_RE.search(text):
        return "Mixture"

    # Try labeled patterns first
    for m in CAS_RE.finditer(text):
        cas = m.group(1).strip()
        if cas_checksum_ok(cas):
            return cas

    # Fallback: generic CAS pattern with checksum validation
    for m in CAS_GENERIC_RE.finditer(text):
        cas = m.group(1).strip()
        if cas_checksum_ok(cas):
            return cas

    return ""


def get_sds_urls(doc_list_html: str) -> list[str]:
    """Extract document URLs from the document-list page."""
    urls = []
    for m in re.finditer(
        r'href=["\']([^"\']*(?:sds|msds|safety|document)[^"\']*)["\']',
        doc_list_html,
        re.IGNORECASE,
    ):
        url = m.group(1)
        if not url.startswith("http"):
            url = BASE_URL + url
        if url not in urls:
            urls.append(url)

    # Also grab all PDF/document links generically
    for m in re.finditer(r'href=["\']([^"\']+\.pdf[^"\']*)["\']', doc_list_html, re.IGNORECASE):
        url = m.group(1)
        if not url.startswith("http"):
            url = BASE_URL + url
        if url not in urls:
            urls.append(url)

    # Grab view page links that contain documents
    for m in re.finditer(
        r'href=["\']([^"\']*document-view[^"\']*)["\']', doc_list_html, re.IGNORECASE
    ):
        url = m.group(1)
        if not url.startswith("http"):
            url = BASE_URL + url
        if url not in urls:
            urls.append(url)

    return urls


def fetch_cas(sku: str) -> str:
    """Fetch CAS number for a given SKU from the document-list page."""
    print(f"  Fetching SDS for {sku} ...")
    doc_url = f"{BASE_URL}/document-list.php?pro_id={sku}"
    doc_html = fetch(doc_url)
    if not doc_html:
        return ""

    # First try extracting CAS directly from the document-list page text
    cas = extract_cas_from_sds(doc_html)
    if cas:
        return cas

    # Try each document linked from the page
    doc_urls = get_sds_urls(doc_html)
    for url in doc_urls[:5]:  # limit to first 5
        print(f"    Checking doc: {url}")
        content = fetch(url)
        if content:
            cas = extract_cas_from_sds(content)
            if cas:
                return cas
        time.sleep(1)

    return "Not Found"


# ── Dilution parsing ────────────────────────────────────────────────────────────

DILUTION_PATTERNS = [
    # "X% in SOLVENT"
    re.compile(
        r"(\d+(?:\.\d+)?)\s*%\s+in\s+(.+?)(?:\s+from\s+|\s*$)",
        re.IGNORECASE,
    ),
]


def parse_dilution(name: str) -> tuple[bool, str, str, str]:
    """
    Returns (is_dilution, active_material_name, solvent_name, active_pct_fraction).
    active_pct_fraction is a decimal like 0.1 for 10%.
    Solvent name returned is the raw text (without 'from PerfumersWorld' suffix).
    """
    for pat in DILUTION_PATTERNS:
        m = pat.search(name)
        if m:
            pct = float(m.group(1))
            solvent_raw = m.group(2).strip()
            # Remove the dilution portion to get the base name
            base_name = name[: m.start()].strip()
            # Clean trailing punctuation/whitespace
            base_name = re.sub(r"[\s,\-]+$", "", base_name).strip()
            return True, base_name, solvent_raw, str(round(pct / 100, 10)).rstrip("0").rstrip(".")
    return False, "", "", ""


# ── Solvent CAS lookup ─────────────────────────────────────────────────────────

KNOWN_SOLVENTS = {
    "DPG": ("25265-71-8", "Dipropylene Glycol (DPG)"),
    "Dipropylene Glycol": ("25265-71-8", "Dipropylene Glycol (DPG)"),
    "TEC": ("77-93-0", "Triethyl Citrate (TEC)"),
    "Triethyl Citrate": ("77-93-0", "Triethyl Citrate (TEC)"),
    "IPM": ("110-27-0", "Isopropyl Myristate (IPM)"),
    "Isopropyl Myristate": ("110-27-0", "Isopropyl Myristate (IPM)"),
    "BB": ("120-51-4", "Benzyl Benzoate (BB)"),
    "Benzyl Benzoate": ("120-51-4", "Benzyl Benzoate (BB)"),
    "DEP": ("84-66-2", "Diethyl Phthalate (DEP)"),
}


def resolve_solvent(solvent_raw: str) -> tuple[str, str]:
    """Return (solvent_cas, canonical_solvent_name)."""
    for key, (cas, canonical) in KNOWN_SOLVENTS.items():
        if key.lower() in solvent_raw.lower():
            return cas, canonical
    return "", solvent_raw


# ── SKU-prefix logic ────────────────────────────────────────────────────────────

def sku_is_base(sku: str) -> bool:
    return sku.startswith("6")


def sku_is_dilution_candidate(sku: str) -> bool:
    return sku.startswith("5")


# ── Main scrape function ────────────────────────────────────────────────────────

def scrape_sku(sku: str) -> dict:
    """
    Scrape a single SKU from PerfumersWorld and return a data dict.
    """
    print(f"\n[{sku}] Fetching product page ...")
    product_url = f"{BASE_URL}/view.php?pro_id={sku}"
    html = fetch(product_url)

    name = extract_product_name(html, sku) if html else ""
    price = extract_price(html) if html else ""

    # CAS handling
    if sku_is_base(sku):
        cas = "Mixture (Perfume Base)"
    else:
        time.sleep(1.5)
        cas = fetch_cas(sku)

    # Build the full material name with supplier suffix
    material_name = f"{name} from {SUPPLIER}" if name else f"{sku} from {SUPPLIER}"

    # Dilution detection
    is_dilution = False
    active_material = ""
    solvent = ""
    active_pct = ""
    cas_value = cas

    if sku_is_dilution_candidate(sku) and "%" in name:
        is_dilution_flag, base_name, solvent_raw, pct_fraction = parse_dilution(name)
        if is_dilution_flag:
            is_dilution = True
            active_material = f"{base_name} from {SUPPLIER}"
            solvent_cas, solvent_canonical = resolve_solvent(solvent_raw)
            solvent = f"{solvent_canonical} from {SUPPLIER}"
            active_pct = pct_fraction

            # Build multi-CAS string: active_cas|fraction\nsolvent_cas|fraction
            if cas and cas not in ("Not Found", "Mixture", "Mixture (Perfume Base)"):
                active_fraction = pct_fraction
                solvent_fraction = str(round(1.0 - float(active_fraction), 10)).rstrip("0").rstrip(".")
                if solvent_cas:
                    cas_value = f"{cas}|{active_fraction}\n{solvent_cas}|{solvent_fraction}"
                else:
                    cas_value = f"{cas}|{active_fraction}"
    else:
        is_dilution = sku_is_dilution_candidate(sku) and "%" in name

    return {
        "Product_ID": sku,
        "Material_Name": material_name,
        "CAS_Number": cas_value,
        "New CAS": "",
        "Price_US/g": price,
        "Notes": "",
        "Is_Dilution": "TRUE" if is_dilution else "FALSE",
        "Active_Material": active_material,
        "Solvent": solvent,
        "Active_%": active_pct,
    }


# ── Output ──────────────────────────────────────────────────────────────────────

OUTPUT_FILE = "new_raw_materials.csv"
FIELDNAMES = [
    "Product_ID",
    "Material_Name",
    "CAS_Number",
    "New CAS",
    "Price_US/g",
    "Notes",
    "Is_Dilution",
    "Active_Material",
    "Solvent",
    "Active_%",
]


def main():
    results = []
    for sku in NEW_SKUS:
        row = scrape_sku(sku)
        results.append(row)
        print(f"  -> {row}")
        time.sleep(2)  # polite delay between SKUs

    # Write to CSV
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(results)

    print(f"\nDone! Results written to: {OUTPUT_FILE}")
    print(f"Total new materials: {len(results)}")

    # Also print as TSV for easy copy-paste into Google Sheets
    print("\n" + "=" * 70)
    print("TSV OUTPUT (copy-paste directly into Google Sheets):")
    print("=" * 70)
    print("\t".join(FIELDNAMES))
    for row in results:
        parts = []
        for field in FIELDNAMES:
            val = str(row.get(field, ""))
            parts.append(val)
        print("\t".join(parts))


if __name__ == "__main__":
    main()
