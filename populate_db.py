import csv
import sqlite3
import re
import os

DB_PATH = 'perfumery.db'
STRUCT_CSV = 'Perfumery_Structural_Database.csv'
PW_CSV = 'perfumersworld_20260401_updated.csv'
MSR_CSV = 'myskinrecipes_20260317.csv'
SSD_CSV = 'simplescentsdiy_20260317.csv'

EXCHANGE_RATE_USD_THB = 35.0

SOLVENTS_MAP = {
    'DPG': 'DPG',
    'TEC': 'TEC',
    'IPM': 'IPM',
    'BB': 'BB',
    'DEP': 'DEP',
    'PG': 'PG',
    'PEA': 'PEA',
    'ETHANOL': 'Ethanol',
    'ALCOHOL': 'Ethanol'
}

SOLVENT_CIDS = {
    'DPG': '134692469',
    'TEC': '6506',
    'IPM': '8042',
    'BB': '2345',
    'DEP': '6781',
    'PG': '1030',
    'PEA': '6054',
    'Ethanol': '702'
}

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

def parse_price(price_str):
    if not price_str:
        return None
    price_str = price_str.replace(',', '').strip()
    try:
        return float(price_str)
    except ValueError:
        return None

def parse_dilution_from_name(name):
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

def determine_type(name, linked_chem_id, linked_nat_id, is_mixture_flag):
    name_upper = name.upper()
    
    # Check if known solvent
    solvents = ['DPG', 'DIPROPYLENE GLYCOL', 'TEC', 'TRIETHYL CITRATE', 'IPM', 'ISOPROPYL MYRISTATE', 
                'BB', 'BENZYL BENZOATE', 'DEP', 'DIETHYL PHTHALATE', 'PG', 'PROPYLENE GLYCOL', 
                'PEA', 'PHENETHYL ALCOHOL', 'ETHANOL', 'ALCOHOL']
    for s in solvents:
        if s in name_upper:
            if "% IN" not in name_upper and "%  IN" not in name_upper and " IN " not in name_upper:
                return 'Solvent'
                
    if is_mixture_flag:
        return 'Base/Mixture'
    if linked_chem_id:
        return 'Chemical'
    if linked_nat_id:
        return 'Natural'
        
    natural_keywords = ['OIL', 'ESSENTIAL', 'ABSOLUTE', 'RESINOID', 'EXTRACT', 'TINCTURE', 'CONCRETE', 'CO2']
    if any(k in name_upper for k in natural_keywords):
        return 'Natural'
        
    return 'Base/Mixture'

def create_schema(cursor):
    # Chemicals Table (Pure aroma chemicals)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chemicals (
        chemical_id TEXT PRIMARY KEY,
        pubchem_cid TEXT UNIQUE,
        canonical_name TEXT NOT NULL,
        iupac_name TEXT,
        smiles TEXT,
        cas_numbers TEXT,
        molecular_weight REAL,
        logp REAL,
        heavy_atom_count INTEGER,
        num_aromatic_rings INTEGER,
        num_aliphatic_rings INTEGER,
        num_benzene_rings INTEGER,
        num_bicyclic INTEGER,
        num_aliphatic_alcohols INTEGER,
        num_phenols INTEGER,
        num_aldehydes INTEGER,
        num_ketones INTEGER,
        num_esters INTEGER,
        num_lactones INTEGER,
        num_ethers INTEGER,
        num_epoxides INTEGER,
        num_furans INTEGER,
        num_thiazoles INTEGER,
        num_pyridines INTEGER,
        num_thiophenes INTEGER,
        num_primary_amines INTEGER,
        num_secondary_amines INTEGER,
        num_tertiary_amines INTEGER,
        olfactory_family TEXT,
        odor_description TEXT,
        volatility_note TEXT,
        odor_strength TEXT
    )
    """)

    # Naturals Table (Botanicals and complex natural extracts)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS naturals (
        natural_id TEXT PRIMARY KEY,
        common_name TEXT NOT NULL,
        botanical_name TEXT,
        extraction_method TEXT,
        plant_part TEXT,
        origin TEXT,
        olfactory_family TEXT,
        odor_description TEXT,
        volatility_note TEXT
    )
    """)

    # Buyables Table (SKUs from Suppliers)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS buyables (
        buyable_id TEXT PRIMARY KEY,
        product_name TEXT NOT NULL,
        supplier TEXT NOT NULL,
        supplier_sku TEXT,
        price_thb REAL,
        quantity_g REAL,
        product_url TEXT,
        is_mixture BOOLEAN DEFAULT 0,
        type TEXT CHECK(type IN ('Chemical', 'Natural', 'Base/Mixture', 'Solvent')),
        notes TEXT
    )
    """)

    # Buyable Components Table (dilutions/mixtures mapping)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS buyable_components (
        composition_id INTEGER PRIMARY KEY AUTOINCREMENT,
        parent_buyable_id TEXT NOT NULL,
        component_buyable_id TEXT,
        component_chemical_id TEXT,
        component_natural_id TEXT,
        percentage REAL NOT NULL,
        FOREIGN KEY(parent_buyable_id) REFERENCES buyables(buyable_id),
        FOREIGN KEY(component_buyable_id) REFERENCES buyables(buyable_id),
        FOREIGN KEY(component_chemical_id) REFERENCES chemicals(chemical_id),
        FOREIGN KEY(component_natural_id) REFERENCES naturals(natural_id)
    )
    """)
    
    # IFRA Standards Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ifra_standards (
        ifra_id INTEGER PRIMARY KEY AUTOINCREMENT,
        chemical_id TEXT,
        natural_id TEXT,
        category_4_limit_percent REAL,
        restriction_type TEXT,
        FOREIGN KEY(chemical_id) REFERENCES chemicals(chemical_id),
        FOREIGN KEY(natural_id) REFERENCES naturals(natural_id)
    )
    """)

def drop_tables(cursor):
    cursor.execute("DROP TABLE IF EXISTS ifra_standards")
    cursor.execute("DROP TABLE IF EXISTS buyable_components")
    cursor.execute("DROP TABLE IF EXISTS buyables")
    cursor.execute("DROP TABLE IF EXISTS naturals")
    cursor.execute("DROP TABLE IF EXISTS chemicals")

def main():
    print("Re-creating SQLite database at", DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    drop_tables(cursor)
    create_schema(cursor)
    
    # Load Perfumery_Structural_Database.csv to populate chemicals and naturals
    if not os.path.exists(STRUCT_CSV):
        print(f"Error: {STRUCT_CSV} not found.")
        return

    print(f"Reading {STRUCT_CSV}...")
    with open(STRUCT_CSV, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        struct_rows = list(reader)

    chemicals = {}
    naturals = {}
    
    # Matching dictionaries
    url_to_id = {}
    orig_name_to_id = {}
    cleaned_name_to_id = {}
    cas_to_id = {}
    
    print("Extracting chemicals and naturals from structural database...")
    for i, row in enumerate(struct_rows):
        cid = row.get('PubChem_CID', '').strip()
        status = row.get('Status', '').strip()
        cleaned_name = row.get('Cleaned_Name', '').strip()
        original_name = row.get('Original_Name', '').strip()
        product_url = row.get('Product_URL', '').strip()
        wip_cas = row.get('WIP_CAS', '').strip()
        pubchem_cas_all = row.get('PubChem_CAS_All', '').strip()
        
        target_id = None
        
        if cid and cid != 'None' and cid.isdigit():
            chem_id = f"CHEM-{cid}"
            target_id = (chem_id, None)
            if chem_id not in chemicals:
                chemicals[chem_id] = {
                    'chemical_id': chem_id,
                    'pubchem_cid': cid,
                    'canonical_name': row.get('PubChem_Title') or cleaned_name,
                    'smiles': row.get('SMILES'),
                    'cas_numbers': pubchem_cas_all,
                    'molecular_weight': row.get('Molecular_Weight'),
                    'logp': row.get('LogP'),
                    'heavy_atom_count': row.get('Heavy_Atom_Count'),
                    'num_aromatic_rings': row.get('Num_Aromatic_Rings'),
                    'num_aliphatic_rings': row.get('Num_Aliphatic_Rings'),
                    'num_benzene_rings': row.get('Num_Benzene_Rings'),
                    'num_bicyclic': row.get('Num_Bicyclic'),
                    'num_aliphatic_alcohols': row.get('Num_Aliphatic_Alcohols'),
                    'num_phenols': row.get('Num_Phenols'),
                    'num_aldehydes': row.get('Num_Aldehydes'),
                    'num_ketones': row.get('Num_Ketones'),
                    'num_esters': row.get('Num_Esters'),
                    'num_lactones': row.get('Num_Lactones'),
                    'num_ethers': row.get('Num_Ethers'),
                    'num_epoxides': row.get('Num_Epoxides'),
                    'num_furans': row.get('Num_Furans'),
                    'num_thiazoles': row.get('Num_Thiazoles'),
                    'num_pyridines': row.get('Num_Pyridines'),
                    'num_thiophenes': row.get('Num_Thiophenes'),
                    'num_primary_amines': row.get('Num_Primary_Amines'),
                    'num_secondary_amines': row.get('Num_Secondary_Amines'),
                    'num_tertiary_amines': row.get('Num_Tertiary_Amines')
                }
        elif status == 'NATURAL_MIXTURE' or 'Essential Oil' in cleaned_name or 'Absolute' in cleaned_name or 'Oil' in original_name:
            nat_id = f"NAT-{i+1:04d}"
            target_id = (None, nat_id)
            if nat_id not in naturals:
                naturals[nat_id] = {
                    'natural_id': nat_id,
                    'common_name': cleaned_name,
                    'extraction_method': 'Unknown'
                }
                
        if target_id:
            if product_url:
                url_to_id[product_url.lower()] = target_id
            if original_name:
                orig_name_to_id[original_name.lower()] = target_id
                # Also index with stripped name
                stripped_orig = re.sub(r'\s+from\s+.*$', '', original_name, flags=re.I).lower()
                orig_name_to_id[stripped_orig] = target_id
            if cleaned_name:
                cleaned_name_to_id[cleaned_name.lower()] = target_id
            if wip_cas:
                cas_to_id[wip_cas] = target_id
            if pubchem_cas_all:
                for c in pubchem_cas_all.split('|'):
                    c_clean = c.strip()
                    if c_clean:
                        cas_to_id[c_clean] = target_id

    # Insert Chemicals
    print(f"Inserting {len(chemicals)} chemicals into SQLite...")
    for chem in chemicals.values():
        placeholders = ', '.join(['?'] * len(chem))
        columns = ', '.join(chem.keys())
        values = [v if v != '' else None for v in chem.values()]
        cursor.execute(f"INSERT OR IGNORE INTO chemicals ({columns}) VALUES ({placeholders})", values)

    # Insert Naturals
    print(f"Inserting {len(naturals)} naturals into SQLite...")
    for nat in naturals.values():
        placeholders = ', '.join(['?'] * len(nat))
        columns = ', '.join(nat.keys())
        values = [v if v != '' else None for v in nat.values()]
        cursor.execute(f"INSERT OR IGNORE INTO naturals ({columns}) VALUES ({placeholders})", values)

    # Pre-create Solvent buyables
    created_solvents = {}
    print("Pre-creating generic solvents...")
    for solv_name, solv_code in SOLVENTS_MAP.items():
        solv_id = f"SKU-SOLV-{solv_code}"
        if solv_id not in created_solvents:
            cursor.execute("""
                INSERT OR IGNORE INTO buyables (buyable_id, product_name, supplier, is_mixture, type)
                VALUES (?, ?, ?, ?, ?)
            """, (solv_id, solv_code, 'Generic', 0, 'Solvent'))
            created_solvents[solv_code] = solv_id

    def lookup_material_id(url, name, cas, orig_name=None):
        # 1. Match by URL
        if url and url.lower() in url_to_id:
            return url_to_id[url.lower()]
            
        # 2. Match by exact Material Name
        if name and name.lower() in orig_name_to_id:
            return orig_name_to_id[name.lower()]
            
        if orig_name and orig_name.lower() in orig_name_to_id:
            return orig_name_to_id[orig_name.lower()]
            
        # 3. Match by stripped Name
        if name:
            stripped = re.sub(r'\s+from\s+.*$', '', name, flags=re.I).lower()
            if stripped in orig_name_to_id:
                return orig_name_to_id[stripped]
            
            clean_name = clean_for_pubchem(name).lower()
            if clean_name in cleaned_name_to_id:
                return cleaned_name_to_id[clean_name]

        if orig_name:
            stripped = re.sub(r'\s+from\s+.*$', '', orig_name, flags=re.I).lower()
            if stripped in orig_name_to_id:
                return orig_name_to_id[stripped]
            
            clean_name = clean_for_pubchem(orig_name).lower()
            if clean_name in cleaned_name_to_id:
                return cleaned_name_to_id[clean_name]
                
        # 4. Match by CAS
        if cas:
            clean_cas = cas.strip().split('|')[0].split('\n')[0].strip()
            if clean_cas in cas_to_id:
                return cas_to_id[clean_cas]
                
        return None, None

    # Load and process PerfumersWorld
    print(f"Processing PerfumersWorld from {PW_CSV}...")
    pw_count = 0
    with open(PW_CSV, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            sku = row['Product_ID'].strip()
            name = row['Material_Name']
            cas = row['CAS_Number']
            price_usd = row.get('Price_US/g')
            url = row.get('Source_URL') or (f"https://www.perfumersworld.com/view.php?pro_id={sku}" if sku else "")
            is_dil = row.get('Is_Dilution') == 'TRUE'
            
            if not sku:
                m_url = re.search(r'pro_id=([A-Z0-9]+)', url, re.IGNORECASE)
                if m_url:
                    sku = m_url.group(1)
                else:
                    sku = f"PWGEN-{pw_count}"
            
            buyable_id = f"SKU-PW-{sku}"
            price_thb = float(price_usd) * EXCHANGE_RATE_USD_THB if price_usd else None
            is_mixture = 1 if is_dil or sku.startswith('6') else 0
            
            # Lookup chemical/natural ID
            chem_id, nat_id = lookup_material_id(url, name, cas)
            
            # If not resolved by URL/Name, check if the active component is resolved
            if not chem_id and not nat_id and is_dil:
                act_name = row.get('Active_Material')
                chem_id, nat_id = lookup_material_id(None, act_name, None)
                
            b_type = determine_type(name, chem_id, nat_id, is_mixture)
            
            cursor.execute("""
                INSERT INTO buyables (buyable_id, product_name, supplier, supplier_sku, price_thb, quantity_g, product_url, is_mixture, type, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (buyable_id, name, 'PerfumersWorld', sku, price_thb, 1.0, url, is_mixture, b_type, row.get('Notes')))
            
            # Link components
            if is_dil:
                act_pct_raw = float(row.get('Active_%', '1.0'))
                act_pct = act_pct_raw * 100.0 if act_pct_raw <= 1.0 else act_pct_raw
                
                # Active component
                if chem_id or nat_id:
                    cursor.execute("""
                        INSERT INTO buyable_components (parent_buyable_id, component_chemical_id, component_natural_id, percentage)
                        VALUES (?, ?, ?, ?)
                    """, (buyable_id, chem_id, nat_id, act_pct))
                
                # Solvent component
                solv_name = row.get('Solvent')
                solv_code = None
                if solv_name:
                    for key, code in SOLVENTS_MAP.items():
                        if key.lower() in solv_name.lower():
                            solv_code = code
                            break
                if solv_code:
                    solv_sku = created_solvents.get(solv_code)
                    cursor.execute("""
                        INSERT INTO buyable_components (parent_buyable_id, component_buyable_id, percentage)
                        VALUES (?, ?, ?)
                    """, (buyable_id, solv_sku, 100.0 - act_pct))
            elif chem_id or nat_id:
                cursor.execute("""
                    INSERT INTO buyable_components (parent_buyable_id, component_chemical_id, component_natural_id, percentage)
                    VALUES (?, ?, ?, 100.0)
                """, (buyable_id, chem_id, nat_id))
            pw_count += 1

    # Load and process MySkinRecipes
    print(f"Processing MySkinRecipes from {MSR_CSV}...")
    msr_count = 0
    with open(MSR_CSV, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            sku = row['Product_ID'].strip()
            name_orig = row['Material_Name'].strip()
            name = clean_msr_name(row.get('Product_URL', ''), name_orig)
            cas = row['CAS_Number']
            package_size = row.get('Package_Size')
            url = row.get('Product_URL', '')
            
            if not sku:
                # Match /3971-ethyl-anthranilatefema-2421.html -> 3971
                m_url = re.search(r'/(\d+)-', url)
                if m_url:
                    sku = m_url.group(1)
                else:
                    sku = f"MSRGEN-{msr_count}"
            
            buyable_id = f"SKU-MSR-{sku}"
            quantity_g = parse_quantity_g(package_size)
            price_thb = parse_price(row.get('Price_THB_total'))
            if price_thb is None and row.get('Price_THB/g'):
                price_thb = parse_price(row.get('Price_THB/g')) * quantity_g
                
            dilution_info = parse_dilution_from_name(name)
            is_mixture = 1 if dilution_info or row.get('Is_Dilution') == 'TRUE' else 0
            
            chem_id, nat_id = lookup_material_id(url, name, cas, orig_name=name_orig)
            
            # If name matches dilution
            if not chem_id and not nat_id and dilution_info:
                act_name, _, _ = dilution_info
                chem_id, nat_id = lookup_material_id(None, act_name, None)
                
            b_type = determine_type(name, chem_id, nat_id, is_mixture)
            
            cursor.execute("""
                INSERT INTO buyables (buyable_id, product_name, supplier, supplier_sku, price_thb, quantity_g, product_url, is_mixture, type, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (buyable_id, name, 'MySkinRecipes', sku, price_thb, quantity_g, url, is_mixture, b_type, row.get('Notes')))
            
            if dilution_info:
                _, act_pct, solv_code = dilution_info
                # Active component
                if chem_id or nat_id:
                    cursor.execute("""
                        INSERT INTO buyable_components (parent_buyable_id, component_chemical_id, component_natural_id, percentage)
                        VALUES (?, ?, ?, ?)
                    """, (buyable_id, chem_id, nat_id, act_pct))
                # Solvent component
                if solv_code:
                    solv_sku = created_solvents.get(solv_code)
                    cursor.execute("""
                        INSERT INTO buyable_components (parent_buyable_id, component_buyable_id, percentage)
                        VALUES (?, ?, ?)
                    """, (buyable_id, solv_sku, 100.0 - act_pct))
            elif chem_id or nat_id:
                cursor.execute("""
                    INSERT INTO buyable_components (parent_buyable_id, component_chemical_id, component_natural_id, percentage)
                    VALUES (?, ?, ?, 100.0)
                """, (buyable_id, chem_id, nat_id))
            msr_count += 1

    # Load and process SimpleScentsDIY
    print(f"Processing SimpleScentsDIY from {SSD_CSV}...")
    ssd_count = 0
    with open(SSD_CSV, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            sku = row['Product_ID'].strip()
            name = row['Material_Name']
            cas = row['CAS_Number']
            package_size = row.get('Package_Size')
            url = row.get('Product_URL', '')
            
            if not sku:
                # Match /product/36462/roomspray -> 36462
                m_url = re.search(r'/product/(\d+)', url)
                if m_url:
                    sku = m_url.group(1)
                else:
                    sku = f"SSDGEN-{ssd_count}"
            
            buyable_id = f"SKU-SSD-{sku}"
            quantity_g = parse_quantity_g(package_size)
            price_thb = parse_price(row.get('Price_THB_total'))
            if price_thb is None and row.get('Price_THB/g'):
                price_thb = parse_price(row.get('Price_THB/g')) * quantity_g
                
            dilution_info = parse_dilution_from_name(name)
            is_mixture = 1 if dilution_info or row.get('Is_Dilution') == 'TRUE' else 0
            
            chem_id, nat_id = lookup_material_id(url, name, cas)
            
            # If name matches dilution
            if not chem_id and not nat_id and dilution_info:
                act_name, _, _ = dilution_info
                chem_id, nat_id = lookup_material_id(None, act_name, None)
                
            b_type = determine_type(name, chem_id, nat_id, is_mixture)
            
            cursor.execute("""
                INSERT INTO buyables (buyable_id, product_name, supplier, supplier_sku, price_thb, quantity_g, product_url, is_mixture, type, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (buyable_id, name, 'SimpleScentsDIY', sku, price_thb, quantity_g, url, is_mixture, b_type, row.get('Notes')))
            
            if dilution_info:
                _, act_pct, solv_code = dilution_info
                # Active component
                if chem_id or nat_id:
                    cursor.execute("""
                        INSERT INTO buyable_components (parent_buyable_id, component_chemical_id, component_natural_id, percentage)
                        VALUES (?, ?, ?, ?)
                    """, (buyable_id, chem_id, nat_id, act_pct))
                # Solvent component
                if solv_code:
                    solv_sku = created_solvents.get(solv_code)
                    cursor.execute("""
                        INSERT INTO buyable_components (parent_buyable_id, component_buyable_id, percentage)
                        VALUES (?, ?, ?)
                    """, (buyable_id, solv_sku, 100.0 - act_pct))
            elif chem_id or nat_id:
                cursor.execute("""
                    INSERT INTO buyable_components (parent_buyable_id, component_chemical_id, component_natural_id, percentage)
                    VALUES (?, ?, ?, 100.0)
                """, (buyable_id, chem_id, nat_id))
            ssd_count += 1

    conn.commit()
    
    # Run stats
    print("\n--- Statistics ---")
    cursor.execute("SELECT COUNT(*) FROM chemicals")
    print(f"Chemicals: {cursor.fetchone()[0]}")
    cursor.execute("SELECT COUNT(*) FROM naturals")
    print(f"Naturals: {cursor.fetchone()[0]}")
    cursor.execute("SELECT supplier, COUNT(*) FROM buyables GROUP BY supplier")
    for row in cursor.fetchall():
        print(f"Buyables ({row[0]}): {row[1]}")
    cursor.execute("SELECT COUNT(*) FROM buyable_components")
    print(f"Buyable components linked: {cursor.fetchone()[0]}")
    
    conn.close()
    print("\nDatabase populate successfully completed!")

if __name__ == '__main__':
    main()
