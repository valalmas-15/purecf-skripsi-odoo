import json
import logging
from odoo import api, SUPERUSER_ID

logger = logging.getLogger(__name__)

data = [
    {'week': 'Minggu I', 'name': 'Beans (Biji Kopi)', 'qty': 5.0, 'price_total': 875000.0, 'odoo_name': 'Beans'},
    {'week': 'Minggu I', 'name': 'Susu UHT', 'qty': 3.0, 'price_total': 663000.0, 'odoo_name': 'Susu UHT'},
    {'week': 'Minggu I', 'name': 'Paper Cup 22oz', 'qty': 1.0, 'price_total': 860000.0, 'odoo_name': 'Cup Ice'},
    {'week': 'Minggu I', 'name': 'Creamer', 'qty': 25.0, 'price_total': 1150000.0, 'odoo_name': 'Creamer'},
    {'week': 'Minggu I', 'name': 'Matcha Powder', 'qty': 1.0, 'price_total': 107000.0, 'odoo_name': 'Matcha Powder'},
    {'week': 'Minggu I', 'name': 'Chocolate Powder', 'qty': 1.0, 'price_total': 170000.0, 'odoo_name': 'Chocolate Powder'},
    {'week': 'Minggu I', 'name': 'Syrup Shaka', 'qty': 3.0, 'price_total': 321000.0, 'odoo_name': 'Liquid Shaka'},
    {'week': 'Minggu I', 'name': 'Syrup Palme', 'qty': 3.0, 'price_total': 264000.0, 'odoo_name': 'Liquid Palme'},
    {'week': 'Minggu I', 'name': 'Syrup Scotchie', 'qty': 2.0, 'price_total': 190000.0, 'odoo_name': 'Liquid Scothcie'},
    {'week': 'Minggu I', 'name': 'Syrup Vanille', 'qty': 2.0, 'price_total': 208000.0, 'odoo_name': 'Liquid Vanille'},
    {'week': 'Minggu I', 'name': 'Syrup Monkist', 'qty': 2.0, 'price_total': 214000.0, 'odoo_name': 'Liquid Monkist'},
    {'week': 'Minggu I', 'name': 'Syrup Nutty', 'qty': 2.0, 'price_total': 212000.0, 'odoo_name': 'Liquid Nutty'},
    {'week': 'Minggu I', 'name': 'Syrup Rume', 'qty': 1.0, 'price_total': 111000.0, 'odoo_name': 'Liquid Rume'},
    {'week': 'Minggu I', 'name': 'Fruit Base (Lyche/Lemon)', 'qty': 4.0, 'price_total': 248000.0, 'odoo_name': 'Lychee Based'}, # Mapping to lychee for now
    
    {'week': 'Minggu II', 'name': 'Susu UHT', 'qty': 3.0, 'price_total': 663000.0, 'odoo_name': 'Susu UHT'},
    
    {'week': 'Minggu III', 'name': 'Beans (Biji Kopi)', 'qty': 5.0, 'price_total': 875000.0, 'odoo_name': 'Beans'},
    {'week': 'Minggu III', 'name': 'Susu UHT', 'qty': 3.0, 'price_total': 663000.0, 'odoo_name': 'Susu UHT'},
    {'week': 'Minggu III', 'name': 'Paper Cup 22oz', 'qty': 1.0, 'price_total': 860000.0, 'odoo_name': 'Cup Ice'},
    {'week': 'Minggu III', 'name': 'Matcha Powder', 'qty': 1.0, 'price_total': 107000.0, 'odoo_name': 'Matcha Powder'},
    {'week': 'Minggu III', 'name': 'Syrup Shaka', 'qty': 3.0, 'price_total': 321000.0, 'odoo_name': 'Liquid Shaka'},
    {'week': 'Minggu III', 'name': 'Syrup Palme', 'qty': 2.0, 'price_total': 176000.0, 'odoo_name': 'Liquid Palme'},
    {'week': 'Minggu III', 'name': 'Syrup Scotchie', 'qty': 2.0, 'price_total': 190000.0, 'odoo_name': 'Liquid Scothcie'},
    {'week': 'Minggu III', 'name': 'Syrup Vanille', 'qty': 2.0, 'price_total': 208000.0, 'odoo_name': 'Liquid Vanille'},
    {'week': 'Minggu III', 'name': 'Fruit Base (Lyche/Lemon)', 'qty': 2.0, 'price_total': 124000.0, 'odoo_name': 'Lychee Based'},
    
    {'week': 'Minggu IV', 'name': 'Susu UHT', 'qty': 3.0, 'price_total': 663000.0, 'odoo_name': 'Susu UHT'},
]

# Clean up old imports (Rollback stock first)
old_audits = env['purecf.audit.log'].search([('note', 'ilike', 'dari file April')])
for log in old_audits:
    try:
        old_state = json.loads(log.old_state)
        new_state = json.loads(log.new_state)
        old_qty = old_state.get('qty_available', 0.0)
        new_qty = new_state.get('qty_available', 0.0)
        location_id = new_state.get('location_id')
        
        diff = new_qty - old_qty
        if diff > 0:
            product_tmpl = env['product.template'].browse(log.res_id)
            if product_tmpl.exists() and product_tmpl.type == 'product':
                product_variant = product_tmpl.product_variant_id
                if product_variant:
                    quant = env['stock.quant'].sudo().with_context(inventory_mode=True).search([
                        ('product_id', '=', product_variant.id),
                        ('location_id', '=', location_id)
                    ], limit=1)
                    if quant:
                        old_cost = old_state.get('cost')
                        if old_cost:
                            product_tmpl.sudo().write({'standard_price': old_cost})
                        
                        quant.inventory_quantity = quant.quantity - diff
                        quant.action_apply_inventory()
                        print(f"REVERTED: {product_tmpl.name} (subtracted {diff})")
    except Exception as e:
        print(f"Error reverting log {log.id}: {e}")

old_expenses = env['purecf.expense'].search([
    ('note', '=like', '[Bahan Baku] Pembelian %'),
    ('date', 'in', [
        '2026-04-07 10:00:00',
        '2026-04-14 10:00:00',
        '2026-04-21 10:00:00',
        '2026-04-28 10:00:00'
    ])
])
old_expenses.unlink()

old_audits.unlink()

week_dates = {
    'Minggu I': '2026-04-07 10:00:00',
    'Minggu II': '2026-04-14 10:00:00',
    'Minggu III': '2026-04-21 10:00:00',
    'Minggu IV': '2026-04-28 10:00:00',
}

for row in data:
    product = env['product.template'].search([('name', '=', row['odoo_name'])], limit=1)
    if product:
        # Convert quantity properly if UoM differ. E.g. beans in kg, but Odoo in gr.
        # Susu UHT in krat (we need to know what krat means in ml).
        # Let's assume standard quantities or we adjust here:
        qty = row['qty']
        uom_name = product.uom_id.name.lower()
        
        # Manual conversions based on name and assumed standard
        if 'beans' in row['odoo_name'].lower() and uom_name == 'gr':
            qty = qty * 1000 # 5 kg -> 5000 gr
        elif 'powder' in row['odoo_name'].lower() and uom_name == 'gr':
            qty = qty * 1000 # 1 kg -> 1000 gr
        elif 'creamer' in row['odoo_name'].lower() and uom_name == 'gr':
            qty = qty * 1000 # 25 kg -> 25000 gr
        elif 'susu uht' in row['odoo_name'].lower() and uom_name == 'ml':
            qty = qty * 12 * 1000 # 1 krat usually 12 liters/boxes
        elif 'cup' in row['odoo_name'].lower() and uom_name == 'units':
            qty = qty * 1000 # 1 dus = 1000 pcs (often) - let's assume 1000
        elif 'liquid' in row['odoo_name'].lower() or 'based' in row['odoo_name'].lower():
            if uom_name == 'ml':
                qty = qty * 750 # 1 bottle usually 750ml or 1000ml
        
        # Note
        note = f"[Bahan Baku] {row['week']} - Pembelian {row['qty']} dari file April"
        record_date = week_dates.get(row['week'], '2024-04-01 10:00:00')
        
        # Execute stock incoming
        try:
            product.action_add_stock_incoming(
                incoming_qty=qty, 
                admin_id=env.user.id, 
                total_price=row['price_total'], 
                note=note,
                date=record_date
            )
            print(f"SUCCESS: Imported {row['name']} ({qty} {uom_name}) - Total: Rp{row['price_total']}")
        except Exception as e:
            print(f"ERROR processing {row['name']}: {str(e)}")
    else:
        print(f"PRODUCT NOT FOUND: {row['odoo_name']}")

env.cr.commit()
print("Import Complete.")

