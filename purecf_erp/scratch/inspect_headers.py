import pandas as pd

file = "/Users/alle/Projects/Odoo17/purecf_erp/data/data transaksi purecf - April.xlsx"

xl = pd.ExcelFile(file)

for sheet in xl.sheet_names:
    print(f"\n--- Headers for sheet: {sheet} ---")
    df = pd.read_excel(file, sheet_name=sheet, skiprows=1)
    print(df.columns.tolist())
    print("\n--- First row of data ---")
    print(df.iloc[0].to_dict())
