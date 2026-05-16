import csv
import re
import json
import time
import urllib.request
import urllib.parse
import os
import ssl

# --- Configuration ---
DELAY_BETWEEN_REQUESTS = 0.5 
CACHE_FILE = '/Users/kijjaz/Desktop/Antigravity/2026/20260317 Perfumery Raw Materials Update/pubchem_verification_cache.json'
INPUT_FILES = [
    'perfumersworld_20260401.csv',
    'myskinrecipes_20260317.csv',
    'simplescentsdiy_20260317.csv'
]
BASE_DIR = '/Users/kijjaz/Desktop/Antigravity/2026/20260317 Perfumery Raw Materials Update'

# --- Name Recovery & Cleaning ---

def recover_name_from_url(url, current_name):
    """Recover chemical name from MySkinRecipes URLs if the name is too short."""
    if not url or "myskinrecipes.com" not in url:
        return current_name
    
    # Example: https://www.myskinrecipes.com/shop/th/ungrouped/33790-113-trimethyl-3-phenyl-indan.html
    match = re.search(r'/(\d+)-([^/]+)\.html$', url)
    if match:
        slug = match.group(2)
        # Convert slug to name
        slug_name = slug.replace('-', ' ')
        # If current name is just a number or very short, use slug
        if len(current_name) < 4 or current_name.isdigit():
            return slug_name
    return current_name

def clean_for_pubchem(name):
    """Advanced cleaning for PubChem compatibility."""
    if not name: return ""
    
    # 1. Remove Thai characters
    name = re.sub(r'[^\x00-\x7F]+', '', name)
    
    # 2. Split on common delimiters and take the first part
    name = re.split(r'[\\/|]', name)[0]
    
    # 3. Handle 'from' (remove suffix)
    name = re.sub(r'\s+from\s+.*$', '', name, flags=re.I)
    
    # 4. Remove common marketing terms and supplier suffixes
    marketing_terms = [
        "Fleuressence", "F-TEC", "Replacer", "Base", "Oliffac", "Grasse", 
        "Synarome", "Givaudan", "IFF", "Firmenich", "Symrise", "Takasago"
    ]
    for term in marketing_terms:
        name = re.sub(r'\b' + re.escape(term) + r'\b', '', name, flags=re.I)

    # 5. Remove dilution markers
    name = re.sub(r'\s+\d+(\.\d+)?%\s+in\s+.*$', '', name, flags=re.I)
    name = re.sub(r'\s*\d+%.*$', '', name, flags=re.I)
    
    # 6. Remove trailing punctuation and descriptors in brackets
    name = re.sub(r'\s*[\[\(].*?[\]\)]\s*$', '', name)
    
    # 7. Final polish
    name = name.strip(' ,-—|/')
    return name

# --- PubChem API (2-Step) ---

def fetch_cas_from_pug_view(cid, ctx):
    """Fetch CAS numbers from PUG-View (annotated data) using a robust recursive search."""
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
                    if obj.get("TOCHeading") == heading:
                        return obj
                    return find_section(obj.get("Section"), heading)
                return None

            cas_section = find_section(data.get("Record", {}), "CAS")
            if not cas_section:
                return []

            cas_list = []
            for info in cas_section.get("Information", []):
                val_obj = info.get("Value", {})
                for val in val_obj.get("StringWithMarkup", []):
                    s = val.get("String")
                    if s and re.match(r'^\d+-\d+-\d+$', s):
                        cas_list.append(s)
            
            return list(set(cas_list))
    except Exception as e:
        print(f"  Error fetching CAS for CID {cid}: {e}")
        return []

def fetch_from_pubchem(name, raw_cas, cache):
    if not name or len(name) < 3: return None
    cache_key = f"{name}_{raw_cas}"
    if cache_key in cache: return cache[cache_key]
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    result = {"cid": None, "cas": [], "canonical_title": None, "source": None}
    
    try:
        # Step 1: Try Name -> CID
        encoded = urllib.parse.quote(name)
        url_name = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{encoded}/cids/JSON"
        req = urllib.request.Request(url_name, headers={'User-Agent': 'CASValidator/2.0'})
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=5) as resp:
                data = json.load(resp)
                if 'IdentifierList' in data and 'CID' in data['IdentifierList']:
                    result["cid"] = data['IdentifierList']['CID'][0]
                    result["source"] = "name"
        except:
            pass

        # Step 2: Try CAS -> CID (if name failed or as verify)
        if not result["cid"] and raw_cas and re.match(r'^\d+-\d+-\d+$', raw_cas):
            url_cas = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{raw_cas}/cids/JSON"
            req = urllib.request.Request(url_cas, headers={'User-Agent': 'CASValidator/2.0'})
            try:
                with urllib.request.urlopen(req, context=ctx, timeout=5) as resp:
                    data = json.load(resp)
                    if 'IdentifierList' in data and 'CID' in data['IdentifierList']:
                        result["cid"] = data['IdentifierList']['CID'][0]
                        result["source"] = "cas_lookup"
            except:
                pass

        if not result["cid"]:
            return None # Truly not found

        # Step 3: CID -> CAS (Annotations)
        result["cas"] = fetch_cas_from_pug_view(result["cid"], ctx)
            
        # Step 4: CID -> Canonical Title
        url_title = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{result['cid']}/description/JSON"
        time.sleep(DELAY_BETWEEN_REQUESTS)
        req_title = urllib.request.Request(url_title, headers={'User-Agent': 'CASValidator/2.0'})
        with urllib.request.urlopen(req_title, context=ctx, timeout=10) as resp:
            data = json.load(resp)
            if 'InformationList' in data and 'Information' in data['InformationList']:
                result["canonical_title"] = data['InformationList']['Information'][0].get('Title')

    except Exception as e:
        print(f"  Error fetching {name}/{raw_cas}: {e}")
        pass
        
    cache[cache_key] = result
    return result

# --- Reporting ---

def generate_report(mismatches, successes, data_gaps_count):
    report_path = os.path.join(BASE_DIR, 'CAS_Accuracy_Audit.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# CAS Accuracy Audit (External Verification)\n\n")
        f.write(f"> [!IMPORTANT]\n")
        f.write(f"> This report is based on **PubChem** as the primary source of truth. Supplier data is flagged if it contradicts PubChem's records.\n\n")
        
        f.write("## 🚨 Level 1: Critical Mismatches\n")
        f.write("Materials where the supplier provided a CAS number that disagrees with PubChem.\n\n")
        f.write("| Cleaned Name | Suppliers | PubChem CAS | Canonical Name |\n")
        f.write("| :--- | :--- | :--- | :--- |\n")
        
        if not mismatches:
            f.write("| (Searching...) | | | |\n")
        else:
            for m in mismatches:
                supp_str = "<br>".join([f"{s}: `{c}`" for s, c in m["supplier_info"].items()])
                pc_cas_str = "<br>".join([f"`{c}`" for c in m["pc_cas"]])
                f.write(f"| {m['name']} | {supp_str} | {pc_cas_str} | {m['pc_title']} |\n")
            
        f.write("\n## ✅ Level 2: Verified Matches\n")
        f.write("Materials where the supplier data exactly matches PubChem.\n\n")
        f.write("| Cleaned Name | Verified CAS | suppliers |\n")
        f.write("| :--- | :--- | :--- |\n")
        
        if not successes:
            f.write("| (Searching...) | | |\n")
        else:
            # Show first 50 successes to keep report clean
            for s in successes[:50]:
                f.write(f"| {s['name']} | `{s['pc_cas'][0]}` | {', '.join(s['supplier_info'].keys())} |\n")
            if len(successes) > 50:
                f.write(f"| ... and {len(successes)-50} more | | |\n")

        f.write("\n## 📊 Summary\n")
        f.write(f"- **Matches Found**: {len(successes)}\n")
        f.write(f"- **Critical Mismatches**: {len(mismatches)}\n")
        f.write(f"- **Data Gaps (No PC Match)**: {data_gaps_count}\n")
        f.write(f"\n*Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')}*\n")

# --- Main Audit ---

def main():
    print("Loading existing cache...")
    cache = {}
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f:
            cache = json.load(f)
            
    unique_materials = {} # cleaned_name -> {suppliers: {supp: cas}, url: url}
    
    for filename in INPUT_FILES:
        path = os.path.join(BASE_DIR, filename)
        if not os.path.exists(path): continue
        print(f"Reading {filename}...")
        with open(path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                raw_name = row.get('Material_Name', '')
                url = row.get('Product_URL') or row.get('Source_URL')
                raw_cas = row.get('CAS_Number', '').split('|')[0].strip().split('\n')[0].strip() # Get main CAS
                
                # Exclude obvious mixtures
                if raw_cas.lower() in ["mixture", "not found", "mixture (perfume base)"]: continue
                
                # Recover and Clean
                recovered_name = recover_name_from_url(url, raw_name)
                clean_name = clean_for_pubchem(recovered_name)
                
                if not clean_name: continue
                
                if clean_name not in unique_materials:
                    unique_materials[clean_name] = {"suppliers": {}, "url": url, "raw_name": raw_name}
                
                supp = row.get('Supplier', filename.split('_')[0])
                unique_materials[clean_name]["suppliers"][supp] = raw_cas

    # Prioritize items that have at least one CAS number from suppliers (actual audit targets)
    sorted_items = sorted(unique_materials.items(), 
                          key=lambda x: any(v for v in x[1]["suppliers"].values() if v), 
                          reverse=True)

    print(f"Unique materials to verify: {len(sorted_items)}")
    
    mismatches = []
    success_list = []
    data_gaps_count = 0
    
    count = 0
    for name, info in sorted_items:
        count += 1
        
        # Periodic Save & Report
        if count % 20 == 0:
            print(f"Verified {count}/{len(sorted_items)}... (Matches: {len(success_list)}, Mismatches: {len(mismatches)}, Gaps: {data_gaps_count})")
            with open(CACHE_FILE, 'w') as f: json.dump(cache, f, indent=2)
            generate_report(mismatches, success_list, data_gaps_count)

        # Skip if too generic
        if len(name) < 4: continue

        # First non-empty cas for this cleaned name
        any_cas = next((v for v in info["suppliers"].values() if v), None)
        
        pc = fetch_from_pubchem(name, any_cas, cache)
        if not pc or not pc["cas"]:
            data_gaps_count += 1
            continue
            
        # Compare with each supplier
        has_mismatch = False
        for supp, s_cas in info["suppliers"].items():
            if s_cas and s_cas in pc["cas"]:
                pass # OK
            elif s_cas:
                has_mismatch = True
            else:
                pass # Empty supplier CAS skip
        
        item = {
            "name": name,
            "raw_name": info["raw_name"],
            "url": info["url"],
            "supplier_info": info["suppliers"],
            "pc_cas": pc["cas"],
            "pc_title": pc["canonical_title"]
        }
        
        if has_mismatch:
            mismatches.append(item)
        else:
            success_list.append(item)

    # Save final cache
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=2)

    # Generate final report
    generate_report(mismatches, success_count, data_gaps_count)
    print(f"Audit complete. Final report at {os.path.join(BASE_DIR, 'CAS_Accuracy_Audit.md')}")
        
    print(f"Report generated at {report_path}")

if __name__ == "__main__":
    main()
