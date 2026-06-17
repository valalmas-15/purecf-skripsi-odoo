import json
logs = env['purecf.audit.log'].search([('change_type', '=', 'stock_adj')])
print(f'Total stock_adj logs: {len(logs)}')
for log in logs:
    print(log.id, log.create_date, log.note)
    print("Old state:", log.old_state)
    print("New state:", log.new_state)
    product = env['product.template'].browse(log.res_id)
    if product.exists():
        print("Product standard price:", product.standard_price)
    print("-" * 50)
