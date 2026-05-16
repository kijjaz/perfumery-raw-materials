import csv
import re
import json
import time
import urllib.request
import urllib.parse
import os
import ssl

# --- Configuration ---
DELAY_BETWEEN_REQUESTS = 0.2 
CACHE_FILE = '/Users/kijjaz/Desktop/Antigravity/2026/20260317 Perfumery Raw Materials Update/pubchem_master_audit_cache.json'
WIP_FILE = '20260401 Kijjaz - miniChihuahua 0.1.10 WIP PW & SimpleScentsDIY Edition - 🌿 RawMaterials.csv'
SUPPLIER_FILES = [
    'perfumersworld_20260401.csv',
    'myskinrecipes_20260317.csv',
    'simplescentsdiy_20260317.csv'
]
BASE_DIR = '/Users/kijjaz/Desktop/Antigravity/2026/20260317 Perfumery Raw Materials Update'
OUTPUT_CSV = os.path.join(BASE_DIR, 'Perfumery_Raw_Materials_Audit_Master.csv')

# --- Name Recovery & Cleaning ---

def recover_name_from_url(url, current_name):
    if not url or "myskinrecipes.com" not in url: return current_name
    match = re.search(r'/(\d+)-([^/]+)\.html$', url)
    if match:
        slug = match.group(2).replace('-', ' ')
        if len(current_name) < 4 or current_name.isdigit(): return slug
    return current_name

def clean_for_pubchem(name):
    if not name: return ""
    name = re.sub(r'[^\x00-\x7F]+', '', name) # Remove non-ASCII
    name = re.split(r'[\\/|]', name)[0] # Take first part
    name = re.sub(r'\s+from\s+.*$', '', name, flags=re.I)
    marketing = ["Fleuressence", "F-TEC", "Replacer", "Base", "Oliffac", "Grasse", "Synarome", "Givaudan", "IFF", "Firmenich", "Symrise", "Takasago"]
    for term in marketing:
        name = re.sub(r'\b' + re.escape(term) + r'\b', '', name, flags=re.I)
    name = re.sub(r'\s+\d+(\.\d+)?%\s+in\s+.*$', '', name, flags=re.I)
    name = re.sub(r'\s*\d+%.*$', '', name, flags=re.I)
    name = re.sub(r'\s*[\[\(].*?[\]\)]\s*$', '', name)
    return name.strip(' ,-—|/')

# --- PubChem API ---

def fetch_synonyms(cid, ctx):
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/synonyms/JSON"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'CASValidator/2.0'})
        with urllib.request.urlopen(req, context=ctx, timeout=5) as r:
            data = json.loads(r.read().decode('utf-8'))
            return data.get("InformationList", {}).get("Information", [{}])[0].get("Synonym", [])[:10]
    except: return []

def fetch_cas_from_pug_view(cid, ctx):
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/{cid}/JSON?heading=CAS"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'CASValidator/2.0'})
        with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
            data = json.loads(r.read().decode('utf-8'))
            def find_section(obj, heading):
                if isinstance(obj, list):
                    for item in obj:
                        res = find_section(item, heading)
                        if res: return res
                elif isinstance(obj, dict):
                    if obj.get("TOCHeading") == heading: return obj
                    return find_section(obj.get("Section"), heading)
                return None
            cas_section = find_section(data.get("Record", {}), "CAS")
            if not cas_section: return []
            cas_list = []
            for info in cas_section.get("Information", []):
                val_obj = info.get("Value", {})
                for val in val_obj.get("StringWithMarkup", []):
                    s = val.get("String")
                    if s and re.match(r'^\d+-\d+-\d+$', s): cas_list.append(s)
            return list(set(cas_list))
    except: return []

def fetch_full_audit_data(name, raw_cas, cache):
    cache_key = f"{name}_{raw_cas}"
    if cache_key in cache:
        entry = cache[cache_key]
        # Compatibility with old cache schema
        if "canonical_title" in entry and "title" not in entry:
            entry["title"] = entry["canonical_title"]
        if "synonyms" not in entry:
            entry["synonyms"] = []
        
        # If we have a CID but no synonyms/title, we might want to re-fetch
        if entry.get("cid") and (not entry.get("synonyms") or not entry.get("title")):
            pass # We'll allow it to use cache for now, or re-fetch if needed
        else:
            return entry
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    res = {"cid": None, "cas": [], "synonyms": [], "title": None, "source": None}
    try:
        encoded = urllib.parse.quote(name)
        url_name = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{encoded}/cids/JSON"
        try:
            req = urllib.request.Request(url_name, headers={'User-Agent': 'CASValidator/2.0'})
            with urllib.request.urlopen(req, context=ctx, timeout=5) as resp:
                data = json.load(resp)
                if 'IdentifierList' in data and 'CID' in data['IdentifierList']:
                    res["cid"] = data['IdentifierList']['CID'][0]; res["source"] = "name"
        except: pass
        if not res["cid"] and raw_cas and re.match(r'^\d+-\d+-\d+$', raw_cas):
            url_cas = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{raw_cas}/cids/JSON"
            try:
                req = urllib.request.Request(url_cas, headers={'User-Agent': 'CASValidator/2.0'})
                with urllib.request.urlopen(req, context=ctx, timeout=5) as resp:
                    data = json.load(resp)
                    if 'IdentifierList' in data and 'CID' in data['IdentifierList']:
                        res["cid"] = data['IdentifierList']['CID'][0]; res["source"] = "cas_lookup"
            except: pass
        if res["cid"]:
            time.sleep(DELAY_BETWEEN_REQUESTS)
            res["cas"] = fetch_cas_from_pug_view(res["cid"], ctx)
            time.sleep(DELAY_BETWEEN_REQUESTS)
            res["synonyms"] = fetch_synonyms(res["cid"], ctx)
            url_title = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{res['cid']}/description/JSON"
            req_title = urllib.request.Request(url_title, headers={'User-Agent': 'CASValidator/2.0'})
            with urllib.request.urlopen(req_title, context=ctx, timeout=10) as resp:
                data = json.load(resp)
                if 'InformationList' in data and 'Information' in data['InformationList']:
                    res["title"] = data['InformationList']['Information'][0].get('Title')
    except Exception as e: print(f"Error fetching {name}: {e}")
    cache[cache_key] = res
    return res

# --- Main Audit ---

def main():
    print("Loading existing cache...")
    cache = {}
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f: cache = json.load(f)
            
    # unique_materials[clean_name] = {wip_cas, supplier_cas_map, raw_name, url}
    data = {} 
    
    # 1. Read WIP Database (Baseline)
    wip_path = os.path.join(BASE_DIR, WIP_FILE)
    if os.path.exists(wip_path):
        print(f"Reading WIP Database: {WIP_FILE}...")
        with open(wip_path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                raw_name = row.get('Material_Name', '')
                clean_name = clean_for_pubchem(raw_name)
                cas = row.get('CAS_Number', '').strip()
                if clean_name not in data:
                    data[clean_name] = {"wip_cas": cas, "supplier_cas": {}, "raw_name": raw_name, "url": ""}
                else:
                    data[clean_name]["wip_cas"] = cas

    # 2. Read Supplier Files
    for filename in SUPPLIER_FILES:
        path = os.path.join(BASE_DIR, filename)
        if not os.path.exists(path): continue
        print(f"Reading Supplier: {filename}...")
        with open(path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                raw_name = row.get('Material_Name', '')
                url = row.get('Product_URL', row.get('Source_URL', ''))
                clean_name = clean_for_pubchem(recover_name_from_url(url, raw_name))
                cas = row.get('CAS_Number', '').strip().split('|')[0].strip().split('\n')[0].strip()
                if cas.lower() in ["mixture", "not found"]: cas = ""
                
                if clean_name not in data:
                    data[clean_name] = {"wip_cas": "", "supplier_cas": {}, "raw_name": raw_name, "url": url}
                
                supp = row.get('Supplier', filename.split('_')[0])
                data[clean_name]["supplier_cas"][supp] = cas
                if not data[clean_name]["url"]: data[clean_name]["url"] = url

    # 3. Sort for Audit
    # Prioritize items with non-empty CAS (either WIP or Supplier)
    sorted_items = sorted(data.items(), 
                          key=lambda x: (bool(x[1]["wip_cas"]), len(x[1]["supplier_cas"])), 
                          reverse=True)

    print(f"Total materials to audit: {len(sorted_items)}")
    
    # 4. Process and Generate CSV
    results = []
    count = 0
    for name, info in sorted_items:
        count += 1
        any_cas = info["wip_cas"] or next(iter(info["supplier_cas"].values()), "")
        pc = fetch_full_audit_data(name, any_cas, cache)
        
        status = "DATA_GAP"
        notes = []
        
        if pc["cid"]:
            # Check Match
            if info["wip_cas"] and info["wip_cas"] in pc["cas"]:
                 status = "WIP_VERIFIED"
            elif info["wip_cas"]:
                 status = "WIP_DISCREPANCY"
                 notes.append(f"WIP CAS {info['wip_cas']} not in PubChem {pc['cas']}")
            
            # Trace Supplier
            for s, s_cas in info["supplier_cas"].items():
                if s_cas and s_cas not in pc["cas"]:
                    notes.append(f"Supplier {s} CAS {s_cas} error")
                    if status != "WIP_DISCREPANCY": status = "SUPPLIER_MISMATCH"
        
        elif "Oil" in info["raw_name"] or "Essential" in info["raw_name"]:
            status = "NATURAL_MIXTURE"
        
        results.append({
            "Status": status,
            "Cleaned_Name": name,
            "WIP_CAS": info["wip_cas"],
            "PubChem_CID": pc.get("cid"),
            "PubChem_Title": pc.get("title") or pc.get("canonical_title"),
            "PubChem_CAS_All": "|".join(pc.get("cas", [])),
            "PubChem_Synonyms_Top10": "|".join(pc.get("synonyms", [])),
            "Audit_Notes": "; ".join(notes),
            "Original_Name": info["raw_name"],
            "Supplier_CAS_Map": str(info["supplier_cas"]),
            "Product_URL": info["url"]
        })
        
        if count % 100 == 0:
            print(f"Verified {count}/{len(sorted_items)}... saving intermediate CSV.")
            with open(OUTPUT_CSV, 'w', encoding='utf-8', newline='') as f:
                if results:
                    writer = csv.DictWriter(f, fieldnames=results[0].keys())
                    writer.writeheader()
                    writer.writerows(results)
            with open(CACHE_FILE, 'w') as f: json.dump(cache, f, indent=2)

    with open(OUTPUT_CSV, 'w', encoding='utf-8', newline='') as f:
        if results:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)
    
    print(f"Master Audit complete: {OUTPUT_CSV}")
    with open(CACHE_FILE, 'w') as f: json.dump(cache, f, indent=2)

if __name__ == "__main__":
    main()
