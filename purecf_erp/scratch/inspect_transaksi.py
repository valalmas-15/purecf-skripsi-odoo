import pandas as pd
import os

file = "/Users/alle/Projects/Odoo17/purecf_erp/data/data transaksi purecf - April.xlsx"

try:
    df = pd.read_excel(file)
    print("--- Columns found in Excel ---")
    print(df.columns.tolist())
    
    # Check for payment method column (could be 'Metode Pembayaran', 'Payment Method', etc.)
    payment_col = None
    for col in df.columns:
        if 'pembayaran' in col.lower() or 'payment' in col.lower():
            payment_col = col
            break
            
    if payment_col:
        print(f"\n--- Unique Payment Methods in '{payment_col}' ---")
        counts = df[payment_col].value_counts()
        print(counts)
    else:
        print("\nCould not find a payment method column.")
        
except Exception as e:
    print(f"Error reading {file}: {e}")
