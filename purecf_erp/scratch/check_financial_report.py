import json
start_dt = '2026-04-01 00:00:00'
end_dt = '2026-05-18 23:59:59'
waste_logs = env['purecf.audit.log'].search([
    ('change_type', '=', 'stock_adj'),
    ('create_date', '>=', start_dt),
    ('create_date', '<=', end_dt)
])
total_waste = 0.0
for log in waste_logs:
    old_qty = json.loads(log.old_state or '{}').get('qty_available', 0)
    new_qty = json.loads(log.new_state or '{}').get('qty_available', 0)
    diff = old_qty - new_qty
    if diff > 0:
        product = env['product.template'].browse(log.res_id)
        if product.exists():
            total_waste += diff * product.standard_price
print("TOTAL WASTE COST AFTER ADJUSTMENT:", total_waste)
