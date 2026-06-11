#!/usr/bin/env python3
"""
PerfumersWorld Local HTML Processor (2026 Update)
Processes locally saved perfume-supplies.php and extracts:
- Name, SKU, Price (USD/g)
- CAS Number (from live SDS document-list)
- Dilution info (parsed from name)
"""

import csv
import re
import ssl
import time
import urllib.request
import os
from html.parser import HTMLParser
from typing import List, Dict, Tuple, Optional

# Constants
BASE_URL = "https://www.perfumersworld.com"
SUPPLIER = "PerfumersWorld"
INPUT_HTML = "20260401 Perfume Supplies _ PerfumersWorld.html"
OUTPUT_CSV = "perfumersworld_20260401_updated.csv"

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
                headers={"User-Agent": "Mozilla/5.0 (compatible; PerfumeScraper/2026.04)"},
            )
            with urllib.request.urlopen(req, context=SSL_CTX, timeout=20) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            print(f"  [ERROR] Attempt {attempt+1}/{retries} for {url}: {e}")
            time.sleep(2)
    return ""

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self._skip_tags = {"script", "style"}
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._skip_tags: self._skip += 1

    def handle_endtag(self, tag):
        if tag in self._skip_tags and self._skip > 0: self._skip -= 1

    def handle_data(self, data):
        if self._skip == 0: self.parts.append(data)

    def get_text(self):
        return " ".join(self.parts)

def strip_html(html: str) -> str:
    p = TextExtractor()
    p.feed(html)
    return p.get_text()

# --- CAS EXTRACTION ---

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
    # Find all potential matches and pick the first valid one
    for m in CAS_RE.finditer(text):
        cas = m.group(1).strip()
        if cas_checksum_ok(cas): return cas
    for m in CAS_GENERIC_RE.finditer(text):
        cas = m.group(1).strip()
        if cas_checksum_ok(cas): return cas
    return ""

def fetch_cas(sku: str) -> str:
    """Fetch CAS number by visiting the product's document list."""
    if sku.startswith("6"): return "Mixture (Perfume Base)"
    doc_url = f"{BASE_URL}/document-list.php?pro_id={sku}"
    doc_html = fetch(doc_url)
    if not doc_html: return "Not Found"

    cas = extract_cas_from_sds(doc_html)
    if cas: return cas

    # Check for PDF/Document links if not directly in doc_html
    doc_pattern = re.compile(r'href="([^"]*(?:sds|msds|safety|document-view)[^"]*)"', re.IGNORECASE)
    doc_urls = doc_pattern.findall(doc_html)
    for url in doc_urls[:3]: # check first 3 links
        full_url = url if url.startswith("http") else BASE_URL + "/" + url.lstrip("/")
        content = fetch(full_url)
        if content:
            cas = extract_cas_from_sds(content)
            if cas: return cas
    return "Not Found"

# --- DILUTION PARSING ---

DILUTION_PATTERNS = [
    re.compile(r"(\d+(?:\.\d+)?)\s*%\s+in\s+(.+?)(?:\s+from\s+|\s*$)", re.IGNORECASE),
]

KNOWN_SOLVENTS = {
    "DPG": ("25265-71-8", "Dipropylene Glycol (DPG)"),
    "TEC": ("77-93-0", "Triethyl Citrate (TEC)"),
    "IPM": ("110-27-0", "Isopropyl Myristate (IPM)"),
    "BB": ("120-51-4", "Benzyl Benzoate (BB)"),
    "DEP": ("84-66-2", "Diethyl Phthalate (DEP)"),
    "PG": ("57-55-6", "Propylene Glycol (PG)"),
    "Ethanol": ("64-17-5", "Ethanol"),
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

# --- LOCAL PROCESSING ---

def load_cas_cache(filepath: str) -> Dict[str, str]:
    """Load existing SKU -> CAS mapping from a previous CSV."""
    cache = {}
    if not os.path.exists(filepath):
        return cache
    print(f"Loading CAS cache from {filepath} ...")
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sku = row.get("Product_ID")
            cas = row.get("CAS_Number")
            if sku and cas and cas not in ("Not Found", "Mixture", ""):
                cache[sku] = cas
    return cache

def process_local_html(filepath: str) -> List[Dict]:
    """Parse the local HTML file for product data."""
    if not os.path.exists(filepath):
        print(f"[FATAL] Input file {filepath} not found.")
        return []
        
    with open(filepath, "r", encoding="utf-8") as f:
        html = f.read()
        
    print(f"Reading {filepath} ...")
    
    # We find all <tr> entries in the HTML to isolate each row
    tr_pattern = re.compile(r'<tr[^>]*>.*?</tr>', re.DOTALL | re.IGNORECASE)
    tr_blocks = tr_pattern.findall(html)
    
    products = []
    # Match product link (sku and name) and price (allowing flexible unit suffixes like grams? or 0)
    link_pattern = re.compile(
        r'href="[^"]*view\.php\?pro_id=([^"&]+)"[^>]*title="([^"]+)"',
        re.IGNORECASE
    )
    price_pattern = re.compile(
        r'@\s*US\$\s*([\d,.]+)\s*/\s*([a-zA-Z0-9]+)',
        re.IGNORECASE
    )
    
    for block in tr_blocks:
        link_match = link_pattern.search(block)
        price_match = price_pattern.search(block)
        
        if link_match and price_match:
            sku = link_match.group(1).strip()
            name = link_match.group(2).strip()
            price = price_match.group(1).replace(",", "").strip()
            
            products.append({
                "Product_ID": sku,
                "Material_Name": name,
                "Price_US/g": price
            })
            
    return products

def main():
    # Load cache from the most recent previous run
    PREVIOUS_CSV = "perfumersworld_20260329.csv"
    cas_cache = load_cas_cache(PREVIOUS_CSV)
    print(f"Loaded {len(cas_cache)} CAS numbers from cache.")

    discovery = process_local_html(INPUT_HTML)
    print(f"Total products found in HTML: {len(discovery)}")
    
    if not discovery:
        return

    fieldnames = [
        "Product_ID", "Material_Name", "Supplier", "CAS_Number", "New CAS", 
        "Price_US/g", "Notes", "Is_Dilution", "Active_Material", "Solvent", "Active_%", "Source_URL"
    ]
    
    print(f"Processing details. Fetching missing CAS numbers...")
    
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for i, item in enumerate(discovery):
            sku = item["Product_ID"]
            name = item["Material_Name"]
            price_usd = item["Price_US/g"]
            
            # Print progress every 10 items or at start/end
            if i == 0 or (i + 1) % 10 == 0 or (i + 1) == len(discovery):
                print(f"[{i+1}/{len(discovery)}] Processing {sku}: {name} ...")
            
            # CAS extraction (Check Cache first)
            if sku in cas_cache:
                cas = cas_cache[sku]
            else:
                cas = fetch_cas(sku)
                # If we were processing dilutions, simple cache might not have the multi-line CAS
                # But for the purpose of speed, this is a good first pass.
                # Actually, our cache load handles multi-line CAS because it reads the whole column.
            
            # Dilution parsing
            dilution = parse_dilution(name)
            
            material_name = f"{name} from {SUPPLIER}"
            cas_value = cas
            
            # Multi-CAS logic for dilutions (if not already handled by cache)
            # If the cached value already looks like a multi-line entry (contains | or \n), skip re-generating
            if dilution["Is_Dilution"] == "TRUE" and "|" not in cas_value:
                active_pct = dilution["Active_%"]
                solvent_cas = dilution["Solvent_CAS"]
                if cas and cas not in ("Not Found", "Mixture", "Mixture (Perfume Base)"):
                    if solvent_cas:
                        try:
                           # Extract the base CAS from cached multi-line or single CAS
                           base_cas = cas.split("|")[0].split("\n")[0].strip()
                           solvent_pct = str(round(1.0 - float(active_pct), 10)).rstrip("0").rstrip(".")
                           cas_value = f"{base_cas}|{active_pct}\n{solvent_cas}|{solvent_pct}"
                        except:
                           cas_value = f"{cas}|{active_pct}"
                    else:
                        cas_value = f"{cas}|{active_pct}"

            row = {
                "Product_ID": sku,
                "Material_Name": material_name,
                "Supplier": SUPPLIER,
                "CAS_Number": cas_value,
                "New CAS": "",
                "Price_US/g": price_usd,
                "Notes": "",
                "Is_Dilution": dilution["Is_Dilution"],
                "Active_Material": dilution["Active_Material"],
                "Solvent": dilution["Solvent"],
                "Active_%": dilution["Active_%"],
                "Source_URL": f"{BASE_URL}/view.php?pro_id={sku}"
            }
            writer.writerow(row)
            
            # Delay only if we actually fetched from web
            if sku not in cas_cache and (i + 1) % 5 == 0:
                time.sleep(1)
                
        print(f"\nDone! Processed {len(discovery)} items.")

    print(f"Final data saved to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
