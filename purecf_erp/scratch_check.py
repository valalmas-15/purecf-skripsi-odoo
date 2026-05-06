import odoo
from odoo import api, SUPERUSER_ID

# Setup Odoo
odoo.tools.config.parse_config(['-d', 'purecf'])
registry = odoo.registry('purecf')

with registry.cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    
    # Check POS Orders
    pos_orders = env['pos.order'].search([])
    print(f"Total POS Orders: {len(pos_orders)}")
    for order in pos_orders[:5]:
        print(f" - Order: {order.name}, State: {order.state}, Total: {order.amount_total}, Date: {order.date_order}")

    # Check Account Moves (Expenses)
    expenses = env['account.move'].search([('move_type', 'in', ['in_invoice', 'in_receipt'])])
    print(f"Total Expenses (Vendor Bills/Receipts): {len(expenses)}")
    for move in expenses[:5]:
        print(f" - Move: {move.name}, State: {move.state}, Total: {move.amount_total}")

    # Check Ingredients (Stock Value)
    ingredients = env['product.template'].search([('x_is_ingredient', '=', True)])
    print(f"Total Ingredients: {len(ingredients)}")
    for ing in ingredients[:10]:
        print(f" - {ing.name}: Qty={ing.qty_available}, Cost={ing.standard_price}, Total={ing.qty_available * ing.standard_price}")
