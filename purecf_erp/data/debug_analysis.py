import json
from datetime import date

date_from = date(2024, 4, 1)
date_to = date(2024, 4, 30)

ingredients = env['product.template'].search([('x_is_ingredient', '=', True)])
print("Ingredients:", len(ingredients))

for ingredient in ingredients:
    stock_in_logs = env['purecf.audit.log'].search([
        ('res_model', '=', 'product.template'),
        ('res_id', '=', ingredient.id),
        ('change_type', '=', 'stock_in'),
        ('create_date', '>=', '2024-04-01 00:00:00'),
        ('create_date', '<', '2024-05-01 00:00:00')
    ])
    
    total_in = 0.0
    for log in stock_in_logs:
        try:
            new_s = json.loads(log.new_state)
            old_s = json.loads(log.old_state)
            total_in += (new_s.get('qty_available', 0) - old_s.get('qty_available', 0))
        except Exception as e:
            print("ERROR", e)
            
    if len(stock_in_logs) > 0 or total_in > 0:
        print(f"{ingredient.name}: logs={len(stock_in_logs)}, total_in={total_in}")
