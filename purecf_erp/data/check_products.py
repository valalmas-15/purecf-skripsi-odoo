import json
# Odoo shell script
products = env['product.template'].search([])
names = [p.name for p in products]
print(json.dumps(names))
