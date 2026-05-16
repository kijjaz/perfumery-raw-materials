import csv
import sqlite3
import re
import os

CSV_FILE = 'Perfumery_Structural_Database.csv'
DB_FILE = 'perfumery.db'

def main():
    if not os.path.exists(CSV_FILE):
        print(f"Error: {CSV_FILE} not found.")
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    print(f"Reading {CSV_FILE}...")
    with open(CSV_FILE, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Dictionaries to ensure uniqueness
    chemicals = {}
    naturals = {}
    solvents_map = {
        'DPG': 'DPG',
        'TEC': 'TEC',
        'IPM': 'IPM',
        'PEA': 'PEA', # Phenyl Ethyl Alcohol
        'ETHANOL': 'Ethanol',
        'ALCOHOL': 'Ethanol'
    }
    
    # 1. First Pass: Extract Chemicals and Naturals
    print("Extracting chemicals and naturals...")
    for i, row in enumerate(rows):
        cid = row.get('PubChem_CID', '').strip()
        status = row.get('Status', '').strip()
        cleaned_name = row.get('Cleaned_Name', '').strip()
        
        if cid and cid != 'None' and cid.isdigit():
            chem_id = f"CHEM-{cid}"
            if chem_id not in chemicals:
                chemicals[chem_id] = {
                    'chemical_id': chem_id,
                    'pubchem_cid': cid,
                    'canonical_name': row.get('PubChem_Title') or cleaned_name,
                    'smiles': row.get('SMILES'),
                    'cas_numbers': row.get('PubChem_CAS_All'),
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
        elif status == 'NATURAL_MIXTURE' or 'Essential Oil' in cleaned_name or 'Absolute' in cleaned_name:
            nat_id = f"NAT-{i+1:04d}"
            # Store the generated ID in the row for later reference
            row['_natural_id'] = nat_id
            naturals[nat_id] = {
                'natural_id': nat_id,
                'common_name': cleaned_name,
                'extraction_method': 'Unknown'
            }

    # Insert Chemicals
    for chem in chemicals.values():
        placeholders = ', '.join(['?'] * len(chem))
        columns = ', '.join(chem.keys())
        # Replace empty strings with None
        values = [v if v != '' else None for v in chem.values()]
        cursor.execute(f"INSERT OR IGNORE INTO chemicals ({columns}) VALUES ({placeholders})", values)

    # Insert Naturals
    for nat in naturals.values():
        placeholders = ', '.join(['?'] * len(nat))
        columns = ', '.join(nat.keys())
        values = [v if v != '' else None for v in nat.values()]
        cursor.execute(f"INSERT OR IGNORE INTO naturals ({columns}) VALUES ({placeholders})", values)

    # 2. Second Pass: Extract Buyables and Dilution Linking
    print("Extracting buyables and components...")
    
    # Pre-create solvent SKUs so we can link to them
    created_solvents = {}
    for solv_name in solvents_map.values():
        solv_id = f"SKU-SOLV-{solv_name.upper()}"
        if solv_id not in created_solvents:
            cursor.execute("""
                INSERT OR IGNORE INTO buyables (buyable_id, product_name, supplier, is_mixture, type)
                VALUES (?, ?, ?, ?, ?)
            """, (solv_id, solv_name, 'Generic', 0, 'Solvent'))
            created_solvents[solv_name] = solv_id

    for i, row in enumerate(rows):
        orig_name = row.get('Original_Name', '').strip()
        if not orig_name:
            continue
            
        buyable_id = f"SKU-{i+1:05d}"
        supplier = "Unknown"
        if "from" in orig_name:
            parts = orig_name.rsplit("from", 1)
            supplier = parts[1].strip()
            
        product_url = row.get('Product_URL', '')
        
        # Determine type and parse mixture
        is_mixture = 0
        b_type = 'Chemical'
        
        cid = row.get('PubChem_CID', '').strip()
        status = row.get('Status', '').strip()
        
        if status == 'NATURAL_MIXTURE' or '_natural_id' in row:
            b_type = 'Natural'
        elif not cid or cid == 'None':
            b_type = 'Base/Mixture'
            
        # Parse % in Solvent
        match = re.search(r'(\d+(?:\.\d+)?)%\s+in\s+([A-Za-z0-9_]+)', orig_name, re.IGNORECASE)
        active_percent = 100.0
        solvent_name = None
        
        if match:
            is_mixture = 1
            b_type = 'Base/Mixture'
            try:
                active_percent = float(match.group(1))
            except:
                active_percent = 10.0
            solvent_name = match.group(2).upper()
        
        # Insert Buyable
        cursor.execute("""
            INSERT INTO buyables (buyable_id, product_name, supplier, product_url, is_mixture, type)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (buyable_id, orig_name, supplier, product_url, is_mixture, b_type))
        
        # Insert Linker component for the Active Material
        component_chem = f"CHEM-{cid}" if (cid and cid.isdigit()) else None
        component_nat = row.get('_natural_id') if not component_chem else None
        
        # If we have an active component to link
        if component_chem or component_nat:
            cursor.execute("""
                INSERT INTO buyable_components (parent_buyable_id, component_chemical_id, component_natural_id, percentage)
                VALUES (?, ?, ?, ?)
            """, (buyable_id, component_chem, component_nat, active_percent))
            
        # Insert Linker component for the Solvent
        if solvent_name:
            # Match solvent to our generic solvent SKUs
            mapped_solv = solvents_map.get(solvent_name)
            solv_id = created_solvents.get(mapped_solv) if mapped_solv else None
            
            if solv_id:
                solvent_percent = 100.0 - active_percent
                cursor.execute("""
                    INSERT INTO buyable_components (parent_buyable_id, component_buyable_id, percentage)
                    VALUES (?, ?, ?)
                """, (buyable_id, solv_id, solvent_percent))

    conn.commit()
    conn.close()
    print("Migration complete!")

if __name__ == "__main__":
    main()
