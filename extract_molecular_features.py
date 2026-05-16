import csv
import json
import os
import rdkit
from rdkit import Chem
from rdkit.Chem import Descriptors, Fragments

# --- Configuration ---
MASTER_CSV = 'Perfumery_Raw_Materials_Audit_Master.csv'
SMILES_CACHE = 'pubchem_smiles_cache.json'
OUTPUT_CSV = 'Perfumery_Structural_Database.csv'

def main():
    print(f"Loading SMILES cache from {SMILES_CACHE}...")
    if not os.path.exists(SMILES_CACHE):
        print(f"Error: {SMILES_CACHE} not found.")
        return
        
    with open(SMILES_CACHE, 'r') as f:
        smiles_cache = json.load(f)

    print(f"Reading master CSV from {MASTER_CSV}...")
    with open(MASTER_CSV, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        rows = list(reader)

    # Add new fieldnames
    new_fields = [
        "SMILES",
        "Molecular_Weight",
        "Heavy_Atom_Count",
        "LogP",
        "Num_Aromatic_Rings",
        "Num_Aliphatic_Rings",
        "Num_Aromatic_Heterocycles",
        "Num_Aliphatic_Heterocycles",
        "Num_Benzene_Rings",
        "Num_Bicyclic",
        "Num_Aliphatic_Alcohols",
        "Num_Phenols",
        "Num_Aldehydes",
        "Num_Ketones",
        "Num_Esters",
        "Num_Lactones",
        "Num_Ethers",
        "Num_Epoxides",
        "Num_Furans",
        "Num_Thiazoles",
        "Num_Pyridines",
        "Num_Thiophenes",
        "Num_Primary_Amines",
        "Num_Secondary_Amines",
        "Num_Tertiary_Amines"
    ]
    
    for f in new_fields:
        if f not in fieldnames:
            fieldnames.append(f)

    print("Extracting features with RDKit...")
    processed_count = 0
    error_count = 0

    # RDKit fragments mapping
    fragments_mapping = {
        "Num_Benzene_Rings": Fragments.fr_benzene,
        "Num_Bicyclic": Fragments.fr_bicyclic,
        "Num_Aliphatic_Alcohols": Fragments.fr_Al_OH,
        "Num_Phenols": Fragments.fr_phenol,
        "Num_Aldehydes": Fragments.fr_aldehyde,
        "Num_Ketones": Fragments.fr_ketone,
        "Num_Esters": Fragments.fr_ester,
        "Num_Lactones": Fragments.fr_lactone,
        "Num_Ethers": Fragments.fr_ether,
        "Num_Epoxides": Fragments.fr_epoxide,
        "Num_Furans": Fragments.fr_furan,
        "Num_Thiazoles": Fragments.fr_thiazole,
        "Num_Pyridines": Fragments.fr_pyridine,
        "Num_Thiophenes": Fragments.fr_thiophene,
        "Num_Primary_Amines": Fragments.fr_NH2,
        "Num_Secondary_Amines": Fragments.fr_NH1,
        "Num_Tertiary_Amines": Fragments.fr_NH0,
    }

    for row in rows:
        # Initialize new fields to empty
        for f in new_fields:
            row[f] = ""

        cid = row.get('PubChem_CID', '').strip()
        if not cid or cid == 'None' or not cid.isdigit():
            continue

        cache_entry = smiles_cache.get(cid)
        if not cache_entry:
            continue

        smiles = cache_entry.get('IsomericSMILES') or cache_entry.get('CanonicalSMILES')
        if not smiles:
            continue

        row['SMILES'] = smiles

        # Parse with RDKit
        mol = Chem.MolFromSmiles(smiles)
        if not mol:
            error_count += 1
            continue

        try:
            row['Molecular_Weight'] = round(Descriptors.ExactMolWt(mol), 2)
            row['Heavy_Atom_Count'] = mol.GetNumHeavyAtoms()
            row['LogP'] = round(Descriptors.MolLogP(mol), 2)
            
            row['Num_Aromatic_Rings'] = Descriptors.NumAromaticRings(mol)
            row['Num_Aliphatic_Rings'] = Descriptors.NumAliphaticRings(mol)
            row['Num_Aromatic_Heterocycles'] = Descriptors.NumAromaticHeterocycles(mol)
            row['Num_Aliphatic_Heterocycles'] = Descriptors.NumAliphaticHeterocycles(mol)

            # Functional Groups
            for field, func in fragments_mapping.items():
                row[field] = func(mol)
                
            processed_count += 1
        except Exception as e:
            error_count += 1
            print(f"Error processing CID {cid}: {e}")

    print(f"Writing {len(rows)} rows to {OUTPUT_CSV}...")
    with open(OUTPUT_CSV, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        
    print(f"Done. Successfully processed {processed_count} molecules. Errors: {error_count}")

if __name__ == "__main__":
    main()
