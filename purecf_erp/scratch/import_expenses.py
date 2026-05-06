import pandas as pd
import odoo
from odoo import api, SUPERUSER_ID
from datetime import datetime

def import_expenses():
    file_path = '/Users/alle/Projects/Odoo17/purecf_erp/data/data pengeluaran purecf - April.xlsx'
    df = pd.read_excel(file_path)
    
    # Map columns: Tanggal, Keterangan, Kategori, Nama Barang, Qty, Harga Satuan, Total
    # to purecf.expense: date, note, amount
    
    odoo.tools.config['db_name'] = 'purecf'
    registry = odoo.registry('purecf')
    
    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        
        # Get a default config (e.g. the first one) for branch filtering
        default_config = env['pos.config'].search([], limit=1)
        
        for index, row in df.iterrows():
            date_str = str(row['Tanggal'])
            # Parse date if it's not already a datetime
            try:
                if isinstance(row['Tanggal'], datetime):
                    date = row['Tanggal']
                else:
                    date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
            except:
                date = datetime.now()
                
            note = f"[{row['Keterangan']}] {row['Kategori']}: {row['Nama Barang']} ({row['Qty']})"
            amount = float(row['Total'])
            
            env['purecf.expense'].create({
                'date': date,
                'note': note,
                'amount': amount,
                'config_id': default_config.id if default_config else False
            })
            
        print(f"Imported {len(df)} expense records.")

if __name__ == "__main__":
    import_expenses()
