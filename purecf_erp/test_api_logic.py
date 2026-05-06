import odoo
from odoo import api, SUPERUSER_ID

odoo.tools.config.parse_config(['-d', 'purecf'])
registry = odoo.registry('purecf')

with registry.cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    user = env['res.users'].search([('login', '!=', '__system__')], limit=1)
    print(f"TEST_LOGIN={user.login}")
    
    # Also test the logic directly in the script to see the response
    warehouse_id = user.x_allowed_warehouse_id.id if user.x_allowed_warehouse_id else False
    ctx = {'warehouse': warehouse_id}
    
    ingredients = env['product.template'].with_context(ctx).search_read(
        ['|', ('x_is_ingredient', '=', True), ('purchase_ok', '=', True)],
        ['name', 'qty_available']
    )
    
    print("\nAPI Logic Test Result:")
    for ing in ingredients[:5]:
        print(f" - {ing['name']}: {ing['qty_available']}")
