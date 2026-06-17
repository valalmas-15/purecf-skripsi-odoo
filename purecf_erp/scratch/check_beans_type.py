p = env['product.template'].search([('name', 'ilike', 'Beans')], limit=1)
print('Product name:', p.name)
print('Type:', p.type)
print('Is Ingredient:', p.x_is_ingredient)
