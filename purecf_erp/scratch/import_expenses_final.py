import json
import odoo
from odoo import api, SUPERUSER_ID
from datetime import datetime

def import_expenses():
    with open('/mnt/extra-addons/purecf_erp/scratch/expenses_data.json', 'r') as f:
        data = json.load(f)
    
    odoo.tools.config['db_name'] = 'purecf'
    registry = odoo.registry('purecf')
    
    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        
        # Get a default config
        default_config = env['pos.config'].search([], limit=1)
        
        for row in data:
            date_str = row.get('Tanggal')
            if not date_str or date_str == 'None':
                continue
                
            try:
                date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
            except:
                try:
                    date = datetime.strptime(date_str, '%Y-%m-%d')
                except:
                    date = datetime.now()
            
            fase = row.get('Fase', '')
            kategori = row.get('Kategori', '')
            item = row.get('Item', '')
            qty = row.get('Qty (gr/ml/pcs)', '')
            
            note = f"[{fase}] {kategori}: {item} ({qty})"
            amount_str = row.get('Total', '0').replace(',', '')
            try:
                amount = float(amount_str)
            except:
                amount = 0.0
            
            if amount > 0:
                env['purecf.expense'].create({
                    'date': date,
                    'note': note,
                    'amount': amount,
                    'config_id': default_config.id if default_config else False
                })
            
        print(f"Imported {len(data)} expense records.")

if __name__ == "__main__":
    import_expenses()
