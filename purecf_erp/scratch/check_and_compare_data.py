import openpyxl
import re

# Read original April data
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

print(f"Total items in original Excel: {len(orig_items)}")
orig_total_cost = sum(x['price_total'] for x in orig_items)
print(f"Original Excel Total Cost: Rp{orig_total_cost:,.0f}")

# Now get expenses from Odoo
expenses = env['purecf.expense'].search([('note', '=like', '[Bahan Baku] Pembelian %')])
print(f"Total [Bahan Baku] expenses in Odoo: {len(expenses)}")
odoo_total_cost = sum(e.amount for e in expenses)
print(f"Odoo Total Cost: Rp{odoo_total_cost:,.0f}")

# Let's group and check
import collections
odoo_groups = collections.defaultdict(list)
for e in expenses:
    date_str = str(e.date)[:10]
    odoo_groups[date_str].append(e)

print("\n--- COMPARISON ---")
for start_col, week_name, date_str in orig_weeks:
    orig_week_items = [x for x in orig_items if x['week'] == week_name]
    odoo_week_items = odoo_groups.get(date_str, [])
    
    print(f"\n{week_name} ({date_str}):")
    print(f"  Excel items count: {len(orig_week_items)}, Cost: Rp{sum(x['price_total'] for x in orig_week_items):,.0f}")
    print(f"  Odoo items count: {len(odoo_week_items)}, Cost: Rp{sum(x.amount for x in odoo_week_items):,.0f}")
    
    # Show detail comparisons
    print("  Details in Odoo:")
    for o_item in odoo_week_items:
        print(f"    - ID: {o_item.id}, Note: {o_item.note}, Amount: Rp{o_item.amount:,.0f}")
