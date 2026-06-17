import json
logs = env['purecf.audit.log'].search([('change_type', '=', 'stock_adj')])
print(f"Total stock_adj logs: {len(logs)}")
waste_map = {}
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
                if product.name not in waste_map:
                    waste_map[product.name] = {'qty': 0, 'cost': 0, 'logs': []}
                waste_map[product.name]['qty'] += diff
                waste_map[product.name]['cost'] += cost
                waste_map[product.name]['logs'].append((log.id, log.create_date, diff, old_qty, new_qty, log.note))
    except Exception as e:
        print("Error", log.id, e)

for name, info in sorted(waste_map.items(), key=lambda x: x[1]['cost'], reverse=True)[:5]:
    print(f"Product: {name}, Total Qty: {info['qty']}, Total Cost: {info['cost']}")
    for l in info['logs']:
        print(f"  Log ID: {l[0]}, Date: {l[1]}, Diff: {l[2]}, Old: {l[3]}, New: {l[4]}, Note: {l[5]}")
