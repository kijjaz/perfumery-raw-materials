#!/usr/bin/env python3
"""
PerfumersWorld Price & Availability Updater
============================================
Scrapes ALL product prices from perfumersworld.com/perfume-supplies.php
and compares against the existing RawMaterials_Enriched.csv to produce:

  1. price_update_20260317.csv
     - All rows from existing CSV, with:
       * Updated Price_US/g (if changed)
       * Availability: "Available" | "Not Listed" (removed from shop)
       * Price_Change: e.g. "+0.10", "-0.05", "NEW", "REMOVED", "unchanged"

  2. price_changes_only_20260317.csv
     - Only rows where price changed or item was removed/added

Usage:
    python3 update_prices.py

Output files are written next to this script.
"""

import csv
import re
import ssl
import time
import urllib.request
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

SUPPLIES_URL = "https://www.perfumersworld.com/perfume-supplies.php"
EXISTING_CSV = Path("/Users/kijjaz/Desktop/Antigravity/2026/20260104 CAS Number Check/RawMaterials_Enriched.csv")
OUT_DIR      = Path(__file__).parent
OUT_ALL      = OUT_DIR / "price_update_20260317.csv"
OUT_CHANGES  = OUT_DIR / "price_changes_only_20260317.csv"

# ── SSL (bypass cert check for environments where it fails) ──────────────────

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode   = ssl.CERT_NONE


def fetch(url: str, retries: int = 3) -> str:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; PWPriceScraper/1.0)"},
            )
            with urllib.request.urlopen(req, context=SSL_CTX, timeout=20) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:
            print(f"  [fetch error attempt {attempt+1}] {e}")
            time.sleep(3)
    return ""


# ── Parse the supplies page ────────────────────────────────────────────────────
# Format on the page:
#   [Product Name](https://...view.php?pro_id=XXXXXXXX)
#   [XXXXXXXX @ US$0.29/gram](https://...view.php?pro_id=XXXXXXXX)

PRICE_LINE_RE = re.compile(
    r"([0-9][A-Z0-9]{7})\s*@\s*US\$([\d.]+)/gram",
    re.IGNORECASE,
)

# Raw-material SKUs start with a digit 0-9
RAW_MATERIAL_RE = re.compile(r"^[0-9][A-Z0-9]{7}$")


def scrape_all_prices() -> dict[str, float]:
    """Return {SKU: price_float} for every raw material on the supplies page."""
    print(f"Fetching: {SUPPLIES_URL}")
    html = fetch(SUPPLIES_URL)
    if not html:
        raise RuntimeError("Failed to fetch supplies page.")

    prices: dict[str, float] = {}
    for m in PRICE_LINE_RE.finditer(html):
        sku   = m.group(1).upper()
        price = float(m.group(2))
        if RAW_MATERIAL_RE.match(sku):
            prices[sku] = price

    print(f"  → Found {len(prices)} priced raw-material SKUs on site.")
    return prices


# ── Load existing CSV ─────────────────────────────────────────────────────────

FIELDNAMES = [
    "Product_ID", "Material_Name", "CAS_Number", "Price_US/g",
    "Notes", "Is_Dilution", "Active_Material", "Solvent", "Active_%",
]

OUT_FIELDNAMES = FIELDNAMES + ["Availability", "Price_Change"]


def load_existing_csv() -> list[dict]:
    rows = []
    with open(EXISTING_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    print(f"  → Loaded {len(rows)} rows from existing CSV.")
    return rows


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\n=== PerfumersWorld Price Updater ===\n")

    # 1. Scrape live prices
    live_prices = scrape_all_prices()
    live_skus   = set(live_prices.keys())

    # 2. Load existing database
    existing_rows = load_existing_csv()
    existing_skus = {row["Product_ID"] for row in existing_rows}

    # 3. Detect new SKUs on site not yet in the database
    new_on_site = live_skus - existing_skus
    if new_on_site:
        print(f"\n  ⚠  {len(new_on_site)} SKUs live on site but NOT in existing CSV:")
        for sku in sorted(new_on_site):
            print(f"       {sku}  US${live_prices[sku]:.3f}/g")

    # 4. Build updated rows
    all_output     = []
    changes_output = []

    for row in existing_rows:
        sku = row["Product_ID"]
        old_price_str = row.get("Price_US/g", "").strip()

        try:
            old_price = float(old_price_str) if old_price_str else None
        except ValueError:
            old_price = None

        if sku in live_prices:
            new_price    = live_prices[sku]
            availability = "Available"

            if old_price is None:
                price_change = "NEW_PRICE"
                new_price_str = f"{new_price:.3f}"
            elif abs(new_price - old_price) < 0.0001:
                price_change  = "unchanged"
                new_price_str = old_price_str   # keep original formatting
            else:
                diff          = new_price - old_price
                price_change  = f"{diff:+.3f}"
                new_price_str = f"{new_price:.3f}"
        else:
            new_price_str = old_price_str
            availability  = "Not Listed"
            price_change  = "REMOVED" if old_price_str else "N/A"

        out_row = dict(row)
        out_row["Price_US/g"]    = new_price_str
        out_row["Availability"]  = availability
        out_row["Price_Change"]  = price_change
        all_output.append(out_row)

        if price_change not in ("unchanged", "N/A"):
            changes_output.append(out_row)

    # 5. Write outputs
    def write_csv(path: Path, rows: list[dict], fieldnames: list[str]):
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        print(f"  ✓ Written: {path}  ({len(rows)} rows)")

    print("\n--- Writing output files ---")
    write_csv(OUT_ALL,     all_output,     OUT_FIELDNAMES)
    write_csv(OUT_CHANGES, changes_output, OUT_FIELDNAMES)

    # 6. Summary
    removed   = sum(1 for r in all_output if r["Price_Change"] == "REMOVED")
    increased = sum(1 for r in all_output if r["Price_Change"].startswith("+"))
    decreased = sum(1 for r in all_output if r["Price_Change"].startswith("-"))
    unchanged = sum(1 for r in all_output if r["Price_Change"] == "unchanged")

    print(f"""
=== Summary ===
  Total rows in existing DB : {len(existing_rows)}
  Unchanged prices          : {unchanged}
  Price increases           : {increased}
  Price decreases           : {decreased}
  Removed from site         : {removed}
  New on site (not in DB)   : {len(new_on_site)}
  Changes output file rows  : {len(changes_output)}
""")


if __name__ == "__main__":
    main()
