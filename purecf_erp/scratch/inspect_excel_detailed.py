import pandas as pd
import os

file = "/Users/alle/Projects/Odoo17/purecf_erp/data/data transaksi purecf - April.xlsx"

try:
    xl = pd.ExcelFile(file)
    print("--- Sheet Names ---")
    print(xl.sheet_names)
    
    for sheet in xl.sheet_names:
        print(f"\n--- First 10 rows of sheet: {sheet} ---")
        df = pd.read_excel(file, sheet_name=sheet, header=None)
        print(df.head(10))
        
except Exception as e:
    print(f"Error reading {file}: {e}")
