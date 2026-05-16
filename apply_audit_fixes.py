import csv
import os
import re

# --- Configuration ---
AUDIT_CSV = 'Perfumery_Raw_Materials_Audit_Master.csv'
WIP_DATABASE = '20260401 Kijjaz - miniChihuahua 0.1.10 WIP PW & SimpleScentsDIY Edition - 🌿 RawMaterials.csv'
OUTPUT_FILE = '🌿 RawMaterials_v0_1_11_Cleaned.csv'
BASE_DIR = '/Users/kijjaz/Desktop/Antigravity/2026/20260317 Perfumery Raw Materials Update'

def clean_for_pubchem(name):
    if not name: return ""
    name = re.sub(r'[^\x00-\x7F]+', '', name) # Remove non-ASCII
    name = re.split(r'[\\/|]', name)[0] # Take first part
    name = name.strip(' ,-—|/')
    return name

def main():
    audit_path = os.path.join(BASE_DIR, AUDIT_CSV)
    wip_path = os.path.join(BASE_DIR, WIP_DATABASE)
    output_path = os.path.join(BASE_DIR, OUTPUT_FILE)

    if not os.path.exists(audit_path):
        print(f"Error: Audit file {AUDIT_CSV} not found.")
        return

    # 1. Load Audit Fix Map
    # Key: Original_Name -> {verified_cas, canonical_title, status, pc_cas_all}
    fix_map = {}
    print(f"Loading Fix Map from {AUDIT_CSV}...")
    with open(audit_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            orig_name = row.get('Original_Name')
            pc_cas_all = row.get('PubChem_CAS_All', '').split('|')
            best_pc_cas = pc_cas_all[0] if pc_cas_all and pc_cas_all[0] else ""
            
            fix_map[orig_name] = {
                "verified_cas": best_pc_cas,
                "canonical_title": row.get('PubChem_Title', ''),
                "status": row.get('Status', ''),
                "synonyms": row.get('PubChem_Synonyms_Top10', '')
            }

    # 2. Process WIP Database
    if not os.path.exists(wip_path):
        print(f"Error: WIP Database {WIP_DATABASE} not found.")
        return

    print(f"Applying fixes to {WIP_DATABASE}...")
    updated_rows = []
    fieldnames = []

    with open(wip_path, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        # Add new columns
        new_cols = ['Verified_CAS', 'Canonical_Name', 'Remediation_Status']
        for col in new_cols:
            if col not in fieldnames:
                fieldnames.insert(fieldnames.index('CAS_Number') + 1, col)

        for row in reader:
            orig_name = row.get('Material_Name')
            wip_cas = row.get('CAS_Number', '').strip()
            
            # Default values
            row['Verified_CAS'] = wip_cas
            row['Canonical_Name'] = ""
            row['Remediation_Status'] = "VERIFIED"

            # Check Formatting Fixes (Auto)
            # Remove leading zeros e.g. 0140-11-4 -> 140-11-4
            normalized_wip_cas = re.sub(r'^0+', '', wip_cas)
            if normalized_wip_cas != wip_cas and re.match(r'^\d+-\d+-\d+$', normalized_wip_cas):
                row['Verified_CAS'] = normalized_wip_cas
                row['Remediation_Status'] = "FORMATTING_FIX"

            # Apply Audit Fixes
            if orig_name in fix_map:
                fix = fix_map[orig_name]
                row['Canonical_Name'] = fix['canonical_title']
                
                if fix['status'] == 'WIP_DISCREPANCY':
                    row['Verified_CAS'] = fix['verified_cas']
                    row['Remediation_Status'] = "FIXED_FROM_AUDIT"
                elif fix['status'] == 'DATA_GAP':
                    row['Remediation_Status'] = "DATA_GAP_MANUAL_CHECK"
                elif fix['status'] == 'NATURAL_MIXTURE':
                    row['Remediation_Status'] = "NATURAL_MIXTURE"
                elif fix['status'] == 'WIP_VERIFIED' and row['Remediation_Status'] != "FORMATTING_FIX":
                    row['Remediation_Status'] = "VERIFIED_MATCH"

            updated_rows.append(row)

    # 3. Save Cleaned Database
    with open(output_path, mode='w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(updated_rows)

    print(f"Remediation complete! Cleaned database saved at: {OUTPUT_FILE}")
    print(f"Total rows processed: {len(updated_rows)}")

if __name__ == "__main__":
    main()
