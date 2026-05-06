
import odoo
from odoo import api, SUPERUSER_ID

db_name = 'purecf'
registry = odoo.registry(db_name)
with registry.cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    session = env['pos.session'].browse(57)
    if session.exists():
        print(f"Session: {session.name}, State: {session.state}, Start (UTC): {session.start_at}")
        orders = session.order_ids
        print(f"Total Orders in session: {len(orders)}")
        for o in orders:
            print(f"  Name: {o.name}, Date (UTC): {o.date_order}, State: {o.state}, Total: {o.amount_total}")
    else:
        print("Session 57 not found")
