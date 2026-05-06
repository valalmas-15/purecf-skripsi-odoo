import pandas as pd
import json
from datetime import datetime

file_path = "/Users/alle/Projects/Odoo17/purecf_erp/data/data transaksi purecf - April.xlsx"
json_output = "/Users/alle/Projects/Odoo17/purecf_erp/data/excel_data.json"

def prepare_for_import_logic():
    # Read Transactions
    df_trans = pd.read_excel(file_path, sheet_name='Transaksi', skiprows=1)
    # Read Details
    df_detail = pd.read_excel(file_path, sheet_name='Detail Transaksi', skiprows=1)
    
    # Clean up Transactions
    df_trans = df_trans.dropna(subset=['Id Transaksi'])
    
    trans_list = []
    for _, row in df_trans.iterrows():
        dt = row['Tanggal Transaksi']
        if isinstance(dt, str):
            dt_obj = datetime.strptime(dt, '%d/%m/%Y  %H:%M:%S')
        else:
            dt_obj = dt
            
        trans_list.append({
            'Id Transaksi': str(row['Id Transaksi']),
            'Total Bayar': float(row['Total Bayar']),
            'Metode Bayar': str(row['Metode Bayar']),
            'date_only': dt_obj.strftime('%Y-%m-%d'),
            'dt_parsed': dt_obj.strftime('%Y-%m-%d %H:%M:%S')
        })
        
    # Clean up Details
    df_detail = df_detail.dropna(subset=['Id Transaksi'])
    detail_list = []
    for _, row in df_detail.iterrows():
        detail_list.append({
            'Id Transaksi': str(row['Id Transaksi']),
            'Nama Barang': str(row['Nama Barang']),
            'Qty': float(row['Qty']),
            'Harga': float(row['Harga'])
        })
        
    data = {
        'trans': trans_list,
        'detail': detail_list
    }
    
    with open(json_output, 'w') as f:
        json.dump(data, f, indent=4)
        
    print(f"Prepared {len(trans_list)} transactions and {len(detail_list)} details.")

if __name__ == "__main__":
    prepare_for_import_logic()
