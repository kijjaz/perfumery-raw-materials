import csv
import re
import os
import datetime

# --- Configuration ---
AUDIT_CSV = 'Perfumery_Raw_Materials_Audit_Master.csv'
PW_CSV = 'perfumersworld_20260401_updated.csv'
MSR_CSV = 'myskinrecipes_20260317.csv'
SSD_CSV = 'simplescentsdiy_20260317.csv'

current_date = datetime.datetime.now().strftime("%Y%m%d")
OUTPUT_CSV = f'🌿 RawMaterials_v0_1_11_Cleaned_{current_date}.csv'

EXCHANGE_RATE_USD_THB = 35.0

SOLVENTS_MAP = {
    'DPG': 'Dipropylene Glycol (DPG)',
    'TEC': 'Triethyl Citrate (TEC)',
    'IPM': 'Isopropyl Myristate (IPM)',
    'BB': 'Benzyl Benzoate (BB)',
    'DEP': 'Diethyl Phthalate (DEP)',
    'PG': 'Propylene Glycol (PG)',
    'PEA': 'Phenyl Ethyl Alcohol (PEA)',
    'ETHANOL': 'Ethanol',
    'ALCOHOL': 'Ethanol'
}

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

def clean_supplier_suffix(name):
    if not name:
        return ""
    name = re.sub(r'\s+from\s+(PerfumersWorld|MySkinRecipes|SimpleScentsDIY)\b', '', name, flags=re.IGNORECASE)
    return name.strip()

def clean_cas_formatting(cas_str):
    if not cas_str:
        return ""
    cas_str = cas_str.strip()
    if cas_str.lower() in ["mixture", "confidential", "not found", "not listed", "mixture (perfume base)", "none"]:
        return ""
    # Extract first CAS if multiple are separated by | or newlines
    normalized = cas_str.replace('\n', '|').replace('\r', '')
    parts = normalized.split('|')
    for part in parts:
        part = part.strip()
        # Find something looking like a CAS number: digits-digits-digit
        match = re.search(r'\d+-\d{2}-\d', part)
        if match:
            cas = match.group(0)
            # Remove leading zeros in the first part (e.g. 0140-11-4 -> 140-11-4)
            cleaned = re.sub(r'^0+', '', cas)
            return cleaned
    return ""

def recover_name_from_slug(url, current_name):
    if not url or 'myskinrecipes.com' not in url:
        return current_name
        
    match = re.search(r'/(\d+)-([^/]+)\.html$', url)
    if not match:
        return current_name
        
    slug = match.group(2).strip('- ')
    
    # 1. Extract FEMA tag
    fema_match = re.search(r'fema[-_]?(\d+)', slug, re.IGNORECASE)
    fema_str = ''
    if fema_match:
        fema_str = f' (FEMA {fema_match.group(1)})'
        slug = re.sub(r'fema[-_]?\d+', '', slug, flags=re.IGNORECASE).strip('- ')

    # 2. Normalize stereochemistry prefixes/infixes
    prefix = ''
    if slug.lower().startswith('z-') or slug.lower().startswith('-z-'):
        prefix = '(Z)-'
        slug = re.sub(r'^[-zZ]+-', '', slug)
    elif slug.lower().startswith('e-') or slug.lower().startswith('-e-'):
        prefix = '(E)-'
        slug = re.sub(r'^[-eE]+-', '', slug)
    elif slug.lower().startswith('ee-'):
        prefix = '(E,E)-'
        slug = slug[3:]
    elif slug.lower().startswith('cis-'):
        prefix = 'Cis-'
        slug = slug[4:]
    elif slug.lower().startswith('trans-'):
        prefix = 'Trans-'
        slug = slug[6:]
    elif re.match(r'^\d+[ez]-', slug, re.IGNORECASE):
        m_ste = re.match(r'^(\d+)([ez])-(.*)', slug, re.IGNORECASE)
        if m_ste:
            prefix = f'({m_ste.group(1)}{m_ste.group(2).upper()})-'
            slug = m_ste.group(3)
        
    # Infixes
    slug = re.sub(r'([a-zA-Z]+)-(e|z)-', r'\1 (\2)-', slug, flags=re.IGNORECASE)
    slug = re.sub(r'(\d+)-(e|z)-', r'\1-(\2)-', slug, flags=re.IGNORECASE)
    slug = re.sub(r'\(([ez])\)', lambda m: f'({m.group(1).upper()})', slug, flags=re.IGNORECASE)

    # 3. Add commas for multi-digits at start if they represent chemical positions
    slug = re.sub(r'\b113-([a-zA-Z])', r'1,1,3-\1', slug)
    slug = re.sub(r'\b24-([a-zA-Z])', r'2,4-\1', slug)
    slug = re.sub(r'\b45-([a-zA-Z])', r'4,5-\1', slug)
    slug = re.sub(r'\b245-([a-zA-Z])', r'2,4,5-\1', slug)
    slug = re.sub(r'\b35-([a-zA-Z])', r'3,5-\1', slug)
    slug = re.sub(r'\b36-([a-zA-Z])', r'3,6-\1', slug)
    slug = re.sub(r'\b26-([a-zA-Z])', r'2,6-\1', slug)
    slug = re.sub(r'\b2611-([a-zA-Z])', r'2,6,11-\1', slug)
    slug = re.sub(r'\b13-([a-zA-Z])', r'1,3-\1', slug)
    slug = re.sub(r'\b56-decenoic', r'5(6)-decenoic', slug)
    
    # Replace prefix hyphens with spaces for chemical names, only at the start of the slug and for specific ester/alkyl prefixes!
    prefix_pattern = r'^(methyl|ethyl|propyl|butyl|amyl|pentyl|hexyl|heptyl|octyl|decyl|neryl|geranyl|linalyl|cinnamyl|benzyl|phenethyl|phenyl|isoamyl|isobutyl|isopropyl|natural)-(?=\d|\([EZ]\))'
    slug = re.sub(prefix_pattern, r'\1 ', slug, flags=re.IGNORECASE)

    # 4. Protect hyphens:
    # - Adjacent to digit on either side
    # - Adjacent to (E) or (Z) on either side
    def protect(m):
        return m.group(0).replace('-', '__HYPHEN__')
        
    slug = re.sub(r'\d+-', protect, slug)
    slug = re.sub(r'-\d+', protect, slug)
    slug = re.sub(r'\([EZ]\)-', protect, slug)
    slug = re.sub(r'-\([EZ]\)', protect, slug)

    # Replace remaining hyphens with spaces
    slug = slug.replace('-', ' ')

    # Restore protected hyphens
    slug = slug.replace('__HYPHEN__', '-')

    # 5. Title Case words
    words = slug.split()
    capitalized_words = []
    for w in words:
        if '-' in w:
            w_parts = w.split('-')
            capitalized_parts = []
            for wp in w_parts:
                if wp.lower() in ['yl', 'ol', 'ene', 'al', 'one', 'acid', 'd', 'l', 'dl']:
                    capitalized_parts.append(wp.lower())
                elif wp.isalpha():
                    capitalized_parts.append(wp.capitalize())
                else:
                    capitalized_parts.append(wp)
            capitalized_words.append('-'.join(capitalized_parts))
        else:
            if w.lower() in ['in', 'of', 'and']:
                capitalized_words.append(w.lower())
            elif w.isalpha():
                capitalized_words.append(w.capitalize())
            else:
                capitalized_words.append(w)
                
    result = prefix + ' '.join(capitalized_words) + fema_str
    
    # Simple clean up of common issues
    result = result.replace('2 4-dimethyl', '2,4-dimethyl')
    result = result.replace('3 4-methoxyphenyl', '3,4-methoxyphenyl')
    result = result.replace('3-methyl-5-phenylpentan 1-ol', '3-methyl-5-phenylpentan-1-ol')
    result = result.replace('2 4-methylcyclohexylpropan 2-ol', '2-(4-methylcyclohexyl)propan-2-ol')
    
    return result

def clean_msr_name(url, name):
    name_clean = name.strip()
    name_clean = name_clean.replace('\u2011', '-').replace('\u2013', '-').replace('\u2014', '-')
    
    has_non_ascii = bool(re.search(r'[^\x00-\x7F]+', name_clean))
    
    fema_in_slug = False
    if url:
        match = re.search(r'/(\d+)-([^/]+)\.html$', url)
        if match:
            slug = match.group(2)
            fema_in_slug = 'fema' in slug.lower() and 'fema' not in name_clean.lower()

    more_words_in_slug = False
    if url:
        match = re.search(r'/(\d+)-([^/]+)\.html$', url)
        if match:
            slug = match.group(2)
            slug_clean = re.sub(r'fema[-_]?\d+', '', slug, flags=re.IGNORECASE)
            slug_words = [w for w in slug_clean.split('-') if w and not w.isdigit()]
            name_words = [w for w in name_clean.split() if w]
            more_words_in_slug = len(slug_words) > len(name_words) and len(name_clean) <= 10

    is_trunc = (
        name_clean.endswith('(FEMA') or name_clean.endswith('FEMA') or
        name_clean.count('(') > name_clean.count(')') or
        name_clean.count('[') > name_clean.count(']') or
        len(name_clean) <= 5 or
        re.search(r'^[A-Za-z]+\s+\([EZ]\)$', name_clean) or
        name_clean in ['(Z)', '[(Z)', '(E)', '[(E)', 'Para', 'Beta', 'Alpha', 'Gamma', 'Meta'] or
        re.search(r'^[A-Za-z]+\s+\d+$', name_clean) or
        has_non_ascii or
        fema_in_slug or
        more_words_in_slug
    )
    
    if is_trunc:
        recovered = recover_name_from_slug(url, name_clean)
        if recovered and (len(recovered) > len(name_clean) or has_non_ascii or fema_in_slug):
            return recovered
            
    return name_clean

def determine_remediation_status(raw_name, cas, cleaned_cas, fix):
    remediation_status = "VERIFIED"
    canonical_name = ""
    verified_cas = cleaned_cas
    
    if fix:
        canonical_name = fix['canonical_title']
        if fix['status'] == 'WIP_DISCREPANCY':
            verified_cas = clean_cas_formatting(fix['verified_cas']) or cleaned_cas
            remediation_status = "FIXED_FROM_AUDIT"
        elif fix['status'] == 'DATA_GAP':
            remediation_status = "DATA_GAP_MANUAL_CHECK"
        elif fix['status'] == 'NATURAL_MIXTURE':
            remediation_status = "NATURAL_MIXTURE"
        elif fix['status'] == 'WIP_VERIFIED':
            remediation_status = "VERIFIED_MATCH"
    else:
        # Default logic if not in audit map
        if any(x in raw_name.lower() for x in [" oil ", " essential", " absolute", " resinoid", " extract"]):
            remediation_status = "NATURAL_MIXTURE"
        elif not cleaned_cas:
            remediation_status = "DATA_GAP_MANUAL_CHECK"

    # Refine DATA_GAP_MANUAL_CHECK to identify proprietary mixtures or natural mixtures
    if remediation_status == "DATA_GAP_MANUAL_CHECK":
        name_lower = raw_name.lower()
        cas_lower = cas.lower() if cas else ""
        if any(x in name_lower for x in [" oil ", " essential", " absolute", " resinoid", " extract"]):
            remediation_status = "NATURAL_MIXTURE"
        elif (any(x in name_lower for x in ["f-tec", "fleuressence", "replacer", "base", "oliffac", "grasse", "synarome", "blend", "complex", " reconstituted"]) or
              "mixture" in cas_lower or "confidential" in cas_lower or "none" in cas_lower):
            remediation_status = "PROPRIETARY_MIXTURE"

    # Check if CAS was modified by formatting
    if remediation_status == "VERIFIED" and cleaned_cas != cas and re.match(r'^\d+-\d+-\d+$', cleaned_cas):
        remediation_status = "FORMATTING_FIX"
        
    return remediation_status, canonical_name, verified_cas

def parse_dilution_from_name(name, supplier):
    # e.g., "Skatole 1% in DPG" or "Galaxolide 50% in DPG"
    match = re.search(r'(\d+(?:\.\d+)?)\s*%\s*(?:in\s+)?([A-Za-z0-9]+)', name, re.IGNORECASE)
    if match:
        pct = float(match.group(1))
        solv = match.group(2).upper()
        if solv in SOLVENTS_MAP:
            active_name = name[:match.start()].strip().rstrip(' ,-—/')
            return active_name, pct, SOLVENTS_MAP[solv]
            
    # e.g., "Cedryl Acetate 50%"
    match_pct = re.search(r'(\d+(?:\.\d+)?)\s*%', name)
    if match_pct:
        pct = float(match_pct.group(1))
        active_name = name[:match_pct.start()].strip().rstrip(' ,-—/')
        return active_name, pct, None
        
    return None

def parse_quantity_g(size_str):
    if not size_str:
        return 1.0
    size_str = size_str.lower().strip()
    m_g = re.search(r'([\d.]+)\s*g', size_str)
    if m_g:
        return float(m_g.group(1))
    m_kg = re.search(r'([\d.]+)\s*kg', size_str)
    if m_kg:
        return float(m_kg.group(1)) * 1000.0
    m_ml = re.search(r'([\d.]+)\s*ml', size_str)
    if m_ml:
        return float(m_ml.group(1))
    m_l = re.search(r'([\d.]+)\s*(?:l|liter)', size_str)
    if m_l:
        return float(m_l.group(1)) * 1000.0
    m_oz = re.search(r'([\d.]+)\s*oz', size_str)
    if m_oz:
        return float(m_oz.group(1)) * 28.35
    m_num = re.match(r'([\d.]+)', size_str)
    if m_num:
        return float(m_num.group(1))
    return 1.0

def main():
    # Load audit fixes from Perfumery_Raw_Materials_Audit_Master.csv
    fix_map = {}
    if os.path.exists(AUDIT_CSV):
        print(f"Loading audit fixes from {AUDIT_CSV}...")
        with open(AUDIT_CSV, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                orig_name = row.get('Original_Name')
                if orig_name:
                    pc_cas_all = row.get('PubChem_CAS_All', '').split('|')
                    best_pc_cas = pc_cas_all[0] if pc_cas_all and pc_cas_all[0] else ""
                    
                    fix_data = {
                        "verified_cas": best_pc_cas,
                        "canonical_title": row.get('PubChem_Title', ''),
                        "status": row.get('Status', ''),
                        "synonyms": row.get('PubChem_Synonyms_Top10', ''),
                        "cid": row.get('PubChem_CID', '')
                    }
                    fix_map[orig_name] = fix_data
                    
                    cleaned_key = clean_for_pubchem(orig_name).lower()
                    if cleaned_key:
                        fix_map[cleaned_key] = fix_data
    else:
        print(f"Warning: Audit master {AUDIT_CSV} not found. Continuing without audit fixes.")

    output_rows = []

    # 1. Process PerfumersWorld
    print(f"Processing PerfumersWorld from {PW_CSV}...")
    with open(PW_CSV, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            sku = row['Product_ID'].strip()
            # Filter SKU according to user request: exactly 8 chars and starts with 1-9
            if not (len(sku) == 8 and sku[0] in '123456789'):
                continue
                
            raw_name = row['Material_Name'].strip()
            cas = row.get('CAS_Number', '').strip()
            
            # Extract price in USD/g
            price_usd_str = row.get('Price_US/g', '').strip()
            try:
                price_usd = float(price_usd_str) if price_usd_str else ""
            except ValueError:
                price_usd = ""
                
            # Formatting CAS
            cleaned_cas = clean_cas_formatting(cas)
            
            # Lookup in audit fixes
            # We match by the exact Material_Name or by the clean name
            cleaned_search_key = clean_for_pubchem(raw_name).lower()
            fix = fix_map.get(raw_name) or (fix_map.get(cleaned_search_key) if cleaned_search_key else None)
            
            remediation_status, canonical_name, verified_cas = determine_remediation_status(raw_name, cas, cleaned_cas, fix)

            # Dilution details
            is_dil = row.get('Is_Dilution') == 'TRUE'
            active_pct_val = row.get('Active_%', '').strip()
            
            active_material_col = ""
            solvent_col = ""
            active_pct_col = ""
            
            if is_dil:
                try:
                    pct = float(active_pct_val)
                    if pct <= 1.0:
                        pct = pct * 100.0
                    pct_str = f"{pct:.2f}"
                except ValueError:
                    pct_str = ""
                active_material_col = row.get('Active_Material', '').strip()
                if active_material_col and not active_material_col.endswith('from PerfumersWorld'):
                    active_material_col += ' from PerfumersWorld'
                solvent_col = row.get('Solvent', '').strip()
                if solvent_col and not solvent_col.endswith('from PerfumersWorld'):
                    solvent_col += ' from PerfumersWorld'
                active_pct_col = pct_str

            cid = fix.get('cid', '') if fix else ''
            pubchem_link = f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}" if cid else ""

            output_rows.append({
                'Product_ID': sku,
                'Supplier': 'PerfumersWorld',
                'Material_Name': raw_name,
                'Clean_Search_Name': cleaned_search_key,
                'CAS_Number': cas,
                'Remediation_Status': remediation_status,
                'Canonical_Name': canonical_name,
                'Verified_CAS': verified_cas,
                'PubChem_Link': pubchem_link,
                'Price_USD/g': f"{price_usd:.4f}" if isinstance(price_usd, float) else "",
                'Is_Dilution': 'TRUE' if is_dil else 'FALSE',
                'Active_Material': active_material_col,
                'Solvent': solvent_col,
                'Active_%': active_pct_col,
                'Notes': row.get('Notes', '').strip()
            })

    # 2. Process MySkinRecipes
    print(f"Processing MySkinRecipes from {MSR_CSV}...")
    with open(MSR_CSV, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            sku = row['Product_ID'].strip()
            raw_name_orig = row['Material_Name'].strip()
            raw_name = clean_msr_name(row.get('Product_URL', ''), raw_name_orig)
            # Append from MySkinRecipes suffix if not present
            material_name = raw_name
            if not material_name.endswith('from MySkinRecipes'):
                material_name += ' from MySkinRecipes'
                
            cas = row.get('CAS_Number', '').strip()
            cleaned_cas = clean_cas_formatting(cas)
            
            # Calculate Price in USD/g
            # MySkinRecipes prices are in THB. Convert to USD by dividing by 35.0
            price_thb_g_str = row.get('Price_THB/g', '').strip()
            price_thb_total_str = row.get('Price_THB_total', '').strip()
            pkg_size_str = row.get('Package_Size', '').strip()
            
            price_usd = ""
            try:
                if price_thb_g_str:
                    price_usd = float(price_thb_g_str) / EXCHANGE_RATE_USD_THB
                elif price_thb_total_str and pkg_size_str:
                    qty_g = parse_quantity_g(pkg_size_str)
                    price_usd = (float(price_thb_total_str) / qty_g) / EXCHANGE_RATE_USD_THB
            except Exception:
                price_usd = ""

            # Lookup in audit fixes
            # We match by the raw name, raw name with suffix, or the cleaned version of the name
            cleaned_search_key = clean_for_pubchem(raw_name).lower()
            fix = (
                fix_map.get(raw_name_orig) or 
                fix_map.get(raw_name_orig + ' from MySkinRecipes') or 
                fix_map.get(raw_name) or 
                fix_map.get(material_name) or
                (fix_map.get(cleaned_search_key) if cleaned_search_key else None)
            )
            
            remediation_status, canonical_name, verified_cas = determine_remediation_status(raw_name, cas, cleaned_cas, fix)

            # Dilution details from name or columns
            dilution_info = parse_dilution_from_name(raw_name, 'MySkinRecipes')
            is_dil = False
            active_material_col = ""
            solvent_col = ""
            active_pct_col = ""
            
            if dilution_info:
                is_dil = True
                act_name, pct, solv_name = dilution_info
                pct_str = f"{pct:.2f}"
                active_material_col = act_name + ' from MySkinRecipes'
                solvent_col = (solv_name + ' from MySkinRecipes') if solv_name else ""
                active_pct_col = pct_str
            elif row.get('Is_Dilution') == 'TRUE':
                is_dil = True
                # Parse Active_%
                act_pct_val = row.get('Active_%', '').strip()
                try:
                    pct = float(act_pct_val)
                    if pct <= 1.0:
                        pct = pct * 100.0
                    pct_str = f"{pct:.2f}"
                except ValueError:
                    pct_str = ""
                active_material_col = row.get('Active_Material', '').strip()
                if active_material_col and not active_material_col.endswith('from MySkinRecipes'):
                    active_material_col += ' from MySkinRecipes'
                solvent_col = row.get('Solvent', '').strip()
                if solvent_col and not solvent_col.endswith('from MySkinRecipes'):
                    solvent_col += ' from MySkinRecipes'
                active_pct_col = pct_str

            cid = fix.get('cid', '') if fix else ''
            pubchem_link = f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}" if cid else ""

            output_rows.append({
                'Product_ID': sku,
                'Supplier': 'MySkinRecipes',
                'Material_Name': material_name,
                'Clean_Search_Name': cleaned_search_key,
                'CAS_Number': cas,
                'Remediation_Status': remediation_status,
                'Canonical_Name': canonical_name,
                'Verified_CAS': verified_cas,
                'PubChem_Link': pubchem_link,
                'Price_USD/g': f"{price_usd:.4f}" if isinstance(price_usd, float) else "",
                'Is_Dilution': 'TRUE' if is_dil else 'FALSE',
                'Active_Material': active_material_col,
                'Solvent': solvent_col,
                'Active_%': active_pct_col,
                'Notes': row.get('Notes', '').strip()
            })

    # 3. Process SimpleScentsDIY
    print(f"Processing SimpleScentsDIY from {SSD_CSV}...")
    with open(SSD_CSV, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            sku = row['Product_ID'].strip()
            raw_name = row['Material_Name'].strip()
            # Append from SimpleScentsDIY suffix if not present
            material_name = raw_name
            if not material_name.endswith('from SimpleScentsDIY'):
                material_name += ' from SimpleScentsDIY'
                
            cas = row.get('CAS_Number', '').strip()
            cleaned_cas = clean_cas_formatting(cas)
            
            # Calculate Price in USD/g
            # SimpleScentsDIY prices are in THB. Convert to USD by dividing by 35.0
            price_thb_g_str = row.get('Price_THB/g', '').strip()
            price_thb_total_str = row.get('Price_THB_total', '').strip()
            pkg_size_str = row.get('Package_Size', '').strip()
            
            price_usd = ""
            try:
                if price_thb_g_str:
                    price_usd = float(price_thb_g_str) / EXCHANGE_RATE_USD_THB
                elif price_thb_total_str and pkg_size_str:
                    qty_g = parse_quantity_g(pkg_size_str)
                    price_usd = (float(price_thb_total_str) / qty_g) / EXCHANGE_RATE_USD_THB
            except Exception:
                price_usd = ""

            # Lookup in audit fixes
            # We match by the raw name, raw name with suffix, or the cleaned version of the name
            cleaned_search_key = clean_for_pubchem(raw_name).lower()
            fix = (
                fix_map.get(raw_name) or 
                fix_map.get(material_name) or
                (fix_map.get(cleaned_search_key) if cleaned_search_key else None)
            )
            
            remediation_status, canonical_name, verified_cas = determine_remediation_status(raw_name, cas, cleaned_cas, fix)

            # Dilution details from name or columns
            dilution_info = parse_dilution_from_name(raw_name, 'SimpleScentsDIY')
            is_dil = False
            active_material_col = ""
            solvent_col = ""
            active_pct_col = ""
            
            if dilution_info:
                is_dil = True
                act_name, pct, solv_name = dilution_info
                pct_str = f"{pct:.2f}"
                active_material_col = act_name + ' from SimpleScentsDIY'
                solvent_col = (solv_name + ' from SimpleScentsDIY') if solv_name else ""
                active_pct_col = pct_str
            elif row.get('Is_Dilution') == 'TRUE':
                is_dil = True
                # Parse Active_%
                act_pct_val = row.get('Active_%', '').strip()
                try:
                    pct = float(act_pct_val)
                    if pct <= 1.0:
                        pct = pct * 100.0
                    pct_str = f"{pct:.2f}"
                except ValueError:
                    pct_str = ""
                active_material_col = row.get('Active_Material', '').strip()
                if active_material_col and not active_material_col.endswith('from SimpleScentsDIY'):
                    active_material_col += ' from SimpleScentsDIY'
                solvent_col = row.get('Solvent', '').strip()
                if solvent_col and not solvent_col.endswith('from SimpleScentsDIY'):
                    solvent_col += ' from SimpleScentsDIY'
                active_pct_col = pct_str

            cid = fix.get('cid', '') if fix else ''
            pubchem_link = f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}" if cid else ""

            output_rows.append({
                'Product_ID': sku,
                'Supplier': 'SimpleScentsDIY',
                'Material_Name': material_name,
                'Clean_Search_Name': cleaned_search_key,
                'CAS_Number': cas,
                'Remediation_Status': remediation_status,
                'Canonical_Name': canonical_name,
                'Verified_CAS': verified_cas,
                'PubChem_Link': pubchem_link,
                'Price_USD/g': f"{price_usd:.4f}" if isinstance(price_usd, float) else "",
                'Is_Dilution': 'TRUE' if is_dil else 'FALSE',
                'Active_Material': active_material_col,
                'Solvent': solvent_col,
                'Active_%': active_pct_col,
                'Notes': row.get('Notes', '').strip()
            })

    # Save to consolidated output CSV
    fieldnames = [
        'Product_ID', 'Supplier', 'Material_Name', 'Clean_Search_Name', 'CAS_Number', 
        'Remediation_Status', 'Canonical_Name', 'Verified_CAS', 'PubChem_Link', 
        'Price_USD/g', 'Is_Dilution', 'Active_Material', 'Solvent', 'Active_%', 'Notes'
    ]
    
    print(f"Saving {len(output_rows)} rows to {OUTPUT_CSV}...")
    with open(OUTPUT_CSV, mode='w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)
        
    print("Done! Consolidation complete.")

if __name__ == '__main__':
    main()
