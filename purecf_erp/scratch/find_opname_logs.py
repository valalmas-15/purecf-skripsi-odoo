import json
# Find all stock_adj logs created around 2026-05-18 16:37:34
logs = env['purecf.audit.log'].search([
    ('change_type', '=', 'stock_adj'),
    ('create_date', '>=', '2026-05-18 16:37:00'),
    ('create_date', '<=', '2026-05-18 16:38:00')
])
print(f"Found {len(logs)} logs around that time:")
for log in logs:
    product = env['product.template'].browse(log.res_id)
    print(f"Log ID: {log.id}, Product: {product.name if product.exists() else 'Unknown'}, Note: {log.note}")
    print(f"  Old state: {log.old_state}")
    print(f"  New state: {log.new_state}")
