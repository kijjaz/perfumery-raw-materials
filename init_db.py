import sqlite3
import os

DB_PATH = 'perfumery.db'

def create_schema(cursor):
    # 1. Chemicals Table (The pure aroma chemicals)
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

    # 2. Naturals Table (Botanicals and Complex natural extracts)
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

    # 3. Buyables Table (SKUs from Suppliers)
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

    # 4. Buyable Components Table (Linker for Dilutions/Mixtures)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS buyable_components (
        composition_id INTEGER PRIMARY KEY AUTOINCREMENT,
        parent_buyable_id TEXT NOT NULL,
        component_buyable_id TEXT, -- If it's a dilution in a solvent that we buy
        component_chemical_id TEXT, -- If we know the exact pure chemical
        component_natural_id TEXT,  -- If it's a natural
        percentage REAL NOT NULL,
        FOREIGN KEY(parent_buyable_id) REFERENCES buyables(buyable_id),
        FOREIGN KEY(component_buyable_id) REFERENCES buyables(buyable_id),
        FOREIGN KEY(component_chemical_id) REFERENCES chemicals(chemical_id),
        FOREIGN KEY(component_natural_id) REFERENCES naturals(natural_id)
    )
    """)
    
    # 5. IFRA Standards (For future regulatory updates)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ifra_standards (
        ifra_id INTEGER PRIMARY KEY AUTOINCREMENT,
        chemical_id TEXT,
        natural_id TEXT,
        category_4_limit_percent REAL, -- Fine fragrance limit
        restriction_type TEXT,
        FOREIGN KEY(chemical_id) REFERENCES chemicals(chemical_id),
        FOREIGN KEY(natural_id) REFERENCES naturals(natural_id)
    )
    """)

def main():
    print(f"Initializing {DB_PATH}...")
    if os.path.exists(DB_PATH):
        print(f"Warning: {DB_PATH} already exists. Extending schema.")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    create_schema(cursor)
    
    conn.commit()
    conn.close()
    print("Database schema successfully created!")

if __name__ == "__main__":
    main()
