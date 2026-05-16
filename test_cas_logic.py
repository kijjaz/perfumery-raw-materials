import urllib.request, json, ssl, re

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

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

def test_cas_fetch(cid):
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/{cid}/JSON?heading=CAS"
    req = urllib.request.Request(url, headers={'User-Agent': 'CASValidator/2.0'})
    with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
        data = json.loads(r.read().decode('utf-8'))
        cas_section = find_section(data.get("Record", {}), "CAS")
        if not cas_section:
            print("No CAS section found!")
            return
        
        cas_list = []
        for info in cas_section.get("Information", []):
            val_obj = info.get("Value", {})
            for val in val_obj.get("StringWithMarkup", []):
                s = val.get("String")
                if s and re.match(r'^\d+-\d+-\d+$', s):
                    cas_list.append(s)
        print(f"Found CAS: {cas_list}")

test_cas_fetch(176) # Acetic Acid
