import urllib.request
import json
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

url = "https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/176/JSON?heading=CAS"
with urllib.request.urlopen(url, context=ctx) as r:
    data = json.loads(r.read().decode('utf-8'))
    print(json.dumps(data, indent=2))
