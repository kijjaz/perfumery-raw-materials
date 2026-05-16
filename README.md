# Perfumery Raw Materials Database

A collection of tools and data for managing, auditing, and analyzing perfumery raw materials.

## Features
- **Supplier Scraping**: Scripts for PerfumersWorld, MySkinRecipes, and SimpleScentsDIY.
- **Data Auditing**: CAS number validation and quality audits against PubChem.
- **Structural Analysis**: Extraction of molecular features using RDKit and SMILES data.
- **Unified Database**: Consolidates materials from multiple suppliers into a single SQLite database and master CSV.

## Key Files
- `Perfumery_Raw_Materials_Audit_Master.csv`: The main consolidated dataset.
- `perfumery.db`: SQLite version of the database.
- `scrape_*.py`: Individual scraping scripts for each vendor.
- `fetch_smiles.py` & `extract_molecular_features.py`: Tools for chemical data enrichment.

## Usage
Most scripts are standalone Python utilities. Ensure you have the required dependencies (pandas, rdkit, requests) installed.
