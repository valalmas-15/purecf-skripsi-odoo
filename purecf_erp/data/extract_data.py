import openpyxl
import re

file_path = '/Users/alle/Projects/Odoo17/purecf_erp/data/Data Pengeluaran April.xlsx'

def clean_money(val):
    if not val: return 0.0
    if isinstance(val, (int, float)): return float(val)
    # Remove Rp, dots, and convert to float
    clean = re.sub(r'[^\d]', '', str(val))
    return float(clean) if clean else 0.0

def read_excel():
    wb = openpyxl.load_workbook(file_path, data_only=True)
    sheet = wb.active
    
    all_data = []
    
    # Week mappings (start_col, week_name)
    weeks = [
        (2, 'Minggu I'),
        (8, 'Minggu II'),
        (14, 'Minggu III'),
        (20, 'Minggu IV')
    ]
    
    for start_col, week_name in weeks:
        # Row 3 to 20 approx
        for row_idx in range(3, 21):
            row = [sheet.cell(row=row_idx, column=c).value for c in range(start_col, start_col + 5)]
            name, qty, uom, price_unit, price_total = row
            
            if not name or "TOTAL" in str(name).upper() or str(name).strip() == "":
                continue
                
            # Skip category headers (they usually have no qty/price)
            if qty is None and price_total is None:
                continue

            all_data.append({
                'week': week_name,
                'name': name.strip(),
                'qty': float(qty) if qty else 0.0,
                'price_total': clean_money(price_total)
            })
            
    return all_data

if __name__ == "__main__":
    data = read_excel()
    for d in data:
        print(d)
