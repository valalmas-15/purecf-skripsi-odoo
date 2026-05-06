import pandas as pd
import os

files = [
    "purecf_erp/data/data pengeluaran purecf - April.xlsx",
    "purecf_erp/data/data transaksi purecf - April.xlsx"
]

for file in files:
    abs_path = os.path.join("/Users/alle/Projects/Odoo17", file)
    print(f"--- File: {file} ---")
    try:
        df = pd.read_excel(abs_path)
        print("Columns:", df.columns.tolist())
        print("Head:")
        print(df.head())
        print("\n")
    except Exception as e:
        print(f"Error reading {file}: {e}")
