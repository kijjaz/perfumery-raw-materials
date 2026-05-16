import re

INPUT_HTML = "20260401 Perfume Supplies _ PerfumersWorld.html"

with open(INPUT_HTML, "r", encoding="utf-8") as f:
    html = f.read()

# Pattern to find each product row/links
# Group 1: SKU, Group 2: Name, Group 3: Price
# Link in HTML: <a style="float:left" data-toggle="modal" data-target="#linkModal" target="_pw-view" href="https://perfumersworld.com/view.php?pro_id=4EW07503" title="2 3-Dimethyl Pyrazine">2 3-Dimethyl Pyrazine</a>
# Price link: <a style="float:right;" target="_pw-view" href="https://perfumersworld.com/view.php?pro_id=4EW07503" title="2 3-Dimethyl Pyrazine">4EW07503 @ US$2.69/gram</a>

row_pattern = re.compile(
    r'<tr[^>]*>.*?href="[^"]*view\.php\?pro_id=([^"]+)"[^>]*title="([^"]+)"[^>]*>.*?@ US\$([\d,.]+)/gram</a>.*?</tr>',
    re.DOTALL | re.IGNORECASE
)

matches = list(row_pattern.finditer(html))
print(f"Total matches: {len(matches)}")

for i, m in enumerate(matches[:5]):
    print(f"Match {i+1}: SKU={m.group(1)}, Name={m.group(2)}, Price={m.group(3)}")
