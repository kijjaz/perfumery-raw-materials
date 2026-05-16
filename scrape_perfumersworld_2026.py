#!/usr/bin/env python3
"""
PerfumersWorld Bulk Scraper (2026 Update)
Discovers all products from perfume-supplies.php and extracts:
- Name, SKU, Price
- CAS Number (from SDS document-list)
- Dilution info (parsed from name)
"""

import csv
import re
import ssl
import time
import urllib.request
from html.parser import HTMLParser
from typing import List, Dict, Tuple, Optional

BASE_URL = "https://www.perfumersworld.com"
LIST_URL = f"{BASE_URL}/perfume-supplies.php"
SUPPLIER = "PerfumersWorld"

# SSL context that skips verification
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

def fetch(url: str, retries: int = 3) -> str:
    """Fetch a URL and return the HTML content."""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; PerfumeScraper/2026.03)"},
            )
            with urllib.request.urlopen(req, context=SSL_CTX, timeout=20) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            print(f"  [ERROR] Attempt {attempt+1}/{retries} for {url}: {e}")
            time.sleep(2)
    return ""

# --- HTML Processing ---

class TextExtractor(HTMLParser):
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

# --- SKU Discovery ---

def discover_skus() -> List[Dict]:
    """Scrape the main list page for all products."""
    print(f"Discovering SKUs from {LIST_URL} ...")
    html = fetch(LIST_URL)
    if not html:
        return []

    products = []
    # Pattern: [Name](view.php?pro_id=SKU) followed by [SKU @ US$Price/gram](...)
    # Example: [Evening Primrose Oil - Fixed Oil](https://www.perfumersworld.com/view.php?pro_id=0ZA01393)
    # [0ZA01393 @ US$0.25/gram](https://www.perfumersworld.com/view.php?pro_id=0ZA01393)
    
    # Let's find all view.php?pro_id= links
    matches = re.findall(r'href="(view\.php\?pro_id=([^"]+))"[^>]*>([^<]+)</a>', html)
    
    sku_map = {} # sku -> {"name": name, "price": price}
    
    for link, sku, text in matches:
        text = text.strip()
        if not text: continue
        
        if sku not in sku_map:
            sku_map[sku] = {"Product_ID": sku, "Material_Name": text, "Price_US/g": ""}
        
        # Check if text contains price info: "0ZA01393 @ US$0.25/gram"
        price_match = re.search(r"US\$\s*([\d,.]+)\s*/\s*gram", text, re.IGNORECASE)
        if price_match:
            price = price_match.group(1).replace(",", "")
            sku_map[sku]["Price_US/g"] = price
        else:
            # If it doesn't have price, it's likely the name
            # Only update name if it doesn't look like a SKU repeated
            if text != sku:
                sku_map[sku]["Material_Name"] = text

    return list(sku_map.values())

# --- Detail Extraction (CAS, SDS, Dilutions) ---

CAS_RE = re.compile(
    r"(?:Cas\s*no\.?|CAS[-\s]?No\.?|CAS\s*Number)[:\s]*([\d]{2,7}-\d{2}-\d)",
    re.IGNORECASE,
)
CAS_GENERIC_RE = re.compile(r"\b(\d{2,7}-\d{2}-\d)\b")
CAS_MIXTURE_RE = re.compile(r"Cas\s*no\.?\s*:\s*Mixture", re.IGNORECASE)

def cas_checksum_ok(cas: str) -> bool:
    try:
        parts = cas.split("-")
        if len(parts) != 3: return False
        digits = parts[0] + parts[1]
        check = int(parts[2])
        total = sum((i + 1) * int(d) for i, d in enumerate(reversed(digits)))
        return total % 10 == check
    except: return False

def extract_cas_from_sds(html: str) -> str:
    text = strip_html(html)
    if CAS_MIXTURE_RE.search(text): return "Mixture"
    for m in CAS_RE.finditer(text):
        cas = m.group(1).strip()
        if cas_checksum_ok(cas): return cas
    for m in CAS_GENERIC_RE.finditer(text):
        cas = m.group(1).strip()
        if cas_checksum_ok(cas): return cas
    return ""

def fetch_cas(sku: str) -> str:
    if sku.startswith("6"): return "Mixture (Perfume Base)"
    doc_url = f"{BASE_URL}/document-list.php?pro_id={sku}"
    doc_html = fetch(doc_url)
    if not doc_html: return "Not Found"

    cas = extract_cas_from_sds(doc_html)
    if cas: return cas

    # Check for PDF links
    doc_pattern = re.compile(r'href="([^"]*(?:sds|msds|safety|document-view)[^"]*)"', re.IGNORECASE)
    doc_urls = doc_pattern.findall(doc_html)
    for url in doc_urls[:3]:
        if not url.startswith("http"): url = BASE_URL + url
        content = fetch(url)
        if content:
            cas = extract_cas_from_sds(content)
            if cas: return cas
    return "Not Found"

# --- Dilution Parsing ---

DILUTION_PATTERNS = [
    re.compile(r"(\d+(?:\.\d+)?)\s*%\s+in\s+(.+?)(?:\s+from\s+|\s*$)", re.IGNORECASE),
]

KNOWN_SOLVENTS = {
    "DPG": ("25265-71-8", "Dipropylene Glycol (DPG)"),
    "TEC": ("77-93-0", "Triethyl Citrate (TEC)"),
    "IPM": ("110-27-0", "Isopropyl Myristate (IPM)"),
    "BB": ("120-51-4", "Benzyl Benzoate (BB)"),
    "DEP": ("84-66-2", "Diethyl Phthalate (DEP)"),
}

def parse_dilution(name: str) -> dict:
    for pat in DILUTION_PATTERNS:
        m = pat.search(name)
        if m:
            pct_val = float(m.group(1))
            solvent_raw = m.group(2).strip()
            base_name = name[:m.start()].strip().rstrip(" ,-")
            
            solvent_cas = ""
            solvent_canonical = solvent_raw
            for key, (cas, canonical) in KNOWN_SOLVENTS.items():
                if key.lower() in solvent_raw.lower():
                    solvent_cas = cas
                    solvent_canonical = canonical
                    break
            
            return {
                "Is_Dilution": "TRUE",
                "Active_Material": f"{base_name} from {SUPPLIER}",
                "Solvent": f"{solvent_canonical} from {SUPPLIER}",
                "Active_%": str(round(pct_val / 100, 10)).rstrip("0").rstrip("."),
                "Solvent_CAS": solvent_cas
            }
    return {"Is_Dilution": "FALSE", "Active_Material": "", "Solvent": "", "Active_%": "", "Solvent_CAS": ""}

# --- Main ---

def main():
    discovery = discover_skus()
    print(f"Total SKUs discovered: {len(discovery)}")
    
    output_file = "perfumersworld_20260329.csv"
    fieldnames = [
        "Product_ID", "Material_Name", "CAS_Number", "New CAS", "Price_US/g", 
        "Notes", "Is_Dilution", "Active_Material", "Solvent", "Active_%"
    ]
    
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for i, item in enumerate(discovery):
            sku = item["Product_ID"]
            name = item["Material_Name"]
            price = item["Price_US/g"]
            
            print(f"[{i+1}/{len(discovery)}] Processing {sku}: {name} ...")
            
            # CAS extraction
            cas = fetch_cas(sku)
            
            # Dilution parsing
            dilution = parse_dilution(name)
            
            material_name = f"{name} from {SUPPLIER}"
            cas_value = cas
            
            # If it's a dilution, handle multi-CAS format
            if dilution["Is_Dilution"] == "TRUE":
                active_pct = dilution["Active_%"]
                solvent_cas = dilution["Solvent_CAS"]
                if cas and cas not in ("Not Found", "Mixture", "Mixture (Perfume Base)"):
                    if solvent_cas:
                        solvent_pct = str(round(1.0 - float(active_pct), 10)).rstrip("0").rstrip(".")
                        cas_value = f"{cas}|{active_pct}\n{solvent_cas}|{solvent_pct}"
                    else:
                        cas_value = f"{cas}|{active_pct}"

            row = {
                "Product_ID": sku,
                "Material_Name": material_name,
                "CAS_Number": cas_value,
                "New CAS": "",
                "Price_US/g": price,
                "Notes": "",
                "Is_Dilution": dilution["Is_Dilution"],
                "Active_Material": dilution["Active_Material"],
                "Solvent": dilution["Solvent"],
                "Active_%": dilution["Active_%"],
            }
            writer.writerow(row)
            
            # Polite delay
            if (i + 1) % 5 == 0:
                time.sleep(1)

    print(f"Done! Data saved to {output_file}")

if __name__ == "__main__":
    main()
