import openpyxl
import re
import subprocess
import json

# 1. Read original Excel
def clean_money(val):
    if not val: return 0.0
    if isinstance(val, (int, float)): return float(val)
    clean = re.sub(r'[^\d]', '', str(val))
    return float(clean) if clean else 0.0

wb_original = openpyxl.load_workbook('/Users/alle/Projects/Odoo17/purecf_erp/data/Data Pengeluaran April.xlsx', data_only=True)
sheet_orig = wb_original.active

orig_weeks = [
    (2, 'Minggu I', '2026-04-07'),
    (8, 'Minggu II', '2026-04-14'),
    (14, 'Minggu III', '2026-04-21'),
    (20, 'Minggu IV', '2026-04-28')
]

orig_items = []
for start_col, week_name, date_str in orig_weeks:
    for row_idx in range(3, 21):
        row = [sheet_orig.cell(row=row_idx, column=c).value for c in range(start_col, start_col + 5)]
        name, qty, uom, price_unit, price_total = row
        if not name or "TOTAL" in str(name).upper() or str(name).strip() == "":
            continue
        if qty is None and price_total is None:
            continue
        orig_items.append({
            'week': week_name,
            'date': date_str,
            'name': name.strip(),
            'qty': float(qty) if qty else 0.0,
            'price_total': clean_money(price_total)
        })

orig_total_cost = sum(x['price_total'] for x in orig_items)

# 2. Get Odoo expenses via psql
psql_cmd = [
    'docker', 'exec', '-i', 'odoo17-web-1', 
    'psql', '-U', 'odoo', '-h', 'db', 'purecf', 
    '-A', '-F', ',', '-c', 
    "SELECT id, date, amount, note FROM purecf_expense WHERE note LIKE '[Bahan Baku] Pembelian %';"
]

# We need to send password 'odoo' to stdin
process = subprocess.Popen(psql_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
stdout, stderr = process.communicate(input='odoo\n')

odoo_items = []
lines = stdout.strip().split('\n')
if len(lines) > 1:
    header = lines[0].split(',')
    for line in lines[1:]:
        if not line or 'rows' in line:
            continue
        parts = line.split(',')
        if len(parts) >= 4:
            exp_id = parts[0]
            date_val = parts[1]
            amount = float(parts[2])
            note = ','.join(parts[3:]) # handle notes with commas
            odoo_items.append({
                'id': exp_id,
                'date': date_val,
                'amount': amount,
                'note': note
            })

print(f"Total items in original Excel: {len(orig_items)}")
print(f"Original Excel Total Cost: Rp{orig_total_cost:,.0f}")
print(f"Total expenses in Odoo: {len(odoo_items)}")
print(f"Odoo Total Cost: Rp{sum(x['amount'] for x in odoo_items):,.0f}")

# 3. Check for duplicates in Odoo
# Group by date and note to see if there are exact duplicates
duplicates = []
seen = set()
for exp in odoo_items:
    key = (exp['date'][:10], exp['amount'], exp['note'])
    if key in seen:
        duplicates.append(exp)
    else:
        seen.add(key)

print(f"\nDuplicate count in Odoo: {len(duplicates)}")
if duplicates:
    print("Example duplicate records:")
    for d in duplicates[:5]:
        print(f"  ID: {d['id']}, Date: {d['date']}, Amount: {d['amount']}, Note: {d['note']}")

# 4. Compare Week-by-Week
import collections
odoo_groups = collections.defaultdict(list)
for e in odoo_items:
    d_str = e['date'][:10]
    odoo_groups[d_str].append(e)

print("\n--- WEEK-BY-WEEK SUMMARY ---")
for start_col, week_name, date_str in orig_weeks:
    orig_week_items = [x for x in orig_items if x['week'] == week_name]
    odoo_week_items = odoo_groups.get(date_str, [])
    
    print(f"\n{week_name} ({date_str}):")
    print(f"  Excel items count: {len(orig_week_items)}, Cost: Rp{sum(x['price_total'] for x in orig_week_items):,.0f}")
    print(f"  Odoo items count: {len(odoo_week_items)}, Cost: Rp{sum(x['amount'] for x in odoo_week_items):,.0f}")
