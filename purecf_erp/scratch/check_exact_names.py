names = [
    'Beans', 'Susu UHT', 'Cup Ice', 'Creamer', 'Matcha Powder', 
    'Chocolate Powder', 'Liquid Shaka', 'Liquid Palme', 'Liquid Scothcie', 
    'Liquid Vanille', 'Liquid Monkist', 'Liquid Nutty', 'Liquid Rume', 'Lychee Based'
]
for name in names:
    exact = env['product.template'].search([('name', '=', name)], limit=1)
    ilike = env['product.template'].search([('name', 'ilike', name)], limit=1)
    print(f"Name: {name}")
    print(f"  Exact: ID={exact.id}, Name='{exact.name}', Type='{exact.type}'" if exact else "  Exact: NOT FOUND")
    print(f"  Ilike: ID={ilike.id}, Name='{ilike.name}', Type='{ilike.type}'" if ilike else "  Ilike: NOT FOUND")
