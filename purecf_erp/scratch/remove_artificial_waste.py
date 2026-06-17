import json
logs = env['purecf.audit.log'].search([
    ('change_type', '=', 'stock_adj'),
    ('create_date', '>=', '2026-05-18 00:00:00')
])
print(f"Total stock_adj logs today: {len(logs)}")
adjusted_count = 0
for log in logs:
    try:
        old_state = json.loads(log.old_state or '{}')
        new_state = json.loads(log.new_state or '{}')
        old_qty = old_state.get('qty_available', 0)
        new_qty = new_state.get('qty_available', 0)
        diff = old_qty - new_qty
        if diff > 0:
            product = env['product.template'].browse(log.res_id)
            if product.exists():
                cost = diff * product.standard_price
                # If the cost of waste is large (e.g. > Rp 5,000) or it's one of the known double-imported items
                if cost > 5000:
                    print(f"Adjusting Log ID {log.id} ({product.name}): diff was {diff}, changing old_qty to {new_qty} to remove artificial waste")
                    old_state['qty_available'] = new_qty
                    log.old_state = json.dumps(old_state)
                    adjusted_count += 1
    except Exception as e:
        print("Error with log", log.id, e)

env.cr.commit()
print(f"Successfully adjusted {adjusted_count} logs.")
