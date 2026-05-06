
import odoo
from odoo import api, SUPERUSER_ID

db_name = 'purecf'
registry = odoo.registry(db_name)
with registry.cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    orders = env['pos.order'].search([], order='id desc', limit=10)
    print(f"Latest 10 orders:")
    for o in orders:
        print(f"ID: {o.id}, Name: {o.name}, Date (UTC): {o.date_order}, State: {o.state}, Total: {o.amount_total}")
