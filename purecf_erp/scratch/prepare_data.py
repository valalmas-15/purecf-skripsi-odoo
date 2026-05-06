import pandas as pd
import json
from datetime import datetime

file_path = "/Users/alle/Projects/Odoo17/purecf_erp/data/data transaksi purecf - April.xlsx"

def excel_to_json():
    # Read Transactions
    df_trans = pd.read_excel(file_path, sheet_name='Transaksi', skiprows=1)
    # Read Details
    df_details = pd.read_excel(file_path, sheet_name='Detail Transaksi', skiprows=1)
    
    # Clean up
    df_trans = df_trans.dropna(subset=['Id Transaksi'])
    df_details = df_details.dropna(subset=['Id Transaksi'])
    
    # Convert to list of dicts
    trans_data = df_trans.to_dict(orient='records')
    detail_data = df_details.to_dict(orient='records')
    
    # Process transactions to include details
    processed_data = []
    for t in trans_data:
        # Format date
        date_str = str(t['Tanggal Transaksi'])
        try:
            # Check if it's already a datetime object or a string
            if isinstance(t['Tanggal Transaksi'], datetime):
                dt = t['Tanggal Transaksi']
            else:
                dt = datetime.strptime(date_str, '%d/%m/%Y  %H:%M:%S')
            t['date_order'] = dt.strftime('%Y-%m-%d %H:%M:%S')
        except Exception as e:
            print(f"Error parsing date {date_str}: {e}")
            t['date_order'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
        t_id = t['Id Transaksi']
        t['details'] = [d for d in detail_data if d['Id Transaksi'] == t_id]
        processed_data.append(t)
        
    with open('/Users/alle/Projects/Odoo17/purecf_erp/scratch/transaksi_data.json', 'w') as f:
        json.dump(processed_data, f, indent=4, default=str)
    
    print(f"Exported {len(processed_data)} transactions to JSON.")

if __name__ == "__main__":
    excel_to_json()
