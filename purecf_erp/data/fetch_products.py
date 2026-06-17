import json
products = env['product.template'].search([])
names = [{'id': p.id, 'name': p.name, 'uom': p.uom_id.name, 'variant_id': p.product_variant_id.id if p.product_variant_id else None} for p in products]
print(json.dumps(names))
