# CAS Accuracy Audit (External Verification)

> [!IMPORTANT]
> This report is based on **PubChem** as the primary source of truth. Supplier data is flagged if it contradicts PubChem's records.

## 🚨 Level 1: Critical Mismatches
Materials where the supplier provided a CAS number that disagrees with PubChem.

| Cleaned Name | Suppliers | PubChem CAS | Canonical Name |
| :--- | :--- | :--- | :--- |
| 2-Methyl-2-Pentenoic Acid | PerfumersWorld: `6297-41-2` | `3142-72-1`<br>`16957-70-3` | None |
| Aldehyde C-12 MNA | PerfumersWorld: `67634-00-8`<br>SimpleScentsDIY: `110-41-8` | `110-41-8` | 2-Methylundecanal |
| Alpha Damascone | PerfumersWorld: `43052-87-5` | `116497-11-1`<br>`23726-94-5` | (Z)-1-(2,6,6-Trimethyl-2-cyclohexen-1-yl)-2-buten-1-one |
| Beta Caryophyllene | PerfumersWorld: `87-44-5` | `10579-93-8` | (+)-beta-Caryophyllene |
| Bourgeonal | PerfumersWorld: `18127-01-0`<br>MySkinRecipes: `18127-01-0`<br>SimpleScentsDIY: `110-41-8` | `18127-01-0` | Bourgeonal |
| Camphene | PerfumersWorld: `5794-03-6`<br>MySkinRecipes: `79-92-5` | `79-92-5` | Camphene |
| Caryophyllene Acetate | PerfumersWorld: `32214-91-8` | `57082-24-3` | beta-Caryophyllene alcohol acetate |
| Cedroxyde | PerfumersWorld: `71735-79-0`<br>SimpleScentsDIY: `71735-79-0` | `13786-79-3` | 13-Oxabicyclo(10.1.0)trideca-4,8-diene, 1,5,9-trimethyl- |
| Cosmone | PerfumersWorld: `259854-70-1`<br>MySkinRecipes: `10461-98-0` | `259854-70-1`<br>`1117765-92-0` | 5-Cyclotetradecen-1-one, 3-methyl-, (5E)- |
| Coumarin | PerfumersWorld: `8008-93-3`<br>MySkinRecipes: `91-64-5` | `91-64-5` | Coumarin |
| Delta Decalactone | PerfumersWorld: `2825-91-4` | `705-86-2` | delta-Decalactone |
| Dihydro Myrcenol | PerfumersWorld: `18479-58-8` | `18479-59-9` | 7-Octen-2-ol, 2-methyl-6-methylene-, dihydro deriv. |
| Ethyl Amyl Ketone | PerfumersWorld: `106-68-3` | `541-85-5` | 5-Methyl-3-heptanone |
| Ethyl Safranate | PerfumersWorld: `35044-57-6`<br>MySkinRecipes: `35044-59-8` | `35044-59-8` | 1,3-Cyclohexadiene-1-carboxylic acid, 2,6,6-trimethyl-, ethyl ester |
| Geosmin | PerfumersWorld: `23333-91-7` | `19700-21-1` | Geosmin |
| Habanolide | PerfumersWorld: `111879-80-2`<br>MySkinRecipes: `3796-70-1` | `423773-57-3`<br>`111879-80-2` | Oxacyclohexadecen-2-one, (12E)- |
| Iso E Super | PerfumersWorld: `54464-57-2`<br>MySkinRecipes: `54464-57-2` | `59056-94-9`<br>`144651-56-9` | 1-(2,3,8,8-Tetramethyl-1,2,3,4,5,6,7,8-octahydronaphthalen-2-YL)ethanone, trans-(A+-)- |
| Isobutyl Quinoline | PerfumersWorld: `65442-31-1`<br>MySkinRecipes: `65442-31-1` | `1333-58-0`<br>`7661-51-0` | (Isobutyl)quinoline |
| Isolongifolanone | PerfumersWorld: `14727-47-0`<br>SimpleScentsDIY: `23787-90-8` | `29461-14-1`<br>`23787-90-8`<br>`33407-62-4` | Isolongifolanone |
| Jasmin Lactone | PerfumersWorld: `34686-71-0` | `25524-95-2` | Jasmine lactone |
| L-Carvone | PerfumersWorld: `99-49-0` | `6485-40-1` | Carvone, (-)- |
| Ocimene | PerfumersWorld: `13877-91-3`<br>MySkinRecipes: `13877-91-3`<br>SimpleScentsDIY: `13877-91-3` | `29714-87-2` | Ocimene |
| Phenyl Ethyl Isobutyrate | PerfumersWorld: `103-48-0` | `2901-13-5` | Benzeneacetic acid, alpha,alpha-dimethyl-, ethyl ester |
| Styralyl Alcohol | PerfumersWorld: `98-85-1`<br>MySkinRecipes: `7549-33-9` | `13323-81-4`<br>`98-85-1` | 1-Phenylethanol |
| Verdyl Acetate | PerfumersWorld: `2500-83-6`<br>MySkinRecipes: `5413-60-5` | `5413-60-5` | Verdyl acetate |
| Alpha | MySkinRecipes: `99-86-5` | `127292-42-6`<br>`1241677-25-7` | alpha-Ethyl-1,3-benzodioxole-5-methanamine |
| Muscone | MySkinRecipes: `541-91-3` | `10403-00-6` | Muscone |
| Rhodinol | MySkinRecipes: `141-25-3` | `6812-78-8` | Rhodinol |
| DeltaUndecalactone | MySkinRecipes: `710-04-3` | `104-67-6` | Gamma-undecalactone |
| Indolene 50 | MySkinRecipes: `68908-82-7` | `67801-36-9` | 1H-Indole-1-heptanol, eta-1H-indol-1-yl-alpha,alpha,epsilon-trimethyl- |

## ✅ Level 2: Verified Matches
Materials where the supplier data exactly matches PubChem.

| Cleaned Name | Verified CAS | suppliers |
| :--- | :--- | :--- |
| 2 3-Dimethyl Pyrazine | `5910-89-4` | PerfumersWorld |
| 2 Acetyl Thaizole | `24295-03-2` | PerfumersWorld |
| 2-Acetyl Pyrazine | `22047-25-2` | PerfumersWorld |
| 2-iso Propyl 4 Methyl Thiazole | `15679-13-7` | PerfumersWorld |
| 2-Methylbutyl 2-Methylbutyrate | `2445-78-5` | PerfumersWorld |
| 2-Octen-4-one | `22286-99-3` | PerfumersWorld |
| 3-Methyl-3-Methoxy Butanol | `56539-66-3` | PerfumersWorld |
| Acetic Acid | `68475-71-8` | PerfumersWorld |
| Acetoin | `513-86-0` | PerfumersWorld, MySkinRecipes |
| Acetophenone | `98-86-2` | PerfumersWorld, MySkinRecipes |
| Acetyl Isoeugenol | `93-29-8` | PerfumersWorld |
| Adoxal | `141-13-9` | PerfumersWorld, MySkinRecipes |
| Alcohol C-7 Heptanol | `53535-33-4` | PerfumersWorld |
| Alcohol C-8 Octanol | `111-87-5` | PerfumersWorld |
| Alcohol C-9 | `143-08-8` | PerfumersWorld |
| Aldehyde C-10 Decanal | `67634-00-8` | PerfumersWorld |
| Aldehyde C-11 Undecanal | `112-44-7` | PerfumersWorld |
| Aldehyde C-11 Undecylenic | `112-45-8` | PerfumersWorld |
| Aldehyde C-12 Lauric Dodecanal | `67634-00-8` | PerfumersWorld |
| Aldehyde C-14 Gamma Undecalactone | `104-67-6` | PerfumersWorld |
| Aldehyde C-16 Ethyl Methyl Phenyl Glycidate | `19464-95-0` | PerfumersWorld |
| Aldehyde C-18 Gamma Nonalactone | `104-61-0` | PerfumersWorld |
| Aldehyde C-7 Heptanal | `111-71-7` | PerfumersWorld |
| Aldehyde C-8 Octanal | `9006-52-4` | PerfumersWorld |
| Aldehyde C-9 Nonanal | `75718-12-6` | PerfumersWorld |
| Algix Pure | `72987-59-8` | PerfumersWorld |
| Allyl Amyl Glycolate | `67634-00-8` | PerfumersWorld, MySkinRecipes, SimpleScentsDIY |
| Allyl Caproate | `123-68-2` | PerfumersWorld |
| Allyl Ionone Cetone V | `79-78-7` | PerfumersWorld |
| Alpha Ionone | `127-41-3` | PerfumersWorld |
| Alpha Irone | `79-69-6` | PerfumersWorld |
| Alpha Isomethyl Ionone | `127-51-5` | PerfumersWorld |
| Alpha Pinene | `2437-95-8` | PerfumersWorld |
| Alpha Terpineol | `98-55-5` | PerfumersWorld |
| Amber Core | `139504-68-0` | PerfumersWorld |
| Amber Decane | `58567-11-6` | PerfumersWorld, MySkinRecipes |
| Amberketal IPM | `57345-19-4` | PerfumersWorld |
| Ambermax | `929625-08-1` | PerfumersWorld |
| Ambrettolide | `123-69-3` | PerfumersWorld |
| Ambrocenide | `211299-54-6` | PerfumersWorld |
| Ambrofix | `6790-58-5` | PerfumersWorld |
| Ambrox Super | `6790-58-5` | PerfumersWorld |
| Ambroxan | `6790-58-5` | PerfumersWorld, MySkinRecipes |
| Amyl Cinnamic Aldehyde | `122-40-7` | PerfumersWorld |
| Amyl Valerate | `2173-56-0` | PerfumersWorld, MySkinRecipes |
| Anethole | `50770-19-9` | PerfumersWorld, MySkinRecipes |
| Anisaldehyde | `123-11-5` | PerfumersWorld |
| Anisyl Acetate | `1331-83-5` | PerfumersWorld |
| Anisyl Alcohol | `105-13-5` | PerfumersWorld |
| Anthopogen Essential Oil | `116-26-7` | PerfumersWorld |
| ... and 481 more | | |

## 📊 Summary
- **Matches Found**: 531
- **Critical Mismatches**: 30
- **Data Gaps (No PC Match)**: 737

*Last updated: 2026-04-02 00:44:16*
