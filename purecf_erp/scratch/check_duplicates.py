import pandas as pd
import os

file = "purecf_erp/data/data transaksi purecf - April.xlsx"
abs_path = os.path.join("/Users/alle/Projects/Odoo17", file)

try:
    df = pd.read_excel(abs_path, header=1) # The header is on row 1
    print("Shape:", df.shape)
    print("Unique Id Transaksi count:", df['Id Transaksi'].nunique())
    print("Duplicate Id Transaksi count:", df['Id Transaksi'].duplicated().sum())
    if df['Id Transaksi'].duplicated().any():
        print("Example duplicates:")
        print(df[df['Id Transaksi'].duplicated(keep=False)].head(10))
except Exception as e:
    print(f"Error: {e}")
