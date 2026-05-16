#!/usr/bin/env python3
"""
MySkinRecipes Aroma Chemicals Scraper (Synthetics only)
========================================================
Scrapes the ส่วนประกอบ (Aroma Chemicals / components) category:
  https://www.myskinrecipes.com/shop/th/293-ส่วนประกอบ

Pages 1–N (found to be 86 pages). Each product page contains:
  - Product name
  - Price in THB (per quantity sold, often per unit weight)
  - CAS number (usually in the product description)

HTML is archived in html_cache/myskinrecipes/ for fast re-runs.

Output: myskinrecipes_20260317.csv
"""

import csv
import re
import ssl
import time
import urllib.request
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────────────────────

BASE_CAT_URL = (
    "https://www.myskinrecipes.com/shop/th/293-"
    "%E0%B8%AA%E0%B9%88%E0%B8%A7%E0%B8%99%E0%B8%9B%E0%B8%A3%E0%B8%B0%E0%B8%81%E0%B8%AD%E0%B8%9A"
)
BASE_URL   = "https://www.myskinrecipes.com"
OUT_FILE   = Path(__file__).parent / "myskinrecipes_20260317.csv"
HTML_CACHE = Path(__file__).parent / "html_cache" / "myskinrecipes"
HTML_CACHE.mkdir(parents=True, exist_ok=True)
DELAY      = 1.5
SUPPLIER   = "MySkinRecipes"

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode   = ssl.CERT_NONE
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; RawMaterialScraper/1.0)",
           "Accept-Language": "th-TH,th;q=0.9,en;q=0.8"}

# ── CAS checksum ───────────────────────────────────────────────────────────────

def cas_checksum_ok(cas: str) -> bool:
    m = re.match(r"^(\d+)-(\d{2})-(\d)$", cas)
    if not m:
        return False
    digits = m.group(1) + m.group(2)
    check  = int(m.group(3))
    total  = sum((i + 1) * int(d) for i, d in enumerate(reversed(digits)))
    return total % 10 == check

CAS_RE = re.compile(r"\b(\d{2,7}-\d{2}-\d)\b")

def extract_best_cas(text: str) -> str:
    found = [c for c in CAS_RE.findall(text) if cas_checksum_ok(c)]
    return found[0] if found else ""

# ── HTML cache ─────────────────────────────────────────────────────────────────

def _cache_path(url: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", url)[-150:]
    return HTML_CACHE / (safe + ".html")

def fetch(url: str, retries: int = 3) -> str:
    # Percent-encode non-ASCII chars (Thai slugs) — only if not already encoded
    if any(ord(c) > 127 for c in url):
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

# ── HTML helpers ───────────────────────────────────────────────────────────────

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
    def handle_data(self, d):
        self.parts.append(d)
    def get(self):
        return " ".join(self.parts)

def strip_html(html: str) -> str:
    te = TextExtractor()
    te.feed(html)
    return te.get()

# ── Catalogue page: extract product URLs ──────────────────────────────────────

PRODUCT_LINK_RE = re.compile(
    r'href="(https://www\.myskinrecipes\.com/shop/th/[^"]+\.html)"',
    re.IGNORECASE,
)

def get_product_links_from_page(url: str) -> list[str]:
    html = fetch(url)
    links = list(dict.fromkeys(PRODUCT_LINK_RE.findall(html)))   # dedup, preserve order
    return links

def get_all_product_links(max_pages: int = 100) -> list[str]:
    all_links: list[str] = []
    for page in range(1, max_pages + 1):
        url = BASE_CAT_URL + (f"?page={page}" if page > 1 else "")
        print(f"  Catalogue page {page}: {url}")
        links = get_product_links_from_page(url)
        if not links:
            print(f"  → no product links found, stopping at page {page - 1}")
            break
        new = [l for l in links if l not in all_links]
        all_links.extend(new)
        print(f"  → {len(new)} new links (total {len(all_links)})")
        time.sleep(DELAY)
    return all_links

# ── Parse a product page ───────────────────────────────────────────────────────

def parse_product(url: str) -> dict:
    html = fetch(url)
    text = strip_html(html)

    # ── Name: from <title> or <h1> ─────────────────────────────────────────
    m_title = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    name = m_title.group(1).strip() if m_title else ""
    # Remove the site name from the title (usually after " - " or " | ")
    name = re.sub(r"\s*[|–—-]\s*MySkinRecipes.*$", "", name, flags=re.I).strip()
    name = re.sub(r"&[a-z#0-9]+;", " ", name).strip()
    if not name:
        m_h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
        name = strip_html(m_h1.group(1)).strip() if m_h1 else ""

    # ── Product ID: from URL (numeric ID before dash-slug) ─────────────────
    m_id = re.search(r"/(\d+)-[^/]+\.html$", url)
    product_id = m_id.group(1) if m_id else ""

    # ── Price ──────────────────────────────────────────────────────────────
    # MySkinRecipes shows "฿ 250.00" or JSON price data
    price_thb = None
    # Try JSON-LD / meta first
    m_json = re.search(r'"price"\s*:\s*"?([\d.]+)"?', html)
    if m_json:
        price_thb = float(m_json.group(1))
    else:
        for pat in [r"฿\s*([\d,]+(?:\.\d+)?)", r"([\d,]+(?:\.\d+)?)\s*฿",
                    r"([\d,]+(?:\.\d+)?)\s*บาท"]:
            m = re.search(pat, text)
            if m:
                price_thb = float(m.group(1).replace(",", ""))
                break

    # ── Package size + price/g ─────────────────────────────────────────────
    # Look for weight sold: "ราคาต่อ 1 กรัม" or "ขายเป็น / x กรัม" or just extract from name
    grams = None
    m_g   = re.search(r"(\d+(?:\.\d+)?)\s*กรัม", text)
    if m_g:
        grams = float(m_g.group(1))
    else:
        m_g2  = re.search(r"(\d+(?:\.\d+)?)\s*g\b", text, re.I)
        if m_g2:
            grams = float(m_g2.group(1))
    package_size = f"{grams:.0f} g" if grams else ""

    price_per_g = None
    if price_thb and grams:
        price_per_g = round(price_thb / grams, 4)

    # ── CAS ────────────────────────────────────────────────────────────────
    cas = extract_best_cas(text)

    return {
        "Product_ID":      product_id,
        "Material_Name":   name,
        "Package_Size":    package_size,
        "CAS_Number":      cas,
        "New CAS":         "",
        "Price_THB_total": f"{price_thb:.2f}" if price_thb else "",
        "Price_THB/g":     f"{price_per_g:.4f}" if price_per_g else "",
        "Notes":           "",
        "Is_Dilution":     "",
        "Active_Material": "",
        "Solvent":         "",
        "Active_%":        "",
        "Supplier":        SUPPLIER,
        "Product_URL":     url,
    }

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("\n=== MySkinRecipes Scraper (Synthetics / ส่วนประกอบ) ===\n")

    print("[Step 1] Collecting product links from catalogue pages...")
    links = get_all_product_links(max_pages=100)
    print(f"\nTotal product links: {len(links)}")

    print("\n[Step 2] Scraping individual product pages...")
    rows = []
    for i, link in enumerate(links):
        row = parse_product(link)
        rows.append(row)
        status = f"  [{i+1}/{len(links)}] {row['Material_Name'][:55]}"
        if row["Price_THB/g"]:
            status += f"  ฿{row['Price_THB/g']}/g"
        if row["CAS_Number"]:
            status += f"  CAS:{row['CAS_Number']}"
        print(status)
        # Skip delay if served from cache
        cache_hit = _cache_path(link).exists()
        if not cache_hit:
            time.sleep(DELAY)

    fieldnames = [
        "Product_ID", "Material_Name", "Package_Size", "CAS_Number", "New CAS",
        "Price_THB_total", "Price_THB/g", "Notes",
        "Is_Dilution", "Active_Material", "Solvent", "Active_%",
        "Supplier", "Product_URL",
    ]
    with open(OUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    missing_cas   = sum(1 for r in rows if not r["CAS_Number"])
    missing_price = sum(1 for r in rows if not r["Price_THB/g"])
    print(f"""
=== Summary ===
  Total products : {len(rows)}
  Missing CAS    : {missing_cas}
  Missing price/g: {missing_price}
  Output         : {OUT_FILE}
""")

if __name__ == "__main__":
    main()
