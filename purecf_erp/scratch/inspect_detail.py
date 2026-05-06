import pandas as pd
import os

file = "purecf_erp/data/data transaksi purecf - April.xlsx"
abs_path = os.path.join("/Users/alle/Projects/Odoo17", file)

try:
    df = pd.read_excel(abs_path, sheet_name='Detail Transaksi', header=1)
    print("Columns:", df.columns.tolist())
    print("Head:")
    print(df.head(20))
except Exception as e:
    print(f"Error: {e}")
