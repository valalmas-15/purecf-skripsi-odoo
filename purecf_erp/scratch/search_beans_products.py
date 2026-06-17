products = env['product.template'].search([('name', 'ilike', 'beans')])
for p in products:
    print(p.id, p.name, p.type, p.x_is_ingredient)
