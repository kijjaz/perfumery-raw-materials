import csv
import re
import os

# --- CAS Validation Logic (from validate_cas.py) ---

def validate_cas_check_digit(cas_str):
    clean_cas = cas_str.strip()
    match = re.match(r'^(\d{2,7})-(\d{2})-(\d)$', clean_cas)
    if not match:
        return False, "Format Mismatch"
    
    part1, part2, check_digit = match.groups()
    digits_str = part1 + part2
    digits = [int(d) for d in digits_str]
    
    checksum = 0
    for i, digit in enumerate(reversed(digits)):
        weight = i + 1
        checksum += weight * digit
        
    calculated_check = checksum % 10
    return (calculated_check == int(check_digit)), f"Checksum Fail (Expected {calculated_check}, Got {check_digit})"

def process_cas_entry(cas_entry):
    if not cas_entry: return []
    entry = cas_entry.strip()
    if entry.lower() in ["mixture", "confidential", "not found", "mixture (perfume base)"]:
        return []
    
    issues = []
    normalized_entry = entry.replace('\n', '|').replace('\r', '')
    parts = normalized_entry.split('|')
    
    for part in parts:
        part = part.strip()
        if not part or re.match(r'^0\.\d+$', part) or re.match(r'^\d+(\.\d+)?%$', part):
            continue
        if re.search(r'\d+-\d{2}-\d', part):
            is_valid, reason = validate_cas_check_digit(part)
            if not is_valid:
                issues.append(f"Invalid CAS '{part}': {reason}")
    return issues

# --- Name Normalization for Comparison ---

def normalize_name(name):
    if not name: return ""
    # Remove supplier suffixes
    name = re.sub(r'\s+from\s+(PerfumersWorld|MySkinRecipes|SimpleScentsDIY)', '', name, flags=re.I)
    # Remove common descriptors
    name = re.sub(r'\s+(Essential\s+Oil|Pure|Natural|Organic|Absolute|Resinoid|Fixed\s+Oil)', '', name, flags=re.I)
    # Remove dilution indicators (e.g. "10% in DPG")
    name = re.sub(r'\s+\d+%.*$', '', name, flags=re.I)
    # Basic cleanup
    name = name.lower().strip()
    # Normalize spaces
    name = " ".join(name.split())
    return name

# --- Main Validation Logic ---

def run_audit():
    suppliers = {
        'PerfumersWorld': 'perfumersworld_20260401.csv',
        'MySkinRecipes': 'myskinrecipes_20260317.csv',
        'SimpleScentsDIY': 'simplescentsdiy_20260317.csv'
    }
    
    all_data = []
    name_to_cas = {} # normalized_name -> set of (cas, supplier)
    
    for supplier_name, filename in suppliers.items():
        path = os.path.join('/Users/kijjaz/Desktop/Antigravity/2026/20260317 Perfumery Raw Materials Update', filename)
        if not os.path.exists(path):
            print(f"Warning: {filename} not found.")
            continue
            
        print(f"Processing {supplier_name}...")
        with open(path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get('Material_Name', '')
                cas = row.get('CAS_Number', '')
                prod_id = row.get('Product_ID', '')
                
                # Internal Validation
                issues = process_cas_entry(cas)
                
                # Cross-Supplier Data Collection
                norm_name = normalize_name(name)
                # Only track primary materials (not obviously dilutions for the name check)
                if not row.get('Is_Dilution') == 'TRUE' and norm_name:
                    if norm_name not in name_to_cas:
                        name_to_cas[norm_name] = set()
                    if cas and cas.lower() not in ["mixture", "not found", "mixture (perfume base)"]:
                        name_to_cas[norm_name].add((cas, supplier_name))
                
                all_data.append({
                    'supplier': supplier_name,
                    'prod_id': prod_id,
                    'name': name,
                    'norm_name': norm_name,
                    'cas': cas,
                    'issues': issues
                })

    # Generate Report
    report_path = '/Users/kijjaz/Desktop/Antigravity/2026/20260317 Perfumery Raw Materials Update/CAS_Quality_Audit.md'
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# CAS Quality Audit Report\n\n")
        
        # 1. Checksum Failures
        f.write("## 1. Checksum & Format Failures\n")
        f.write("| Supplier | Product ID | Material Name | CAS | Issues |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- |\n")
        fail_count = 0
        for item in all_data:
            if item['issues']:
                fail_count += 1
                cas_disp = item['cas'].replace('\n', '<br>')
                f.write(f"| {item['supplier']} | {item['prod_id']} | {item['name']} | {cas_disp} | {'<br>'.join(item['issues'])} |\n")
        if fail_count == 0:
            f.write("| None | | | | |\n")
        f.write("\n")
        
        # 2. Supplier Discrepancies
        f.write("## 2. Supplier Discrepancies (Same Name, Different CAS)\n")
        f.write("| Normalized Name | Supplier: CAS | Status |\n")
        f.write("| :--- | :--- | :--- |\n")
        disc_count = 0
        for norm_name, cas_list in sorted(name_to_cas.items()):
            # Filter unique CAS numbers (ignoring minor formatting)
            unique_cas = {}
            for cas, supp in cas_list:
                clean_cas = cas.strip().replace('\n', '|')
                if clean_cas not in unique_cas:
                    unique_cas[clean_cas] = []
                unique_cas[clean_cas].append(supp)
            
            if len(unique_cas) > 1:
                disc_count += 1
                cas_str = "<br>".join([f"{', '.join(supps)}: `{cas}`" for cas, supps in unique_cas.items()])
                f.write(f"| {norm_name} | {cas_str} | **SUSPICIOUS** |\n")
        
        if disc_count == 0:
            f.write("| None | | |\n")
            
        f.write(f"\n\n**Audit Summary:**\n- Checksum Fails: {fail_count}\n- Supplier Mismatches: {disc_count}\n")

    print(f"Audit complete. Report generated at {report_path}")

if __name__ == "__main__":
    run_audit()
