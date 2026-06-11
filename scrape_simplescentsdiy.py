#!/usr/bin/env python3
"""
SimpleScentsDIY Scraper
========================
Scrapes product name, SKU, price, and CAS number from SimpleScentsDIY
for the following categories:
  - Naturals (น้ำมันหอมระเหย)
  - Aroma Chemicals
  - Specialty Bases
  - Alcohol & Solvents

Prices are listed per package volume (e.g. "15 ml", "5 ml", "1 oz", "2 g").
We record:
  - Price_THB_total : the listed price in THB
  - Package_size    : e.g. "15 ml" — you can normalise to per-gram manually
  - Price_THB/g     : computed if we can deduce grams (ml≈g for most aroma chems)

Output: simplescentsdiy_20260317.csv
"""

import csv
import re
import ssl
import time
import urllib.request
import urllib.parse
import json
from html.parser import HTMLParser
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

CATEGORY_URLS = [
    ("Naturals",
     "https://www.simplescentsdiy.com/category/4201/1432/"
     "%E0%B8%99%E0%B9%89%E0%B8%B3%E0%B8%A1%E0%B8%B1%E0%B8%99%E0%B8%AB%E0%B8%AD%E0%B8%A1%E0%B8%A3%E0%B8%B0%E0%B9%80%E0%B8%AB%E0%B8%A2"),
    ("Aroma Chemicals",
     "https://www.simplescentsdiy.com/category/4667/1493/aroma-chemicals"),
    ("Specialty Bases",
     "https://www.simplescentsdiy.com/category/4667/1513/specialty-base"),
    ("Alcohol & Solvents",
     "https://www.simplescentsdiy.com/category/4204/"
     "%E0%B9%81%E0%B8%AD%E0%B8%A5%E0%B8%81%E0%B8%AD%E0%B8%AE%E0%B8%AD%E0%B8%A5%E0%B8%A5%E0%B9%8C%E0%B8%AA%E0%B8%B2%E0%B8%A3%E0%B8%97%E0%B8%B3%E0%B8%A5%E0%B8%B0%E0%B8%A5%E0%B8%B2%E0%B8%A2"),
]

OUT_FILE   = Path(__file__).parent / "simplescentsdiy_20260317.csv"
HTML_CACHE = Path(__file__).parent / "html_cache" / "simplescentsdiy"
HTML_CACHE.mkdir(parents=True, exist_ok=True)
DELAY      = 1.5   # seconds between requests
SUPPLIER   = "SimpleScentsDIY"
BASE_URL   = "https://www.simplescentsdiy.com"

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode   = ssl.CERT_NONE

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; RawMaterialScraper/1.0)"}

# ── Volume → grams conversion ─────────────────────────────────────────────────
# ml≈g for most aroma chems (density ≈ 1.0 g/ml); 1 oz = 29.5735 g

def volume_to_grams(size_str: str) -> float | None:
    """Convert '15 ml', '1 oz', '2 g', '5 ml' → float grams. None if unknown."""
    s = size_str.strip().lower()
    m = re.match(r"([\d.]+)\s*(ml|g|oz)", s)
    if not m:
        return None
    qty, unit = float(m.group(1)), m.group(2)
    if unit == "g":
        return qty
    if unit == "ml":
        return qty          # approx
    if unit == "oz":
        return qty * 29.5735
    return None

# ── HTML Parsers ──────────────────────────────────────────────────────────────

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
    def handle_data(self, data):
        self.text.append(data)
    def get_text(self):
        return " ".join(self.text)

class ProductLinkParser(HTMLParser):
    """Extracts /product/... links from a category page."""
    def __init__(self):
        super().__init__()
        self.links: list[str] = []
        self._current_href = None
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            attrs_d = dict(attrs)
            href = attrs_d.get("href", "")
            if "/product/" in href and href not in self.links:
                full = href if href.startswith("http") else BASE_URL + href
                self.links.append(full)

class ProductDetailParser(HTMLParser):
    """Extracts name, SKU, price, CAS from a product detail page."""
    def __init__(self):
        super().__init__()
        self.name   = ""
        self.sku    = ""
        self.price  = None   # THB float
        self.cas    = ""
        self._in_price   = False
        self._in_name    = False
        self._tag_depth  = 0
        self._text_buf   = []
        self._all_text   = []

    def handle_data(self, data):
        self._all_text.append(data)
        if self._in_price or self._in_name:
            self._text_buf.append(data)

    def get_full_text(self):
        return "\n".join(self._all_text)

def _cache_path(url: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", url)[-150:]
    return HTML_CACHE / (safe + ".html")

def fetch(url: str, retries: int = 3) -> str:
    # Percent-encode any non-ASCII characters in the path (Thai slugs etc.)
    try:
        parsed = urllib.parse.urlsplit(url)
        encoded_path = urllib.parse.quote(parsed.path, safe="/:@!$&'()*+,;=")
        url = urllib.parse.urlunsplit(parsed._replace(path=encoded_path))
    except Exception:
        pass
    cp = _cache_path(url)
    if cp.exists():
        return cp.read_text(encoding="utf-8", errors="replace")
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, context=SSL_CTX, timeout=20) as r:
                raw = r.read()
                try:
                    text = raw.decode("utf-8")
                except UnicodeDecodeError:
                    text = raw.decode("tis-620", errors="replace")
                cp.write_text(text, encoding="utf-8")
                return text
        except Exception as e:
            print(f"  [fetch error attempt {attempt+1}] {url}: {e}")
            time.sleep(3)
    return ""

def get_product_links(category_url: str) -> list[str]:
    html = fetch(category_url)
    parser = ProductLinkParser()
    parser.feed(html)
    # Deduplicate preserving order
    seen = set()
    out = []
    for link in parser.links:
        if link not in seen:
            seen.add(link)
            out.append(link)
    return out

def parse_product_page(url: str) -> dict:
    html = fetch(url)
    te = TextExtractor()
    te.feed(html)
    text = te.get_text()

    # Try parsing JSON-LD first
    json_ld_data = None
    scripts = re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL | re.IGNORECASE)
    if not scripts:
        scripts = [s for s in re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL) if 'schema.org' in s]
    
    for s in scripts:
        try:
            data = json.loads(s.strip())
            if isinstance(data, dict) and data.get('@type') == 'Product':
                json_ld_data = data
                break
        except Exception:
            pass

    sku = ""
    material_name = ""
    package_size = ""
    price_thb = None
    cas = ""

    if json_ld_data:
        # Extract from JSON-LD
        sku = json_ld_data.get('sku', '').strip()
        full_name = json_ld_data.get('name', '').strip()
        
        # Clean name & extract size
        # Remove HTML entities
        full_name = re.sub(r"&[a-z]+;", " ", full_name).strip()
        size_match = re.search(r"(\d+(?:\.\d+)?\s*(?:ml|g|oz))", full_name, re.IGNORECASE)
        package_size = size_match.group(1).strip() if size_match else ""
        material_name = re.sub(r"\s*\d+(?:\.\d+)?\s*(?:ml|g|oz)\b", "", full_name, flags=re.IGNORECASE).strip()
        
        # Extract price
        price_val = json_ld_data.get('offers', {}).get('price')
        if price_val:
            try:
                price_thb = float(price_val)
            except ValueError:
                pass
                
        # Extract CAS from description
        desc = json_ld_data.get('description', '')
        m_cas = re.search(r'CAS\s*(?:No\.?)?\s*:\s*(\d{2,7}-\d{2}-\d)', desc, re.IGNORECASE)
        if m_cas:
            cas = m_cas.group(1).strip()

    # Fallback to older text parsing for any empty fields
    if not sku:
        m = re.search(r"SKU\s*:\s*([A-Z0-9]+)", text)
        if m:
            sku = m.group(1).strip()
        if not sku:
            m2 = re.search(r"/product/(\d+)-", url)
            if m2:
                sku = m2.group(1)

    if not material_name:
        m_title = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        raw_title = m_title.group(1) if m_title else ""
        name = raw_title.strip()
        if ":" in name:
            name = name.split(":", 1)[1].strip()
        name = re.sub(r"&[a-z]+;", " ", name).strip()
        
        size_match = re.search(r"(\d+(?:\.\d+)?\s*(?:ml|g|oz))", name, re.IGNORECASE)
        package_size = size_match.group(1).strip() if size_match else ""
        material_name = re.sub(r"\s*\d+(?:\.\d+)?\s*(?:ml|g|oz)\b", "", name, flags=re.IGNORECASE).strip()

    if price_thb is None:
        patterns = [
            r"฿\s*([\d,]+(?:\.\d+)?)",
            r"([\d,]+(?:\.\d+)?)\s*฿",
            r"ราคา\s*([\d,]+(?:\.\d+)?)\s*บาท",
            r"([\d,]+(?:\.\d+)?)\s*บาท",
        ]
        for p in patterns:
            m = re.search(p, text)
            if m:
                price_thb = float(m.group(1).replace(",", ""))
                break

    if not cas:
        m_cas = re.search(r"[Cc]as\s*[Nn]o\.?\s*:?\s*(\d{2,7}-\d{2}-\d)", text)
        if m_cas:
            cas = m_cas.group(1).strip()

    # ── Price per gram ───────────────────────────────────────────────────────
    grams = volume_to_grams(package_size) if package_size else None
    price_per_g = None
    if price_thb and grams:
        price_per_g = round(price_thb / grams, 4)

    return {
        "Product_ID":    sku,
        "Material_Name": material_name,
        "Package_Size":  package_size,
        "CAS_Number":    cas,
        "New CAS":       "",
        "Price_THB_total": f"{price_thb:.2f}" if price_thb else "",
        "Price_THB/g":   f"{price_per_g:.4f}" if price_per_g else "",
        "Notes":         "",
        "Is_Dilution":   "",
        "Active_Material": "",
        "Solvent":       "",
        "Active_%":      "",
        "Supplier":      SUPPLIER,
        "Product_URL":   url,
    }

def main():
    print("\n=== SimpleScentsDIY Scraper ===\n")
    all_rows = []

    for category_name, cat_url in CATEGORY_URLS:
        print(f"\n[Category] {category_name}")
        links = get_product_links(cat_url)
        print(f"  → {len(links)} product links found")
        time.sleep(DELAY)

        for i, link in enumerate(links):
            row = parse_product_page(link)
            all_rows.append(row)
            status = f"  [{i+1}/{len(links)}] {row['Material_Name'][:50]}"
            if row['Price_THB/g']:
                status += f"  ฿{row['Price_THB/g']}/g"
            if row['CAS_Number']:
                status += f"  CAS:{row['CAS_Number']}"
            print(status)
            time.sleep(DELAY)

    # Write CSV
    fieldnames = [
        "Product_ID", "Material_Name", "Package_Size", "CAS_Number", "New CAS",
        "Price_THB_total", "Price_THB/g", "Notes",
        "Is_Dilution", "Active_Material", "Solvent", "Active_%",
        "Supplier", "Product_URL",
    ]
    with open(OUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\n✓ Written {len(all_rows)} rows → {OUT_FILE}")

if __name__ == "__main__":
    main()
