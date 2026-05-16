import rdkit
from rdkit import Chem
from rdkit.Chem import Descriptors

smiles = [
    "CC(=O)C1=CC=C(C=C1)C(C)(C)C", # Celestolide (Musk)
    "CC1=CC=C(C=C1)C(C)C", # p-Cymene
    "C1=CC=C2C(=C1)C=CN2", # Indole
    "CC1=C(C=C(C=C1)O)C(C)(C)C" # BHT (Phenol)
]

for s in smiles:
    mol = Chem.MolFromSmiles(s)
    print(f"SMILES: {s}")
    print(f"  MW: {Descriptors.ExactMolWt(mol):.2f}")
    print(f"  Aromatic Rings: {Descriptors.NumAromaticRings(mol)}")
    print(f"  Aliphatic Rings: {Descriptors.NumAliphaticRings(mol)}")
    print(f"  Heterocycles (Arom): {Descriptors.NumAromaticHeterocycles(mol)}")
    
    # SMARTS
    patterns = {
        "Benzene": "c1ccccc1",
        "Alcohol": "[CX4][OH]",
        "Phenol": "c[OH]",
        "Ketone": "[#6][CX3](=O)[#6]",
        "Aldehyde": "[CX3H1](=O)[#6]",
        "Ester": "[#6][CX3](=O)[OX2H0][#6]",
        "Ether": "[OD2]([#6])[#6]",
    }
    
    for name, smarts in patterns.items():
        pat = Chem.MolFromSmarts(smarts)
        matches = mol.GetSubstructMatches(pat)
        print(f"  {name}: {len(matches)}")
