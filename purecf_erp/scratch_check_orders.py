
orders = env['pos.order'].search([])
print(f"Total orders: {len(orders)}")
for state in set(orders.mapped('state')):
    count = len(orders.filtered(lambda o: o.state == state))
    print(f"State '{state}': {count} orders")

if orders:
    print(f"Date range: {min(orders.mapped('date_order'))} to {max(orders.mapped('date_order'))}")
    
# Check for today's orders specifically
from odoo import fields
today = fields.Date.today()
today_orders = env['pos.order'].search([
    ('date_order', '>=', f"{today} 00:00:00"),
    ('date_order', '<=', f"{today} 23:59:59")
])
print(f"Orders today ({today}): {len(today_orders)}")
for state in set(today_orders.mapped('state')):
    count = len(today_orders.filtered(lambda o: o.state == state))
    print(f"State '{state}': {count} orders")
