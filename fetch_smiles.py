import csv
import json
import time
import urllib.request
import urllib.parse
import os
import ssl

# --- Configuration ---
MASTER_CSV = 'Perfumery_Raw_Materials_Audit_Master.csv'
CACHE_FILE = 'pubchem_smiles_cache.json'
DELAY_BETWEEN_REQUESTS = 0.3
BATCH_SIZE = 100

def fetch_smiles_batch(cids):
    """Fetch IsomericSMILES and CanonicalSMILES for a batch of CIDs."""
    if not cids: return {}
    
    cids_str = ",".join(cids)
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cids_str}/property/IsomericSMILES,CanonicalSMILES/JSON"
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    req = urllib.request.Request(url, headers={'User-Agent': 'SMILES-Fetcher/1.0'})
    results = {}
    
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            properties = data.get("PropertyTable", {}).get("Properties", [])
            for prop in properties:
                cid = str(prop.get("CID"))
                results[cid] = {
                    "IsomericSMILES": prop.get("IsomericSMILES") or prop.get("SMILES"),
                    "CanonicalSMILES": prop.get("CanonicalSMILES") or prop.get("ConnectivitySMILES")
                }
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code} for batch. Retrying in chunks if possible...")
    except Exception as e:
        print(f"Error fetching batch: {e}")
        
    return results

def main():
    print(f"Reading {MASTER_CSV}...")
    if not os.path.exists(MASTER_CSV):
        print(f"Error: {MASTER_CSV} not found.")
        return

    cids_to_fetch = set()
    with open(MASTER_CSV, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cid = row.get('PubChem_CID', '').strip()
            if cid and cid != 'None' and cid.isdigit():
                cids_to_fetch.add(cid)

    cids_to_fetch = sorted(list(cids_to_fetch))
    print(f"Found {len(cids_to_fetch)} unique CIDs in the master CSV.")

    # Load existing cache
    cache = {}
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f:
            cache = json.load(f)
            
    # Filter out CIDs we already have
    missing_cids = [cid for cid in cids_to_fetch if cid not in cache]
    print(f"Missing SMILES for {len(missing_cids)} CIDs. Fetching...")

    for i in range(0, len(missing_cids), BATCH_SIZE):
        batch = missing_cids[i:i+BATCH_SIZE]
        print(f"Fetching batch {i//BATCH_SIZE + 1} of {(len(missing_cids)-1)//BATCH_SIZE + 1}...")
        
        batch_results = fetch_smiles_batch(batch)
        
        if batch_results:
            cache.update(batch_results)
            # Save incrementally
            with open(CACHE_FILE, 'w') as f:
                json.dump(cache, f, indent=2)
                
        time.sleep(DELAY_BETWEEN_REQUESTS)

    print(f"Done. Cache has {len(cache)} entries.")

if __name__ == "__main__":
    main()
