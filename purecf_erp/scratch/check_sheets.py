import pandas as pd
import os

file = "purecf_erp/data/data transaksi purecf - April.xlsx"
abs_path = os.path.join("/Users/alle/Projects/Odoo17", file)

try:
    xl = pd.ExcelFile(abs_path)
    print("Sheet names:", xl.sheet_names)
    for sheet in xl.sheet_names:
        df = pd.read_excel(abs_path, sheet_name=sheet, nrows=10)
        print(f"\n--- Sheet: {sheet} ---")
        print(df.columns.tolist())
        print(df.head())
except Exception as e:
    print(f"Error: {e}")
