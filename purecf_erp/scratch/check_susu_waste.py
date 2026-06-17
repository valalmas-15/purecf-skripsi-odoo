import json
logs = env['purecf.audit.log'].search([('change_type', '=', 'stock_adj'), ('res_id', '=', 7)])
print(f'Total stock_adj logs for Susu UHT: {len(logs)}')
for log in logs:
    old_state = json.loads(log.old_state or '{}')
    new_state = json.loads(log.new_state or '{}')
    old_qty = old_state.get('qty_available', 0)
    new_qty = new_state.get('qty_available', 0)
    diff = old_qty - new_qty
    print(log.id, log.create_date, "diff:", diff, "old:", old_qty, "new:", new_qty, "note:", log.note)
